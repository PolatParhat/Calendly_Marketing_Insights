# Calendly Marketing Insights

An AWS data pipeline that combines Calendly bookings (received by webhook) with daily marketing
spend, stores them in Delta Lake on S3, and shows marketing and meeting metrics in a Streamlit
dashboard. The main metric is Cost Per Booking by channel.

## Docs
- [Requirements](docs/00_requirements/requirements.txt) ([original PDF](docs/00_requirements/Calendly_Marketing_Insights.docx.pdf))
- Architecture options: [A: Delta Lake + EMR](docs/00_requirements/architecture_option_A_emr_delta_lake.jpg) ·
  [B: Databricks](docs/00_requirements/architecture_option_B_databricks.jpg)
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
Steps 4-12 create AWS resources and start only after written SME approval (Step 2).

| Step | What | Done when | Status |
|------|------|-----------|--------|
| 0 | Project scaffold, requirements walkthrough, decisions | decisions.md filled | ✅ done |
| 1 | Repo and skeleton: `src/`, `tests/`, `infra/`, venv, CI runs tests | PR shows green check | ⏭ next |
| 2 | Design + SME approval: draw.io diagram, Bronze/Silver/Gold data model, solution design doc | written SME approval in `docs/` | 🔄 docs done; awaiting SME approval |
| 3 | Transformations locally: PySpark + Delta, landing → Bronze → Silver → Gold, 6 metrics | pytest passes; Gold matches hand calculation | |
| 4 | AWS foundation (CDK): KMS key, encrypted S3, IAM roles, SNS alert | buckets show SSE-KMS | |
| 5 | Webhook receiver: API Gateway + Lambda (signature check) + Secrets Manager + SQS retry queue | POST lands a file in `landing/` | |
| 6 | Spend ingestion Lambda (copies all files in `file_index.json`) | 30 files; re-run gives no duplicates | |
| 7 | Spark job on EMR Serverless on real S3 data | Delta tables in all 3 layers | |
| 8 | Scheduling + failure reload: EventBridge Scheduler → Step Functions, retries, alerts | forced failure alerts; re-run fixes it | |
| 9 | Warehouse: Glue Data Catalog + Athena over Gold | Athena returns CPB by channel | |
| 10 | Streamlit dashboard, 6 panels | runs locally on Athena data | |
| 11 | CI/CD complete: tests, lint, `cdk synth` on every PR | green checks on a real PR | |
| 12 | Submission: README, docs, configs, video, "why" per tool | requirements' Step 6 list ticked | |

## Metrics
Daily calls booked by source · Cost Per Booking (CPB) by channel · Bookings trend over time ·
Channel attribution leaderboard · Booking volume by time slot / day of week · Meeting load per employee.
