# Solution design: Calendly Marketing Insights

Status: draft for SME approval (2026-11-16) · Author: Polat
Related: [architecture.png](architecture.png) · [data_model.md](data_model.md) · [data_model.png](data_model.png) ·
[SME questions and answers](../01_sme/sme_questions.md) · [decision log](../decisions.md)

## 1. Purpose
Marketing pays for Facebook, YouTube and TikTok ads that lead people to book calls in Calendly.
This pipeline brings together **every booking** (from a Calendly webhook) and **daily ad spend** (from a
public S3 bucket), stores both in a Delta Lake on S3, and shows six metrics in a Streamlit dashboard.
The main question it answers: **which channel brings booked calls at the lowest cost?**

## 2. Scope
**In scope**
- Calendly `invitee.created` webhook events, filtered to the 3 marketing event types.
- Daily spend files (USD, per channel, rolling 30-day window, published 06:00 AM US Eastern for Day-1).
- Metrics 1.1–1.6 and a Streamlit dashboard.
- Scheduling, encryption, failure reload, CI/CD, all on AWS.

**Out of scope** (SME-confirmed 2026-11-16)
- Cancellations and reschedules (`invitee.canceled` is not subscribed).
- Bookings made before the webhook goes live (no backfill).
- Non-marketing Calendly events (kept as raw data in Bronze only).

## 3. How each requirement is met
| Requirement (from the requirements doc) | How this design meets it |
|---|---|
| Entire architecture on AWS | Every component is an AWS service; the only external parts are Calendly (source) and GitHub (code + CI/CD) |
| Follow the Lambda-architecture diagram | Option A: Webhook → Delta Lake + Amazon EMR → Data Warehouse → Visualisation, the same 5 sections |
| Store data in Delta Lake on S3 | Bronze, Silver and Gold are Delta tables in one S3 bucket |
| Webhook with a POST API URL | API Gateway HTTP API `POST /webhook`; the URL is sent to the SME after deployment |
| Filter on the 3 event types | Done in the Bronze → Silver step (see [data_model.md](data_model.md)) |
| Read spend files dynamically via `file_index.json` | Spend Lambda reads the index each day and copies every file listed |
| Scheduling | EventBridge Scheduler → Step Functions, daily at 07:00 US Eastern |
| Encryption | SSE-KMS at rest on all data, HTTPS only in transit, webhook signing key in Secrets Manager |
| Failure reload | Retries, a queue for failed webhook events, self-healing spend copy, idempotent `MERGE` (section 7) |
| Dashboard in Streamlit | Streamlit app reading Gold through Athena |
| CI/CD with GitHub | GitHub Actions on every pull request; infrastructure as code with AWS CDK |

## 4. Architecture, section by section
Two paths feed the lake (the "Lambda architecture" idea):
- **Speed path (real time):** each booking arrives as a webhook within seconds and is saved immediately.
- **Batch path (daily):** spend files are copied and the Spark job rebuilds Bronze → Silver → Gold.

### 4.1 Sources
- **Calendly** sends one HTTPS POST per new booking (`invitee.created`) for the whole organization.
- **Marketing spend**: public S3 JSON files, one per day, each holding the last ≤ 30 days × 3 channels.

### 4.2 Webhook + ingestion
| Component | What it does | Why this choice |
|---|---|---|
| **API Gateway (HTTP API)** | Public HTTPS endpoint `POST /webhook` | Managed HTTPS, throttling and access logs, no server to run |
| **Webhook Lambda** | Checks the Calendly signature (HMAC-SHA256 with the signing key), rejects anything invalid (HTTP 401), writes the body unchanged to `landing/calendly/` | Small and fast, so Calendly gets a quick reply; writes plain files rather than Delta, because many Lambdas writing one Delta table at once would conflict |
| **Secrets Manager** | Stores the webhook signing key | The key never appears in code or GitHub |
| **SQS retry queue** | If the S3 write fails, the Lambda puts the event here instead of losing it | Events wait up to 14 days; the daily workflow replays them (section 7) |
| **Spend Lambda** | Reads `file_index.json` and copies every listed file to `landing/spend/` | The data is a few KB, so Spark is not needed; copying all ~30 files each day fills any missed day automatically |

### 4.3 Delta Lake + Amazon EMR
| Component | What it does | Why this choice |
|---|---|---|
| **S3 + Delta Lake** | Holds `landing/`, `bronze/`, `silver/`, `gold/` in one KMS-encrypted bucket | Required by the doc. Delta adds ACID (all-or-nothing) writes, `MERGE` (upsert) and time travel (read an older version to recover from a bad load) |
| **EMR Serverless (PySpark)** | One daily job: landing → Bronze → Silver → Gold, with data-quality checks | Option A of the doc. Serverless means no cluster to manage and no cost while idle |

Data-quality checks in the job (any failure stops the job and sends an alert):
- required keys present (`booking_id`, `spend_date`, `channel`);
- spend is a number ≥ 0 and the channel is one of the 3 known channels;
- Gold row counts match Silver (no rows lost between layers).

