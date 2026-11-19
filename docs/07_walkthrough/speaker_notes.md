# Speaker notes: final project walkthrough video for the SME

Recording length: about **15 minutes**. Read the lines in quotes in your own words; the **[Show]** lines say what is on screen.
Record it **after** the stack is deployed and has run (runbook steps 2-7), and **before** any `cdk destroy`.
Facts come from `README.md`, `docs/02_design/solution_design.md`, `docs/03_deploy/runbook.md` and `docs/decisions.md`.
Numbers marked **[fill: …]** come from your own deployed run; write them in before you record.

## Before you record

- Merge the build PR first, so everything is on `main`, and check the PR's **Actions** checks are green.
- Have done, in this order (runbook): deploy (2), test webhook (3), spend copy twice (4), one successful run (5),
  the forced failure + reload (6), so the history shows all of them. Ask the SME for one test booking per channel
  (facebook, youtube, tiktok) **before** run (5), so the dashboard has real marketing bookings.
- Fill in the **[fill: …]** numbers: Athena CPB query (runbook 5) and the dashboard headline numbers.
- Open these tabs, in this order (GitHub on branch `main`; AWS console in the region you deployed to):
  1. GitHub: repo front page (`README.md`)
  2. GitHub: `docs/02_design/architecture.png` (zoom so the whole diagram fills the screen)
  3. AWS: CloudFormation → Stacks → `CalendlyInsights` → **Resources** tab
  4. AWS: API Gateway → APIs → `WebhookApi` → Routes (shows `POST /webhook`)
  5. AWS: Lambda → Functions (search `CalendlyInsights`: Webhook, SpendCopy, RetryReplay)
  6. AWS: S3 → the `calendlyinsights-lakebucket…` bucket (top level: `landing/ bronze/ silver/ gold/`)
  7. AWS: EventBridge → Scheduler → Schedules → `CalendlyInsights-DailySchedule…`
  8. AWS: Step Functions → State machines → `DailyWorkflow…` → Executions list
  9. AWS: EMR → EMR Serverless → Applications → `calendly-insights` → Job runs
  10. AWS: Athena → Query editor, workgroup **calendly-insights**, the CPB query from runbook step 5 pasted in (run it once)
  11. Your email inbox, filtered to the "Calendly Insights: daily run failed" alert (hide the address bar/sender line)
  12. Streamlit dashboard: `AWS_REGION=<region> streamlit run dashboard/app.py` → http://localhost:8501
  13. AWS: KMS → Customer managed keys → `alias/calendly-insights`
  14. AWS: IAM → Roles, search `CalendlyInsights`
  15. GitHub: Actions tab (the green run of the build PR)
  16. GitHub: `src/calendly_insights/` folder
  17. GitHub: `docs/decisions.md`
- **Never show:** the signing key (never click "Retrieve secret value"), your AWS account number (top-right menu),
  the alert email address, any `.env` file, and no personal data: don't open real booking files under
  `landing/calendly/`, and never `SELECT *` from Silver (names, emails, phones). Gold has no personal data.
- Close Slack/email notifications; set browser zoom so text is readable. Practice once with a timer.

---

## 1. Introduction (0:00–0:45)

[Show] Tab 1, repo front page.

"Hi, I'm Polat. This video walks through the finished Calendly Marketing Insights pipeline, running on AWS.

You approved the design on November 18th. Since then I've built it in the order I showed you:
the transformations first, tested on my laptop, and then each AWS part.

I'll recap the architecture, follow one booking and one spend file through the live system,
show the daily run and the six metrics in the dashboard, show what happens when something breaks,
and finish with security, testing, and the reasons behind each tool."

## 2. The question, and the architecture we agreed (0:45–2:15)

[Show] Tab 2, `architecture.png`.

"The question is still: **which ad channel gets us booked calls for the least money?**

Bookings arrive from Calendly through a webhook. Ad spend arrives as daily files in a public S3 bucket.
Both land in our S3 bucket, a daily Spark job on EMR Serverless builds Bronze, Silver and Gold Delta tables,
Athena queries Gold, and Streamlit shows the six metrics.

This is exactly the design you approved. One small refinement:
the job now ends with data-quality checks, and a failed check stops the run and emails me,
so bad data never reaches the dashboard."

[Show] Tab 3, CloudFormation → Resources.

"None of this was clicked together in the console. It's all Python code with AWS CDK,
and one command, `cdk deploy`, created everything you see in this list:
the encrypted bucket, the KMS key, three Lambda functions, the queue, the secret, the API,
the EMR application, the workflow, the schedule, the alarms and the IAM roles.
One command, `cdk destroy`, removes it again, except the data bucket and the key,
which I keep on purpose, because booking data can't be fetched a second time."

## 3. Follow one booking (2:15–4:15)

[Show] Tab 4, API Gateway, the `POST /webhook` route.

"Let's follow one booking. This is the address I sent you, the POST endpoint your Calendly webhook calls
for every new booking, the `invitee.created` event."

[Show] Tab 5, Lambda list; click the Webhook function, Code tab, scroll to `verify_signature`.

"Behind it is this small Lambda function. The first thing it does is check Calendly's signature.
Calendly signs every message with the key you set up, and the key sits in Secrets Manager, not in the code.
If the signature is wrong, or older than three minutes, the request gets a 401 and nothing is stored.
I tested both cases: a correctly signed test message was stored, and a wrongly signed one was rejected."

[Show] Tab 6, S3: open `landing/` → `calendly/` → a `dt=` folder. Show the file **names** only; don't open a file.

"Then it saves the message, unchanged, in the landing folder, one file per booking,
in a folder for the day it arrived.

If that save ever fails, the Lambda puts the message in an SQS retry queue instead.
The queue keeps it for up to 14 days, an alarm emails me, and the next daily run replays it first.
So a booking is never lost because of a temporary problem."

## 4. Follow one spend file (4:15–5:15)

[Show] Tab 6, S3: `landing/` → `spend/`.

"The spend data takes a different route. A second Lambda reads the file index every morning
and copies every listed file into this folder.

The first time it ran, it copied all 30 files. When I ran it again straight away, it copied zero
and skipped 30, because it only copies what we don't have yet. So running it twice never creates duplicates.

And since each file holds the last 30 days, if one morning is ever missed, the next run fills the gap by itself."

## 5. The daily run (5:15–7:30)

[Show] Tab 7, EventBridge Scheduler.

"Every day at 7 AM US Eastern, one hour after the spend file is published,
EventBridge Scheduler starts the daily workflow. The time zone is New York, so daylight saving is handled."

[Show] Tab 8, Step Functions; open the successful execution and show the green graph.

"This is the workflow in Step Functions, and this is one successful run. The steps run in order:

First, replay anything waiting in the retry queue.
Second, copy the spend files.
Third, run the Spark job on EMR Serverless.
Fourth, register the six Gold tables in the Glue Data Catalog, so Athena can find them.

Every step retries automatically with a growing pause. If it still fails, the whole run goes to this
alert step, which emails me."

[Show] Tab 9, EMR Serverless job runs; point at the successful run and its duration.

"This is the Spark job itself. It took [fill: minutes] minutes. EMR Serverless starts the workers for the job and
stops them five minutes after, so we pay only while it runs.
It's the same PySpark code I tested on my laptop: landing to Bronze, Bronze to Silver, Silver to Gold,
then the data-quality checks."

[Show] Tab 6, S3: open `bronze/`, `silver/`, `gold/` one after the other.

"And here's the result: Delta tables in all three layers. Two in Bronze, three in Silver and six in Gold,
one per metric. Each table has its `_delta_log` folder: that's what makes MERGE and time travel possible."

## 6. The numbers: Athena and the dashboard (7:30–10:30)

[Show] Tab 10, Athena, the CPB query and its result.

"Athena is the data warehouse you chose. It runs SQL straight on the Gold tables in S3; nothing is copied.
This query adds up spend and bookings per channel and divides them.
Facebook: [fill: $ CPB]; YouTube: [fill: $ CPB]; TikTok: [fill: $ CPB].

Remember the rule from the design: cost per booking is always total spend divided by total bookings
for the period, never an average of daily numbers."

[Show] Tab 12, Streamlit dashboard, top of the page.

"Now the dashboard, in Streamlit. At the top: the period and the channels you want to look at.
Below that, three headline numbers: [fill: N] booked calls, [fill: $] ad spend,
and an average cost per booking of [fill: $]."

*(scroll through the panels, one sentence each)*

"1.1: calls booked per day, one colour per channel, and the colour stays the same when you filter.

1.2: cost per booking by channel. Lower is better. A channel that spent money but got no bookings
shows 'no bookings' instead of dividing by zero.

1.3: the trend: a running total for the period, and weekly totals. The faded bars are partial weeks
at the edges of the data, so they don't look like a drop.

1.4: the attribution leaderboard: bookings by channel and UTM campaign. As we agreed,
spend only exists per channel, so cost per booking is shown per channel, not per campaign.

1.5: when meetings take place: weekday against hour, in US Eastern time, using the meeting's start time.

1.6: meeting load: for each employee, marketing meetings divided by the number of weeks in the period."

*(open one "Show data table" expander)*

"Every chart has its data table underneath, so the exact numbers are always one click away."

## 7. When something breaks: failure reload (10:30–12:00)

[Show] Tab 8, Step Functions executions list; open the failed execution, show the red step.

"The requirements ask for a failure reload mechanism, so I tested one on purpose.
I pointed the spend Lambda at a folder that doesn't exist. The run retried twice, then stopped here, in red."

[Show] Tab 11, the alert email (hide the address).

"And this email arrived, saying which step failed and why."

