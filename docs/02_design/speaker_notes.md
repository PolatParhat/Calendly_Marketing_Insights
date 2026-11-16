# Speaker notes: design walkthrough video for SME approval

Recording length: about **10 minutes**. Read the lines in quotes in your own words; the **[Show]** lines say what is on screen.
Facts below come from `docs/02_design/solution_design.md`, `docs/02_design/data_model.md` and `docs/01_sme/sme_questions.md`.

## Before you record

- Merge the design PR first, so everything is on `main`.
- Open these in browser tabs (GitHub, branch `main`), in this order:
  1. Repo front page (`README.md`)
  2. `docs/01_sme/sme_questions.md` (scroll to the **Answers** table)
  3. `docs/02_design/architecture.png` (open the image, zoom so the whole diagram fills the screen)
  4. `docs/02_design/data_model.png` (same)
  5. `docs/02_design/solution_design.md` (section 7, failure reload)
- **Never show** any `.env` file, AWS console pages with account IDs, or the webhook signing key once you have it.
- Close Slack/email notifications; set browser zoom so text is readable in the recording.
- Practice once with a timer; it is fine to read from these notes.

---

## 1. Introduction (0:00–0:40)

[Show] Tab 1, repo front page.

"Hi, I'm Polat. This video walks through the design for the Calendly Marketing Insights pipeline.

I'll cover the business problem, how your answers shaped the design, the architecture, how the pipeline stays
reliable and secure, the data model, and two small points I'd like you to confirm.

Nothing is built yet, on purpose. I'm asking for your approval before I start."

## 2. The problem (0:40–1:30)

[Show] Tab 1, scroll to the metrics list in the README.

"Marketing runs paid ads on three channels: Facebook, YouTube and TikTok.
People click an ad and book a call in Calendly.

The question this project answers is simple: **which channel gets us booked calls for the least money?**

To answer it, I bring two sources together.
The first is every new booking, which Calendly sends us through a webhook.
The second is the daily ad spend, which is published as JSON files in a public S3 bucket every morning.

From those, the dashboard shows six metrics: daily calls by channel, cost per booking, the booking trend,
channel and campaign attribution, booking volume by hour and weekday, and meeting load per employee."

## 3. Your answers, built into the design (1:30–2:30)

[Show] Tab 2, the Answers table.

"Thank you for answering my questions. Every answer is now part of the design:

- A booking is dated by when the lead made it, `created_at`.
- All reports use US Eastern time.
- The channel comes from the event type, and the campaign from `utm_campaign`, or 'Unknown' when it's empty.
- Time slots use the meeting's start time. That one changed my original assumption, and the data model now follows it.
- No cancellation tracking and no backfill: data starts when the webhook goes live.
- And Athena is the data warehouse.

For meeting load, I've decided to count only meetings from the three marketing channels.
I'll come back to that at the end."

## 4. Architecture: follow one booking (2:30–5:00)

[Show] Tab 3, `architecture.png`. Point at each box as you say it.

"This diagram follows option A from the requirements, Delta Lake plus Amazon EMR,
and keeps the same five sections, so it maps one-to-one to the diagram you gave us.

The easiest way to read it is to follow one booking from left to right."

*(point at Calendly)*
"Someone books a call. Calendly immediately sends a message about it to our web address."

*(point at API Gateway and the webhook Lambda)*
"That address is an API Gateway endpoint. A small Lambda function checks the Calendly signature,
so we only accept messages that really come from Calendly.
The signing key is stored in Secrets Manager, never in the code.
Then the Lambda saves the message in S3, exactly as it arrived."

*(point at the SQS retry queue)*
"If that save ever fails, the message goes into a retry queue instead of being lost."

*(point at Marketing spend and the spend Lambda)*
"The ad spend takes a shorter route. Every morning, a second Lambda reads the file index
and copies every spend file into our S3.
Each file holds the last 30 days, so if one day is ever missed, the next run fills it in."

*(point at EMR Serverless and the Bronze, Silver, Gold boxes)*
"Once a day, one PySpark job on EMR Serverless turns the raw files into three layers of Delta tables:
Bronze, Silver and Gold. I'll show those in the data model.
Serverless means there's no cluster to manage, and nothing running when we're not using it."

*(point at Glue and Athena)*
"The Glue Data Catalog holds the table definitions, and Athena queries the Gold tables with SQL,
directly in S3. Nothing is copied."

*(point at Streamlit)*
"Finally, the Streamlit dashboard shows the six metrics."

## 5. Scheduling, failure reload and security (5:00–7:00)

[Show] Tab 3, bottom band of the diagram.

"The requirements ask for three things: scheduling, a failure reload mechanism, and encryption.
This bottom band shows each one."

*(point at Scheduling)*
"Scheduling. The spend file is published at 6 AM Eastern.
At 7 AM, EventBridge Scheduler starts a Step Functions workflow.
It replays anything waiting in the retry queue, copies the spend files, and runs the Spark job.
The extra hour is a safety margin, and the schedule follows daylight-saving time automatically."

*(point at Failure reload)*
"Failure reload. There are three safety nets.
First, every step retries automatically, and if it still fails, I get an email alert.
Second, nothing is lost: failed bookings wait in the queue, and missed spend days fill in the next day.
Third, every write is a Delta MERGE, which updates existing rows instead of adding new ones.
So after fixing a problem, I simply re-run the job, and nothing is ever counted twice."

