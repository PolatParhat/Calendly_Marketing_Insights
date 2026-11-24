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
| 2026-11-16 | Failed webhook writes go to an **SQS retry queue** that the daily Step Functions run replays first (refines the earlier "SQS DLQ"); data-quality checks in the Spark job stop the run and alert | Lambda's built-in DLQ only covers async calls, and API Gateway calls Lambda synchronously, so the Lambda sends failed events to the queue itself |
| 2026-11-16 | **SME-confirmed**: meeting load (1.6) = marketing event types only, counted per week of meeting `start_time` | SME follow-up reply 2026-11-16 |
| 2026-11-16 | **SME-confirmed**: metric 1.4 heatmap shows bookings by channel × campaign; CPB only at channel level (spend has no campaign) | SME follow-up reply 2026-11-16 |
| 2026-11-18 | Local dev Python = **3.11.9** in `.venv` (not the pyenv default 3.13) | PySpark 3.5 (EMR Serverless 7.x) officially supports Python up to 3.11 |
| 2026-11-18 | **Design approved by the SME** (architecture, data model, solution design) | Step 2 gate passed; AWS build (Steps 4-12) may start |
| 2026-11-19 | Local Spark = **pyspark 4.1.1 + delta-spark 4.2.0** (`requirements.txt`); EMR Serverless target = **emr-spark-8.2.0** (Spark 4.1.3, Delta 4.2.0, Python 3.11, Java 17) | delta-spark 4.2.0 requires pyspark<=4.1.1; same minor Spark/Delta as EMR so local tests match the cloud run (replaces the earlier "PySpark 3.5" assumption) |
| 2026-11-19 | Spark session timezone = **UTC**; conversion to US Eastern done explicitly in code | One clear rule for every timestamp |
| 2026-11-19 | Bronze = insert-only Delta MERGE keyed on the landing **file path** (`source_file`; spend: + date, channel); webhook bodies stored whole as text (`raw_json`) | Each file loaded once; re-runs add nothing; Bronze survives payload shape changes |
| 2026-11-19 | Test data = small fake landing files in `tests/data/landing/` with hand-calculated answers in `tests/data/README.md` | Step 3 "done" = Gold equals the hand calculation |
| 2026-11-19 | Silver dedupe: **latest `webhook_created_at` per booking_id** (tie-break: source_file); spend_daily: **newest `file_date` per (date, channel)**; money = `decimal(12,2)` | Duplicate deliveries collapse; restated spend replaces old value; exact money math |
| 2026-11-19 | Gold = full recalculation from Silver each run, written with MERGE + **`whenNotMatchedBySourceDelete`** (`merge_into(..., delete_missing=True)`) | Gold mirrors Silver exactly (no stale groups) while keeping "MERGE everywhere" |
| 2026-11-19 | Gold 1.2: booking day with no spend file yet keeps **spend_usd = null** (not 0), bookings = 0 when missing | Unknown spend is not free spend |
| 2026-11-19 | `is_partial_week` = week not fully inside [min, max] booking_date | Dashboard labels edge weeks instead of showing fake dips |
| 2026-11-19 | Tests run with process **TZ=UTC** (`tests/conftest.py`) | `collect()` converts timestamps to the machine's local zone; UTC makes results identical on laptop and CI |
| 2026-11-19 | **One CDK stack** (`CalendlyInsights`, `infra/calendly_infra/stack.py`) for Steps 4-9 | One deploy/destroy, no cross-stack references; sections in build order |
| 2026-11-19 | Lake bucket + KMS key **RETAIN** on destroy; artifacts bucket (job code) DESTROY | Booking data cannot be fetched again; code is rebuilt from Git on every deploy |
| 2026-11-19 | Lambdas: **Python 3.11, arm64**, standard library + boto3 only, one `lambdas/` asset | No packaging/Docker step; Graviton is cheaper; same Python as the venv |
| 2026-11-19 | Webhook: signature max age **180 s**; only `invitee.created` stored (others → 200 "ignored"); file = `landing/calendly/dt=<received UTC day>/<invitee id>.json`; signing key cached **5 min** | Calendly's replay-attack advice; same-day duplicate overwrites one file; new key works without redeploy |
| 2026-11-19 | Spend landing key `dt=` = **publish day (file date + 1)**, and files already in S3 are **skipped** | Key depends only on the file name, so re-runs add nothing (Step 6 "no dupes"); matches the test data layout |
| 2026-11-19 | **Data-quality checks** (`quality.py`) end every pipeline run and raise on failure | Design 4.3: bad data stops the run and alerts instead of reaching Gold users |
| 2026-11-19 | Gold tables registered for Athena by the workflow: `CREATE EXTERNAL TABLE IF NOT EXISTS … TBLPROPERTIES ('table_type'='DELTA')` | Athena's native Delta reader; schema comes from the Delta log; safe to repeat daily |
| 2026-11-19 | EMR Serverless app: **ARM64**, auto-stop after 5 min idle, max 8 vCPU / 32 GB; Delta jars from `/usr/share/aws/delta/lib/` | Cheaper Graviton; no idle cost; cost guard. Jar path to confirm on first run (runbook) |
| 2026-11-19 | Workflow: Parallel wrapper with one Catch → SNS email; each step 2 retries with back-off; 2 h timeout + alarm | One alert path for every step |
| 2026-11-19 | Dashboard reads Gold via **Athena (boto3)** or a **local lake (Spark)**; metric 1.5 shows all-to-date (its Gold table has no date) | Local mode lets the dashboard be tested and demoed without AWS |
| 2026-11-19 | CI: second job runs **`cdk synth`** with a placeholder account; test job installs dashboard + infra libs | Step 11: broken infrastructure code fails the PR |
| 2026-11-19 | Deployed to **us-west-1** (the AWS CLI default region) | Spend files are fetched over HTTPS from us-east-1, which works from any region; no reason to move |
| 2026-11-19 | EMR Spark settings: **`spark.dynamicAllocation.initialExecutors=1`** (PR #11) | EMR Serverless starts 3 executors by default, above our cap of 2; job was rejected before starting |
| 2026-11-19 | **Delta jar in `spark.submit.pyFiles`** (PR #12) | Delta's Python API ships inside the EMR Delta jar; without it `No module named 'delta'` |
| 2026-11-19 | Dashboard: unknown spend shown as **"spend not published yet"**, never $0 (PR #13) | Today's spend file comes tomorrow 06:00; summing nulls as 0 showed free bookings |
| 2026-11-19 | Webhook subscription created by the SME with scope organization and events `invitee.created` + `invitee.canceled`; canceled events are acknowledged (200) and not stored | Cancellations out of scope (SME 2026-11-16); 200 stops Calendly retrying them |
| 2026-11-19 | Forced-failure test restores the Lambda setting with `update-function-configuration` + drift check instead of `cdk deploy` | Same result; a `cdk deploy` without `-c alert_email` would remove the email subscription |
| 2026-11-23 | Walkthrough CPB query uses `date >= go-live AND spend_usd IS NOT NULL`; dashboard period go-live → last day with spend | Latest day has bookings but no spend yet; including it makes CPB look too low. Same numbers in Athena and dashboard |
| 2026-11-23 | EMR job runs shown from the CLI (`list-job-runs`) in the video, not the console | The EMR Serverless console needs an EMR Studio; creating one adds a resource outside CDK |

## Change log
- 2026-11-14: Project scaffold created; requirements PDF moved to docs/00_requirements/ with text copy and diagrams.
- 2026-11-16: Requirements walkthrough done (4 parts); architecture and metric decisions recorded; SME question message drafted.
- 2026-11-16: Private GitHub repo created (PolatParhat/Calendly_Marketing_Insights); PR #1 (decisions + plan) and PR #2 (plan + architecture in README) merged; SME questions saved to docs/01_sme/sme_questions.md.
- 2026-11-16: SME answered 9 of 10 questions (time slot changed to meeting start_time); architecture diagram drawn (docs/02_design/architecture.drawio + .png).
- 2026-11-16: Data model, follow-up SME questions and solution design drafted (docs/02_design/).
- 2026-11-16: SME answered both follow-up questions (meeting-load week = start_time; heatmap = bookings, CPB per channel). Design PR #4 merged.
- 2026-11-18: Handoff. Step 2 docs merged; awaiting video + written SME approval. Plan tables updated (Step 2 in progress; Step 5 uses SQS retry queue).
- 2026-11-18: Design video recorded and sent; SME approved the design. Step 2 done.
- 2026-11-19: Step 1 merged (PR #7, green CI). Step 3 started on branch step3/local-transformations: Spark+Delta setup, sample data, Bronze load (11 tests pass).
- 2026-11-19: Step 3 done: Silver (bookings 4, booking_hosts 5, spend_daily 9), Gold 6 tables, pipeline.py run script, CI with Java 17 (32 tests). PR #8 merged (ca08946).
- 2026-11-19: Steps 4-12 code written on branch build/steps-4-12: CDK stack, 3 Lambdas, data-quality checks, EMR entry point, Streamlit dashboard, CI cdk synth, runbook, final walkthrough video script. 64 tests pass locally; nothing deployed yet (user runs docs/03_deploy/runbook.md).
- 2026-11-19: Deployed to AWS (us-west-1). Webhook live (SME created the subscription, signing key stored); spend copy 30 files; first two runs failed (EMR executors, delta import), fixed in PRs #11-#12; run SUCCEEDED (Bronze 2, Silver 3, Gold 6, Athena CPB); dashboard on Athena (PR #13 unknown spend); forced failure alerted and re-run gave identical numbers. Steps 4-11 done.
- 2026-11-20: Dashboard 1.5 fix: weekday names match Silver (`Monday`, not `Mon`), test added (PR #16). First scheduled run 04:00 PT green.
- 2026-11-23: Speaker notes rewritten to match live data (PRs #15-#18): CPB go-live → 2026-11-22 tiktok 124.38, youtube 147.30, facebook 360.05; dashboard 38 bookings, $6,765.74, $178.05. Daily scheduled runs 11-20..11-23 all SUCCEEDED. Final video recorded. **Step 12 done; project complete.**
- 2026-11-23: Teardown: `cdk destroy`, lake bucket deleted, KMS key scheduled for deletion (2026-11-30), helper log groups and CDKToolkit removed. Pipeline cost ≈ $0.35 in total.