### 4.4 Data warehouse
| Component | What it does | Why this choice |
|---|---|---|
| **Glue Data Catalog** | Holds table definitions for the Gold Delta tables | Lets Athena find the tables by name |
| **Amazon Athena** | Runs SQL directly on the Gold Delta tables in S3 | SME-approved (2026-11-16). No data copy, pay per query, no idle cost |

### 4.5 Visualisation
**Streamlit** dashboard with one panel per metric (1.1–1.6), a date-range filter and a channel filter.
It queries Gold through Athena. It runs locally first; the hosting choice is made in the dashboard step.

## 5. Data model
Full detail in [data_model.md](data_model.md). In short:
- **Bronze**: raw rows plus load metadata (`calendly_events_raw`, `spend_raw`).
- **Silver**: clean marketing bookings (`bookings`, `booking_hosts`) and one spend value per day and
  channel (`spend_daily`).
- **Gold**: one small table per metric, holding counts and sums. The dashboard computes ratios
  (CPB = total spend ÷ total bookings) for the selected period.

Key business rules (SME-confirmed): booking date = `created_at`; reporting time zone = US Eastern;
channel from the event type; campaign = `utm_campaign`, else "Unknown"; time slot = meeting `start_time`.

## 6. Scheduling
| Time (US Eastern) | What happens |
|---|---|
| continuous | Webhook events land in `landing/calendly/` within seconds of each booking |
| 06:00 | Spend file for the previous day is published (by the source) |
| 07:00 | **EventBridge Scheduler** starts the **Step Functions** workflow (1 hour of margin after publication) |
| 07:00 → | 1. replay any events waiting in the SQS retry queue · 2. run the spend Lambda · 3. run the EMR Serverless job · 4. on success, the dashboard shows yesterday's data |

EventBridge Scheduler uses the `America/New_York` time zone, so the run stays at 07:00 across daylight-saving changes.

## 7. Failure reload: what happens when something breaks
| Failure | What the pipeline does | Data lost? |
|---|---|---|
| Webhook Lambda can't write to S3 | Event goes to the SQS retry queue; the next daily run replays it | No |
| Lambda and queue both unavailable | Lambda returns an error to Calendly so the delivery is not marked successful; CloudWatch alarm | Not by our design; depends on Calendly's redelivery |
| Invalid signature (not from Calendly) | Rejected with HTTP 401, nothing stored | n/a (not real data) |
| Spend file late or missing | Next day's run copies all files in the index, so the missing day fills in | No, as long as it's fixed within ~30 days (older files disappear from the source) |
| Any Step Functions step fails | Retried automatically (2 retries with back-off), then an **SNS email alert** | No; fix and re-run |
| Job re-run after a failure, or run twice | Delta `MERGE` on each table's key updates existing rows instead of adding them | No duplicates |
| Bad data loaded | Delta time travel restores the previous table version; landing files are kept, so layers can be rebuilt | No |

## 8. Security and encryption
- **At rest:** one customer-managed **KMS** key encrypts the S3 bucket (SSE-KMS), the SQS queue, the secret,
  and Athena query results.
- **In transit:** HTTPS only; the bucket policy rejects any non-TLS request.
- **Authentication of the webhook:** every request's Calendly signature is checked before anything is stored.
- **Least privilege (IAM):** each Lambda, the EMR job and Step Functions get their own role with only the
  actions and S3 prefixes they need.
- **PII** (invitee name, email, phone) exists only in Bronze and Silver. Gold and the dashboard show
  aggregates only. Non-marketing bookings never reach Silver.
- **Secrets:** no tokens or keys in code or Git; `.env` files are ignored by Git.

## 9. Monitoring and alerts
- Lambda, Step Functions and EMR logs go to **CloudWatch Logs**.
- **SNS email alert** on: workflow failure, data-quality check failure, messages waiting in the SQS
  retry queue, and webhook Lambda errors.

## 10. CI/CD and infrastructure as code
- All AWS resources are defined in **AWS CDK (Python)** under `infra/`, so the whole stack can be created and
  removed with one command each.
- **GitHub Actions** runs on every pull request: unit tests (pytest, including PySpark transformations on
  sample webhook and spend files), linting, and `cdk synth` (checks the infrastructure code builds).
- Changes reach `main` only through reviewed pull requests; deployment (`cdk deploy`) is run by the developer.

## 11. Cost
Everything is serverless and pay-per-use: no cluster, database or server runs while idle. The daily run
processes kilobytes of data, so the expected cost is low (mostly a few minutes of EMR Serverless per day,
plus KMS and Secrets Manager fixed monthly charges).

## 12. Resolved points
SME-confirmed 2026-11-16 (see [sme_questions.md](../01_sme/sme_questions.md), follow-up answers):
1. Meeting load (1.6): only the 3 marketing event types, counted in the week of the meeting `start_time`.
2. "CPB by Channel and Campaign" heatmap: bookings by channel × campaign; CPB at channel level only.

## 13. Approval
| Role | Name | Decision | Date |
|---|---|---|---|
| SME | | ☐ Approved ☐ Approved with changes ☐ Not approved | |

Comments:
