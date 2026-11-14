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
docs/decisions.md       decisions + change log
STATUS.md               where we are now
```

## Conventions
- Work on a branch, commit, open a PR; user reviews and merges. No direct pushes to main.
- User runs every command that creates/changes/deletes AWS resources (deploy/destroy).
- Never commit secrets, .env, Calendly tokens, data/raw/ or lake/.
- Mac M4 (arm64): build Docker images / Lambda packages for the right architecture.

## Plan
| Step | What | Status |
|------|------|--------|
| 0 | Project scaffold | done |
| (to be agreed after the requirements walkthrough) | | |