[Show] Tab 8, the next execution, green.

"To fix it, I ran `cdk deploy` again, which puts the correct settings back, and started the run again.
It went through, and the Athena numbers were exactly the same as before.
That's because every table is written with a Delta MERGE: rows that already exist are updated, not added again.
So re-running after a failure is always safe."

## 8. Security (12:00–13:00)

[Show] Tab 13, KMS key (rotation enabled).

"Security. One customer-managed KMS key encrypts everything we store: the bucket, the retry queue,
the secret, the alerts, and the Athena results. The key rotates automatically every year.
The bucket refuses any request that isn't HTTPS, and public access is blocked."

[Show] Tab 14, IAM roles.

"Every part has its own IAM role with only what it needs. The webhook Lambda can read the signing key and write
to one folder, `landing/calendly`, and nothing else. The spend Lambda can only touch `landing/spend`.
The Spark job can read and write the lake but can't read the secret. The scheduler can only start the workflow.

The personal data, names, emails and phone numbers, stays in Bronze and Silver.
Gold and the dashboard only hold totals. Non-marketing bookings never get past Bronze."

## 9. Testing and CI/CD (13:00–14:00)

[Show] Tab 15, GitHub Actions, the green run.

"Every change went in through a pull request, and GitHub Actions checks each one automatically:
lint, and over 60 tests. The Spark tests run the whole pipeline on small sample files and compare Gold with
numbers I calculated by hand. The Lambdas are tested with fake AWS services, so there are no real AWS calls,
and a second job builds the whole CDK stack with `cdk synth`. Nothing is merged unless everything is green."

[Show] Tab 16, `src/calendly_insights/`.

"The code is small and split by layer: bronze, silver, gold, the quality checks, and the pipeline that runs them.
The same code runs on my laptop and on EMR."

## 10. Why each tool (14:00–14:40)

[Show] Tab 1, README, scroll to **Why each tool**.

"The requirements ask for the 'why' behind each tool, and it's in this table.
In short: everything is serverless and pay-per-use, so nothing costs money while it's idle.
EMR Serverless and Delta Lake because they're option A in the requirements.
Step Functions instead of Airflow, because for one run a day managed Airflow would cost far more.
And Athena instead of Redshift, because you chose it, and it queries Gold in place.
Every decision and its reason is also logged in `docs/decisions.md`."

## 11. Next steps and close (14:40–15:00)

[Show] Tab 1, README build plan.

"So that's the whole pipeline: bookings arrive in real time through a signed webhook,
spend files are copied every morning, one Spark job builds the Delta Lake every day at 7,
it checks its own data, alerts me when something breaks, re-runs safely, and the dashboard shows all six metrics.

The pipeline is running on its daily schedule now. All the deploy, check and teardown steps are in the runbook.

Thank you for watching."

---

## Likely SME questions (prepare, don't read)

| Question | Answer |
|---|---|
| How fresh is the dashboard? | Up to the previous day, refreshed after the 7 AM Eastern run, same as the spend data. Bookings land in S3 within seconds; running the workflow more often is one schedule setting. |
| A booking is missing from the dashboard. Where do I look? | 1) `landing/calendly/` for the file (did the webhook arrive?); 2) the retry queue alarm; 3) is its event type one of the 3 marketing ones? Others stay in Bronze by design; 4) was the daily run green? |
| What if Calendly sends the same booking twice? | Same invitee ID → same booking_id; Silver keeps one row (latest delivery wins). Tested. |
| What if the endpoint is down? | S3 failure → retry queue, replayed next run. Lambda and queue both down → we return an error, so Calendly doesn't mark the delivery as done; the error alarm emails me. |
| Can you recover from a bad load? | Yes: landing files are kept, so every layer can be rebuilt; and Delta time travel can restore a table's previous version. |
| What if a spend figure is corrected later? | Every run re-reads the index; for each day and channel the newest file wins in Silver, and Gold is recalculated. |
| Why is 1.5 (time slot) not filtered by the date range? | Its Gold table is grouped by weekday and hour only, as in the approved data model. Adding a date column is a small change if you want the filter. |
| How do you know the numbers are right? | Gold equals a hand calculation on sample data (tests), data-quality checks on every run (no rows lost Silver → Gold, no negative spend, known channels only), and your test bookings end to end. |
| What does it cost? | Pay per use. A few minutes of EMR Serverless per day, Lambda and API calls in the free-tier range, plus small fixed monthly charges for the KMS key and the secret. [fill: cost from Billing → Cost Explorer after a few days] |
| How is the signing key changed? | `aws secretsmanager put-secret-value`; the Lambda picks up the new key within 5 minutes, no redeploy. |
| Where does the dashboard run? | Locally against Athena today, as agreed in the design; hosting on AWS is a separate decision. |
| What if a fourth channel is added? | One line in `channels.py` (event type → channel), then deploy. No table changes. |
