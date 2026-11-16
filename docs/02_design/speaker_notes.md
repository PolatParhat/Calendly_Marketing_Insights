# Speaker notes: design review with the SME

Goal of the meeting: walk through the architecture and data model, close the open points, and ask
for **written approval** so the build can start.

Length: about 15 minutes of talking, then questions.
Have open: [architecture.png](architecture.png), [data_model.png](data_model.png),
[solution_design.md](solution_design.md).

| # | Part | Show | Time |
|---|------|------|------|
| 1 | Goal and what you confirmed | (nothing, just talk) | 1 min |
| 2 | Architecture, the 5 sections | architecture.png, top row | 5 min |
| 3 | Scheduling, failure reload, security, CI/CD | architecture.png, bottom band | 4 min |
| 4 | Data model | data_model.png | 3 min |
| 5 | Open points and the ask | solution_design.md, sections 12–13 | 2 min |

---

## 1. Goal and what you confirmed (1 min)
> "Thanks for your time. The goal of this pipeline is to answer one question for marketing: **which
> channel brings booked calls at the lowest cost?** It combines every Calendly booking with the daily ad
> spend and shows six metrics in a Streamlit dashboard.
>
> Your answers last time settled the business rules, and I've built them into the design:
> a booking is dated by `created_at`, reports use US Eastern time, the channel comes from the event type,
> campaign is `utm_campaign` or 'Unknown', time slots use the meeting start time, and there's no
> cancellation tracking or backfill. Athena is the warehouse."

## 2. Architecture: the 5 sections (5 min)
Point at the top row, left to right.

> "I followed option A from the requirements, Delta Lake plus Amazon EMR, and kept the same five sections,
> so it maps one-to-one to the diagram you gave us."

**Section 1, Sources** *(point at the two boxes on the left)*
> "Two sources: the Calendly webhook, which fires on every new booking, and the public S3 bucket with the
> daily spend files."

**Section 2, Webhook + ingestion** *(point at API Gateway → Lambda → S3 landing)*
> "Calendly calls our URL, an API Gateway endpoint. A small Lambda checks the Calendly signature, so we
> only accept real Calendly requests, and saves the event **unchanged** in S3. The signing key lives in
> Secrets Manager, not in the code.
>
> If saving fails, the event goes into an SQS retry queue instead of being lost.
>
> For spend, a second Lambda reads `file_index.json` every day and copies every file listed. Each file
> holds the last 30 days, so if one day is missed, the next run fills it in."

**Section 3, Delta Lake + EMR** *(point at EMR Serverless, then Bronze → Silver → Gold)*
> "Once a day, one PySpark job on EMR Serverless builds three layers of Delta tables on S3:
> Bronze is the raw data, Silver is cleaned and filtered to the three marketing channels, and Gold has
> one small table per metric.
>
> Every write is a Delta MERGE, an upsert, so re-running the job never creates duplicates. Serverless
> means there's no cluster running when we're not using it."

**Section 4, Data warehouse** *(point at Glue and Athena)*
> "The Glue Data Catalog holds the table definitions, and Athena runs SQL directly on the Gold tables in
> S3. Nothing is copied."

**Section 5, Visualisation** *(point at the Streamlit box)*
> "The Streamlit dashboard has one panel per metric, 1.1 to 1.6, with date and channel filters. It reads
> Gold through Athena."

## 3. The bottom band: the three must-haves, plus CI/CD (4 min)
> "The requirements ask for scheduling, encryption and failure reload. This band shows how each is covered."

**Scheduling** *(point at EventBridge → Step Functions)*
> "Spend files are published at 6 AM Eastern. At **7 AM Eastern** EventBridge Scheduler starts a Step
> Functions workflow: first it replays anything waiting in the retry queue, then copies the spend files,
> then runs the Spark job. The schedule follows daylight-saving time automatically."

**Failure reload** *(point at SNS and the bullet list)*
> "If any step fails, Step Functions retries it twice, then I get an email alert through SNS. Nothing is
> lost: failed webhook writes wait in the queue, missed spend days fill in the next day, and because
> everything is a MERGE, I can simply re-run the job after fixing the problem. If bad data ever gets in,
> Delta time travel lets me restore the previous version of a table."

**Security and encryption** *(point at KMS and IAM)*
> "All data in S3 is encrypted with our own KMS key, and everything travels over HTTPS only. Each service
> has its own IAM role with only the permissions it needs. The data contains personal information
> (names, emails, phone numbers), so that stays in Bronze and Silver; Gold and the dashboard only show
> totals."