[Show] Tab 5, section 7, for a few seconds, then back to Tab 3.

"Section 7 of the solution design lists each failure case and what happens, if you'd like the detail."

*(point at Security)*
"Security. All data is encrypted at rest with our own KMS key, and in transit with HTTPS only.
Each service gets its own IAM role with only the permissions it needs.
The bookings contain personal data, names, emails and phone numbers,
so that stays in the Bronze and Silver layers. Gold and the dashboard only show totals."

*(point at CI/CD)*
"And everything is defined as code with AWS CDK, and tested automatically by GitHub Actions on every pull request."

## 6. Data model (7:00–8:45)

[Show] Tab 4, `data_model.png`.

"The data moves left to right through the same layers."

*(point at Landing and Bronze)*
"Bronze keeps the raw data exactly as it arrived, plus which file it came from.
It's our backup: if anything goes wrong, every layer can be rebuilt from here."

*(point at silver.bookings)*
"Silver has one clean row per marketing booking. Only the three marketing event types get this far.
The webhook message is flattened into proper columns, and duplicates are removed using the booking's unique ID.
This is where your rules live: the booking date, Eastern time, the campaign, and the meeting hour and weekday."

*(point at silver.booking_hosts and the many-to-one line)*
"A meeting can have more than one host, so hosts get their own table, one row per host per booking.
That's what the meeting-load metric counts."

*(point at silver.spend_daily)*
"The spend files overlap, so Silver keeps one value per day and channel, from the newest file."

*(point at Gold)*
"Gold has one small table per metric, with counts and totals per day.

One important point about cost per booking: the dashboard always divides total spend by total bookings
for the period you choose. It never averages daily numbers.
For example: on day one, 100 dollars and 10 bookings is 10 dollars each.
On day two, 100 dollars and 1 booking is 100 dollars.
Averaging those gives 55 dollars, which is wrong. The real cost is 200 dollars for 11 bookings: about 18 dollars."

## 7. Points I need you to confirm (8:45–9:30)

[Show] Tab 3 or Tab 4, whichever you're on.

"There are two small points I'd like you to confirm. I've also sent them by email.

First, meeting load. I count only meetings from the three marketing channels.
Should a meeting count in the week it **takes place**, or the week it was **booked**?
I suggest the week it takes place, because the metric is about meetings employees actually attend.

Second, the 'cost per booking by channel and campaign' heatmap.
The spend files only have spend per channel, not per campaign, so a true cost per campaign can't be calculated.
I suggest the heatmap shows the number of bookings per channel and campaign,
and cost per booking stays at channel level."

## 8. Next steps and close (9:30–10:00)

[Show] Tab 1, README build plan.

"If you approve, I'll build in this order: the repo skeleton and CI first,
then the transformations locally with tests, then the AWS foundation, the webhook receiver, spend ingestion,
the Spark job on EMR, scheduling and alerts, Athena, and finally the dashboard.

The first thing you'll get from me is the webhook URL, so you can create the webhook and share the signing key.

What I need from you: approval of the architecture and data model, and your answer on those two points.
Thank you for watching."

---

## Likely SME questions (prepare, don't read)

| Question | Answer |
|---|---|
| Why EMR Serverless and not Databricks? | The requirements say everything must be on AWS; Databricks is a separate vendor. EMR Serverless runs the same Spark with no cluster to manage and no cost while idle. |
| Why doesn't the webhook Lambda write straight into Delta? | Many bookings can arrive at once, and many Lambdas writing one Delta table at the same time would conflict. Saving raw files is fast and safe; the daily Spark job does all the Delta writes. |
| How up to date is the dashboard? | Up to the previous day, refreshed every morning at 7. That matches the spend data, which is also one day behind. The schedule is one setting if fresher booking numbers are needed. |
| What if Calendly sends the same booking twice? | Silver uses the booking's unique ID (`payload.uri`) as its key, so a repeat updates the same row. |
| What if the endpoint is down when someone books? | If the S3 save fails, the booking goes to the retry queue and is replayed the next morning. If the whole endpoint is down, an alarm emails me straight away. |
| What if a spend number is corrected later? | Every run re-reads all files in the index; for each day and channel, the newest file wins. |
| How do you know the numbers are right? | Unit tests compare Gold with hand-calculated values on sample data; data-quality checks run in every job; and test bookings on all three channels check the flow end to end. |
| How is personal data protected? | Encrypted with our KMS key at rest and HTTPS in transit, least-privilege IAM, PII only in Bronze/Silver, non-marketing bookings never reach Silver, dashboard shows totals only. |
| What does it cost? | Pay-per-use only; nothing runs while idle. The daily job processes kilobytes: a few minutes of EMR Serverless a day plus small fixed charges for KMS and Secrets Manager. |
| Why Athena and not Redshift? | You confirmed Athena. It queries Gold in place, with no copy to load or keep in sync, and costs only per query. |
| What if a fourth channel is added? | The event-type-to-channel mapping is a config list. Adding a channel is one line and a redeploy; no table changes. |
| Why 7 AM and not 6 AM? | The spend file is published at 6 AM Eastern; the hour is a safety margin. A file later than that is picked up the next day. |
