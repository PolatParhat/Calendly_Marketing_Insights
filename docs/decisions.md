# Decisions and change log

## Decisions
| Date | Decision | Reason |
|------|----------|--------|
| 2026-11-16 | **Architecture option A**: Delta Lake + Amazon EMR, run as **EMR Serverless** (not Databricks) | Doc: "entire architecture … using AWS resources"; Databricks is a separate vendor. Serverless = no cluster to manage, no idle cost |
| 2026-11-16 | Webhook receiver = **API Gateway (HTTP API) + AWS Lambda**; Lambda verifies the Calendly signature and writes raw JSON to `s3://…/landing/` | Receiver stays tiny and fast; API Gateway adds throttling and logs; Lambdas don't write Delta directly (concurrent-write conflicts) |
| 2026-11-16 | Spend download = **small Lambda** copying every file in `file_index.json` to S3 raw each day | Data is a few KB, Spark is overkill; re-copying all 30 files fills any missed day (failure reload) |
| 2026-11-16 | Processing = **one PySpark job on EMR Serverless**: landing → Bronze → Silver → Gold, Delta `MERGE` everywhere | Idempotent: re-running a failed job never duplicates data |
| 2026-11-16 | Data warehouse = **Athena + Glue Data Catalog** over Gold Delta tables (SME confirmed 2026-11-16) | No data copy, pay per query, near-zero idle cost; Redshift Serverless costs more at this size |
| 2026-11-16 | Scheduling = **EventBridge Scheduler → Step Functions**, daily ~07:00 US Eastern | Serverless, cheap, built-in retries; MWAA runs 24/7 at hundreds of $/month |
| 2026-11-16 | Encryption: **S3 SSE-KMS** on all buckets, HTTPS only, **Secrets Manager** for the webhook signing key, least-privilege IAM roles | Doc requires encryption; data contains PII (names, emails, phones) |
| 2026-11-16 | Failure handling: Step Functions retries + **SQS dead-letter queue** for failed webhook writes + **SNS email alert** | Nothing lost silently; user is notified |
| 2026-11-16 | Infrastructure as code = **AWS CDK in Python** under `infra/` | Repeatable deploy/destroy |
| 2026-11-16 | CI/CD = **GitHub Actions**: tests + `cdk synth` on every PR; user runs `cdk deploy` | Meets doc's CI/CD requirement; user runs all cloud-changing commands |
| 2026-11-16 | Dashboard: **Streamlit run locally first**, reading Athena; AWS hosting decided in the dashboard step | Hosting not specified by the doc |
| 2026-11-16 | Average CPB tile = **total spend ÷ total bookings** (not the mean of channel CPBs) | True cost per call |
| 2026-11-16 | Week = **Monday–Sunday (ISO)**; partial weeks labelled | Avoids fake dips at period edges |
| 2026-11-16 | Meeting load "number of weeks" = **weeks in the selected period** | Matches the doc's formula literally |
| 2026-11-16 | Duplicate webhook deliveries handled by **MERGE on booking_id** (invitee URI) | Calendly may resend the same event |
| 2026-11-16 | Channel with spend but 0 bookings → CPB shown as **"no bookings"** | Avoid division by zero |
| 2026-11-16 | **SME-confirmed**: booking date = `payload.created_at`; reporting time zone = US Eastern; channel = from the 3 event_types; campaign = `utm_campaign` else "Unknown"; no cancellation tracking (`invitee.created` only); no backfill | SME reply 2026-11-16 (docs/01_sme/sme_questions.md) |
| 2026-11-16 | **SME-confirmed, changed**: metric 1.5 time slot = meeting `scheduled_event.start_time` (US Eastern), not the booking moment | SME reply 2026-11-16 |
| 2026-11-16 | **SME-confirmed**: Athena + Glue Data Catalog over Gold is the data warehouse (no Redshift) | SME reply 2026-11-16 |
| 2026-11-16 | Meeting load (1.6) counts **only the 3 marketing channels**; Silver therefore holds marketing bookings only, non-marketing events stay in Bronze | User decision (SME left it open); also keeps less PII |
| 2026-11-16 | Plan order changed: Step 2 (design + SME approval) before Step 1 (repo skeleton) | User: present the design to the SME before building anything |

## Change log
- 2026-11-14: Project scaffold created; requirements PDF moved to docs/00_requirements/ with text copy and diagrams.
- 2026-11-16: Requirements walkthrough done (4 parts); architecture and metric decisions recorded; SME question message drafted.
- 2026-11-16: Private GitHub repo created (PolatParhat/Calendly_Marketing_Insights); PR #1 (decisions + plan) and PR #2 (plan + architecture in README) merged; SME questions saved to docs/01_sme/sme_questions.md.
- 2026-11-16: SME answered 9 of 10 questions (time slot changed to meeting start_time); architecture diagram drawn (docs/02_design/architecture.drawio + .png).