**CI/CD** *(point at GitHub Actions → CDK)*
> "All AWS resources are written as code with AWS CDK in Python. Every pull request on GitHub runs the
> tests and checks that the infrastructure code builds before anything is merged."

## 4. Data model (3 min)
Switch to data_model.png.

> "Left to right is the same Bronze → Silver → Gold flow."

*(point at Bronze)*
> "Bronze keeps the raw data exactly as received, plus the file it came from. Non-marketing events are
> kept here too, but they go no further."

*(point at silver.bookings)*
> "Silver has one row per marketing booking: the webhook JSON flattened into columns. Here are the
> columns from your answers: `booking_date` from `created_at`, `campaign` from `utm_campaign`, and the
> meeting hour and day of week from `start_time`, all in Eastern time."

*(point at silver.booking_hosts and the many : 1 line)*
> "A meeting can have more than one host, so hosts get their own table, one row per host per booking.
> That's what the meeting-load metric counts."

*(point at silver.spend_daily)*
> "Spend files overlap, so Silver keeps one value per day and channel, from the newest file."

*(point at Gold)*
> "Gold has one table per metric, with counts and sums per day. The dashboard computes CPB as **total
> spend divided by total bookings for the selected period**, not as an average of daily CPBs, which would
> give a wrong number."

## 5. Open points and the ask (2 min)
> "Two small points are still open. I sent them by email; I'd like to close them now if possible:
>
> 1. **Meeting load:** I count only meetings from the three marketing event types. Should a meeting
>    count in the week it **takes place** (my proposal) or the week it was **booked**?
> 2. **CPB by channel and campaign heatmap:** spend comes per channel only, so true CPB per campaign
>    can't be calculated. My proposal: the heatmap shows **bookings** per channel and campaign, and CPB
>    stays per channel. The alternative is an estimated CPB per campaign, splitting spend by bookings."

Write their answers down during the meeting.

> "If you're happy with the design, could you confirm your approval in writing, by email or by filling in
> the approval table at the end of the solution design? Once I have it, I'll start building. The first
> thing I'll send you is the webhook URL, so you can create the webhook and share the signing key."

---

## Likely questions and answers

**Why EMR Serverless and not Databricks?**
The requirements say the entire architecture must use AWS resources, and Databricks is a separate
vendor. EMR Serverless runs Spark with no cluster to manage and costs nothing while idle.

**Why doesn't the webhook Lambda write straight into Delta?**
Many bookings can arrive at once. Many Lambdas writing to the same Delta table at the same time would
conflict. Saving raw files first is safe and fast, and the daily Spark job does all the Delta writing.

**How fresh is the dashboard?**
Bookings are saved within seconds, but the dashboard updates after the daily 7 AM run, so it shows data
up to the previous day, matching the spend data, which is also Day-1. If you need fresher booking
numbers, the schedule is one setting: the job can run more often.

**What if Calendly sends the same booking twice?**
Silver uses the booking's unique ID (`payload.uri`) as its key, so a repeated event updates the same row
instead of adding a new one.

**What if our endpoint is down when a booking happens?**
If saving to S3 fails, the event goes to the retry queue and is replayed the next morning. If the whole
endpoint is down, the Lambda returns an error to Calendly, and an alarm emails me. Whether Calendly
re-sends depends on Calendly's own retry behaviour, so the alert matters.

**What if a spend file is restated or arrives late?**
Each run copies every file in the index. For each day and channel, the value from the newest file wins,
so corrections are picked up automatically. Late files are picked up the next day.

**How do you know the numbers are correct?**
Three ways: unit tests that compare Gold results with hand-calculated values on sample data;
data-quality checks inside the job (keys present, spend not negative, no rows lost between layers);
and, with your permission, test bookings on all three channels checked end to end.

**How is personal data protected?**
It's encrypted at rest with our KMS key and in transit with HTTPS. It's only in Bronze and Silver, and
access is limited by IAM roles. Gold and the dashboard show totals only. Bookings from non-marketing
event types never reach Silver.

**What does it cost to run?**
Everything is pay-per-use, with nothing running while idle. The daily job processes kilobytes, so the
main costs are a few minutes of EMR Serverless per day plus small fixed charges for the KMS key and
Secrets Manager.

**What if a fourth channel is added later?**
The event-type-to-channel mapping is a small configuration list in the code. Adding a channel means
adding one line and redeploying; no table changes.

**Why does the run start at 7 AM and not 6 AM?**
The spend file is published at 6 AM Eastern. The extra hour is a safety margin in case it's a bit late.
A file that's later still is picked up the next day.

**Why Athena and not Redshift?**
You confirmed Athena. It queries the Gold tables in place, with no copy to load or keep in sync, and
costs only per query, which suits a small daily dataset.
