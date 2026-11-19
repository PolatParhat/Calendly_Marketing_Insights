# Calendly Marketing Insights

An AWS data pipeline that combines Calendly bookings (received by webhook) with daily marketing
spend, stores them in Delta Lake on S3, and shows marketing and meeting metrics in a Streamlit
dashboard. The main metric is Cost Per Booking by channel.

## Docs
- [Requirements](docs/00_requirements/requirements.txt) ([original PDF](docs/00_requirements/Calendly_Marketing_Insights.docx.pdf))
- Architecture options: [A: Delta Lake + EMR](docs/00_requirements/architecture_option_A_emr_delta_lake.jpg) ·
  [B: Databricks](docs/00_requirements/architecture_option_B_databricks.jpg)
- Design (SME-approved 2026-11-18): [solution design](docs/02_design/solution_design.md) ·
  [architecture](docs/02_design/architecture.png) · [data model](docs/02_design/data_model.md) ·
  [SME questions and answers](docs/01_sme/sme_questions.md)
- [Deploy and operate runbook](docs/03_deploy/runbook.md): every AWS command, in order, with its check
- [Final walkthrough video script](docs/07_walkthrough/speaker_notes.md)
- [Decisions and change log](docs/decisions.md)
- [Current status](STATUS.md)

## Architecture (option A, see [decisions](docs/decisions.md))
```
Calendly ─webhook POST─► API Gateway ─► Lambda ─► S3 landing/        (all S3 encrypted with KMS)
Public spend files ─► Lambda (daily copy) ─► S3 landing/
EventBridge Scheduler ─► Step Functions ─► EMR Serverless (PySpark)
      landing ─► Bronze ─► Silver ─► Gold   (Delta Lake on S3)
                                     └─► Glue Catalog + Athena ─► Streamlit dashboard
```

## Build plan
Steps 4-12 create AWS resources (SME approval received 2026-11-18). 🟡 = code written and tested
locally; Polat runs the deploy with [the runbook](docs/03_deploy/runbook.md).

| Step | What | Done when | Status |
|------|------|-----------|--------|
| 0 | Project scaffold, requirements walkthrough, decisions | decisions.md filled | ✅ done |
| 1 | Repo and skeleton: `src/`, `tests/`, `infra/`, venv, CI runs tests | PR shows green check | ✅ done |
| 2 | Design + SME approval: draw.io diagram, Bronze/Silver/Gold data model, solution design doc | written SME approval in `docs/` | ✅ done |
| 3 | Transformations locally: PySpark + Delta, landing → Bronze → Silver → Gold, 6 metrics | pytest passes; Gold matches hand calculation | ✅ done |
| 4 | AWS foundation (CDK): KMS key, encrypted S3, IAM roles, SNS alert | buckets show SSE-KMS | 🟡 code done, deploy pending |
| 5 | Webhook receiver: API Gateway + Lambda (signature check) + Secrets Manager + SQS retry queue | POST lands a file in `landing/` | 🟡 code done, deploy pending |
| 6 | Spend ingestion Lambda (copies all files in `file_index.json`) | 30 files; re-run gives no duplicates | 🟡 code done, deploy pending |
| 7 | Spark job on EMR Serverless on real S3 data | Delta tables in all 3 layers | 🟡 code done, deploy pending |
| 8 | Scheduling + failure reload: EventBridge Scheduler → Step Functions, retries, alerts | forced failure alerts; re-run fixes it | 🟡 code done, deploy pending |
| 9 | Warehouse: Glue Data Catalog + Athena over Gold | Athena returns CPB by channel | 🟡 code done, deploy pending |
| 10 | Streamlit dashboard, 6 panels | runs locally on Athena data | 🟡 runs on local lake; Athena after deploy |
| 11 | CI/CD complete: tests, lint, `cdk synth` on every PR | green checks on a real PR | 🟡 workflow written; green on the PR |
| 12 | Submission: README, docs, configs, video, "why" per tool | requirements' Step 6 list ticked | 🟡 docs + video script done; record video after deploy |

## Metrics
Daily calls booked by source · Cost Per Booking (CPB) by channel · Bookings trend over time ·
Channel attribution leaderboard · Booking volume by time slot / day of week · Meeting load per employee.

