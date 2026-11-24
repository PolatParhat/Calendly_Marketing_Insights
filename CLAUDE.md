# Calendly Marketing Insights: project rules

State: STATUS.md · History: docs/decisions.md · Requirements: docs/00_requirements/requirements.txt

## Goal
Build a production-level AWS data pipeline that ingests Calendly bookings (via webhook) and daily
marketing spend (public S3 JSON), stores them in Delta Lake on S3 (Bronze/Silver/Gold), computes the
six business metrics, and shows them in a Streamlit dashboard.

## Hard constraints (from the requirements doc, the source of truth)
- Entire architecture on **AWS**. Data stored in **Delta Lake on top of S3**.
- Follow one of the two given Lambda-architecture diagrams (docs/00_requirements/architecture_option_*.jpg):
  A = Delta Lake + Amazon EMR, B = Databricks; both then Data Warehouse -> Visualisation.
- Pipeline must have **scheduling, encryption, and a failure-reload mechanism**.
- Calendly event: webhook `invitee.created` only. Webhook is created by the SME: we send them our API URL (POST endpoint).
- Marketing bookings = only these 3 event_types (filter on them):
  - facebook_paid_ads: https://api.calendly.com/event_types/79652b8a-1688-4d0b-ba8f-733c70856de4
  - youtube_paid_ads:  https://api.calendly.com/event_types/2b5580c2-13e9-4283-8b4d-56401cf31554
  - tiktok_paid_ads:   https://api.calendly.com/event_types/70022cde-e64f-49a0-9362-a815186005dc
- Spend: `https://dea-data-bucket.s3.us-east-1.amazonaws.com/calendly_spend_data/spend_data_YYYY-MM-DD.json`
  (Day-1, published 06:00 AM EST daily, USD); index at `.../calendly_spend_data/file_index.json`.
- Dashboard: **Streamlit**. CI/CD (Continuous Integration / Continuous Delivery): **GitHub** (Actions).
- Architecture + data model need **written SME approval** before building (Step 3 gate).
- Don't propose tools outside the doc unless the user asks.

## Metrics (Step 4/5)
1.1 Daily calls booked by source · 1.2 CPB (Cost Per Booking) = total spend / total booked calls, by channel
· 1.3 Bookings trend (daily/weekly, cumulative) · 1.4 Channel attribution leaderboard (UTM)
· 1.5 Volume by hour / day of week · 1.6 Avg meetings per week per employee = total meetings / weeks.

## Repo layout (grows as we build)
```
docs/00_requirements/   requirements PDF, text copy, architecture diagrams
docs/02_design/         solution design, architecture, data model, design video script
docs/03_deploy/runbook.md  every AWS command in order, with checks (user runs them)
docs/07_walkthrough/    final walkthrough video script
docs/decisions.md       decisions + change log
STATUS.md               where we are now
src/calendly_insights/  PySpark pipeline (bronze, silver, gold, quality, pipeline)
jobs/                   EMR Serverless entry point
lambdas/                webhook, retry_replay, spend_copy Lambda handlers
infra/                  CDK app (calendly_infra/stack.py) + infra/tests
dashboard/              Streamlit app + metrics maths
scripts/                send_test_webhook.py
```

## Conventions
- Work on a branch, commit, open a PR; user reviews and merges. No direct pushes to main.
- User runs every command that creates/changes/deletes AWS resources (deploy/destroy).
- Never commit secrets, .env, Calendly tokens, data/raw/ or lake/.
- Mac M4 (arm64): build Docker images / Lambda packages for the right architecture.

## Plan
Architecture decisions: docs/decisions.md (option A, EMR Serverless, Athena, Step Functions, CDK).
Steps 4-12 create AWS resources: only after written SME approval (Step 2).

| Step | What | Done when | Status |
|------|------|-----------|--------|
| 0 | Project scaffold + requirements walkthrough + decisions | decisions.md filled | done |
| 1 | Repo and skeleton: GitHub repo, src/ tests/ infra/, venv, CI runs tests | PR shows green check | done |
| 2 | Design + SME approval: draw.io diagram, Bronze/Silver/Gold data model, solution design doc | written SME approval in docs/ | done (approved 2026-11-18) |
| 3 | Transformations locally: PySpark + Delta, landing→Bronze→Silver→Gold, 6 metrics | pytest passes; Gold = hand calc | done |
| 4 | AWS foundation (CDK): KMS key, encrypted S3, IAM roles, SNS alert | buckets show SSE-KMS | done (2026-11-19) |
| 5 | Webhook receiver: API Gateway + Lambda (signature) + Secrets Manager + SQS retry queue; URL to SME | POST lands file in landing/ | done (2026-11-19) |
| 6 | Spend ingestion Lambda (copies all files in file_index.json) | 30 files; re-run = no dupes | done (2026-11-19) |
| 7 | Spark job on EMR Serverless on real S3 data | Delta tables in all 3 layers | done (2026-11-19) |
| 8 | Scheduling + failure reload: EventBridge Scheduler → Step Functions, retries, alerts | forced failure alerts; re-run fixes | done (2026-11-19) |
| 9 | Warehouse: Glue Data Catalog + Athena over Gold | Athena returns CPB by channel | done (2026-11-19) |
| 10 | Streamlit dashboard, 6 panels | runs locally on Athena data | done (2026-11-19) |
| 11 | CI/CD complete: tests, lint, cdk synth on every PR | green checks on a real PR | done (2026-11-19) |
| 12 | Submission: README, docs, configs, video, "why" per tool | doc's Step 6 list ticked | done (video recorded 2026-11-23) |