## Repo layout
```
src/calendly_insights/   PySpark pipeline: bronze.py, silver.py, gold.py, quality.py, pipeline.py
jobs/run_pipeline.py     entry point EMR Serverless runs (package shipped as calendly_insights.zip)
lambdas/                 webhook.py (receiver), retry_replay.py (SQS replay), spend_copy.py (spend files)
infra/                   AWS CDK app: calendly_infra/stack.py = every AWS resource; infra/tests/
dashboard/               Streamlit app.py, metrics.py (dashboard maths), data_source.py (Athena / local)
scripts/                 send_test_webhook.py (signed test POST to the deployed webhook)
tests/                   pytest: Spark layers vs hand calculation, Lambdas with fake AWS clients, dashboard
docs/                    requirements, SME Q&A, design, runbook, walkthrough video script, decisions
```

## Run it
```bash
source .venv/bin/activate                     # Python 3.11 venv; Spark needs Java 17
pip install -r requirements.txt -r requirements-dev.txt -r dashboard/requirements.txt -r infra/requirements.txt
pytest -q && ruff check .                     # all tests + lint (same as CI)
PYTHONPATH=src python -m calendly_insights.pipeline --landing tests/data/landing --lake lake
DASHBOARD_SOURCE=local LAKE_PATH=lake streamlit run dashboard/app.py
```
On AWS: follow [docs/03_deploy/runbook.md](docs/03_deploy/runbook.md) (`cdk deploy`, checks, forced-failure test, teardown).

## Why each tool
| Tool | Job in this pipeline | Why this one |
|---|---|---|
| **Amazon API Gateway (HTTP API)** | Public HTTPS `POST /webhook` URL for Calendly | Managed HTTPS, throttling and access logs; no server to run |
| **AWS Lambda** (3 functions) | Webhook receiver, spend-file copy, retry-queue replay | Each job takes seconds; pay per call, nothing idles. Too small for Spark |
| **AWS Secrets Manager** | Holds the Calendly webhook signing key | Key never in code, Git or logs; only the webhook Lambda may read it |
| **Amazon SQS** (Simple Queue Service) | Retry queue for webhook events whose S3 write failed | Keeps events 14 days; the daily run replays them, so no booking is lost |
| **Amazon S3** | Landing files + Bronze/Silver/Gold Delta tables + logs | Required by the doc; cheap, durable, encrypted with KMS, HTTPS only |
| **Delta Lake** | Table format of Bronze/Silver/Gold | Required by the doc; ACID writes, `MERGE` for safe re-runs, time travel to undo a bad load |
| **Amazon EMR Serverless (PySpark)** | Daily landing → Bronze → Silver → Gold job + data-quality checks | Architecture option A; Spark without a cluster to manage, no cost while idle |
| **AWS Step Functions** | Daily workflow: replay → spend copy → Spark → register tables; retries; alert on failure | Built-in retries, visual run history, near-zero cost; managed Airflow would run 24/7 |
| **Amazon EventBridge Scheduler** | Starts the workflow at 07:00 US Eastern | Real time-zone support (daylight saving), serverless cron |
| **AWS Glue Data Catalog + Amazon Athena** | Data warehouse: SQL over the Gold Delta tables | SME-approved; no data copy, pay per query, nothing idles (Redshift would) |
| **AWS KMS** (Key Management Service) | One customer-managed key for S3, SQS, the secret, SNS and Athena results | Doc requires encryption; data contains PII (names, emails, phones) |
| **Amazon SNS + CloudWatch alarms** | Email alert on workflow failure, webhook errors, events waiting in the retry queue | Nothing fails silently |
| **IAM roles** | One least-privilege role per Lambda, Spark job, workflow, scheduler | Each part can touch only the folders and actions it needs |
| **AWS CDK (Python)** | All of the above as code (`infra/`) | One command deploys or removes everything; reviewed in pull requests like any code |
| **Streamlit** | Dashboard with the 6 metrics | Required by the doc; pure Python, reads Athena with boto3 |
| **GitHub Actions** | CI: lint, 60+ tests (Spark, Lambdas, dashboard, CDK), `cdk synth` on every PR | Required by the doc; nothing merges unless green |
