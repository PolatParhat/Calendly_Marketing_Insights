# Speaker notes: final project walkthrough video for the SME

Recording length: about **14 minutes**. Say the lines in quotes in your own words; the **[Show]** lines say what is on screen.
Numbers in this script were checked on AWS on 2026-11-23, after that morning's scheduled run. Every daily run adds a
day, so **if you record after a newer run, read the numbers off the screen**. The sentences still work; only the
figures change (check that TikTok is still the cheapest before you say it).

## Before you record

1. Log in to the AWS console (region **US West (N. California) / us-west-1**).
2. Start the dashboard and leave it running:
   ```bash
   cd ~/Documents/DataEngineerBootcamp/Projects/Calendly_Marketing_Insights && source .venv/bin/activate && AWS_REGION=us-west-1 streamlit run dashboard/app.py
   ```
3. In a second terminal, open all tabs:
   ```bash
   cd ~/Documents/DataEngineerBootcamp/Projects/Calendly_Marketing_Insights && bash scripts/open_recording_tabs.sh
   ```
4. Keep that second terminal for the EMR job list (the EMR console needs an EMR Studio, which we don't have).
   Run this once, so it is on screen when you reach section 5:
   ```bash
   aws emr-serverless list-job-runs --region us-west-1 --application-id "$(aws cloudformation describe-stacks --stack-name CalendlyInsights --region us-west-1 --query "Stacks[0].Outputs[?OutputKey=='EmrApplicationId'].OutputValue" --output text)" --query 'sort_by(jobRuns,&createdAt)[].[createdAt,state]' --output table
   ```
5. In the Athena tab (workgroup **calendly-insights**), paste and run this. It takes every day from go-live
   (2026-11-19) whose spend is already published, so it is always a complete period:
   ```sql
   SELECT channel,
          SUM(spend_usd)                                        AS spend_usd,
          SUM(bookings)                                         AS bookings,
          ROUND(SUM(spend_usd) / NULLIF(SUM(bookings), 0), 2)  AS cpb_usd
   FROM calendly_gold.daily_spend_bookings_by_channel
   WHERE date >= DATE '2026-11-19' AND spend_usd IS NOT NULL
   GROUP BY channel
   ORDER BY cpb_usd;
   ```
6. In the dashboard, set the **Period** from **2026-11-19 to yesterday** (the last day with spend). Its numbers then
   match the Athena query exactly.
7. Check your inbox for the "Calendly Insights: daily run failed" email from the failure test. If it isn't there
   (check spam), skip it in section 7 and point at the green `SendFailureAlert` step instead.
8. **Never show:** the signing key (never click "Retrieve secret value"), the AWS account number (top-right menu),
   the alert email address, and no personal data: don't open files under `landing/calendly/`, and never
   `SELECT *` from Silver. Gold has no personal data.
9. Turn off notifications, zoom the browser so text is readable, practise once with a timer.

**Tabs** (opened by the script, in this order):
1 README · 2 `architecture.png` · 3 CloudFormation → `CalendlyInsights` → Resources · 4 API Gateway → `WebhookApi` → Routes ·
5 Lambda functions · 6 S3 lake bucket · 7 EventBridge Scheduler · 8 Step Functions → `DailyWorkflow…` · 9 EMR (use the terminal) ·
10 Athena · 11 your email (open it yourself) · 12 dashboard · 13 KMS keys · 14 IAM roles · 15 GitHub Actions ·
16 `src/calendly_insights/` · 17 `docs/decisions.md`

**Numbers on 2026-11-23** (go-live to 2026-11-22):

| channel | spend | bookings | cost per booking |
|---|---|---|---|
| TikTok | $1,741.28 | 14 | **$124.38** |
| YouTube | $2,504.08 | 17 | $147.30 |
| Facebook | $2,520.38 | 7 | $360.05 |
| **Dashboard headline** | **$6,765.74** | **38** | **$178.05** |

---

## 1. Introduction (0:00–0:45)

[Show] Tab 1, README.

"Hi, I'm Polat. This video walks through the finished Calendly Marketing Insights pipeline, live on AWS.

You approved the design on November 18th, and the pipeline went live on November 19th.
Since then it has run by itself every morning.

I'll recap the architecture, show how a booking and a spend file get in, show the daily run,
the numbers in Athena and the dashboard, what happens when something breaks,
and finish with security, testing and why I picked each tool."

## 2. The question and the architecture (0:45–2:15)

[Show] Tab 2, `architecture.png`.

"The question is: **which ad channel gets us booked calls for the least money?**

Two kinds of data come in. Bookings arrive from Calendly the moment someone books. Ad spend arrives once a day
as a file. Both land in our S3 bucket. Every morning a Spark job cleans them and builds three layers of
Delta tables, Bronze, Silver and Gold. Athena queries Gold, and Streamlit shows the six metrics.

This is the design you approved, with one addition: the job ends with data-quality checks,
and if a check fails, the run stops and emails me, so bad numbers never reach the dashboard."

[Show] Tab 3, CloudFormation → Resources.

"Nothing here was clicked together by hand. The whole setup is Python code using AWS CDK.
One command, `cdk deploy`, created everything in this list: the bucket, the encryption key, the Lambda functions,
the queue, the API, the Spark application, the workflow, the schedule, the alarms and the permissions.
And one command, `cdk destroy`, removes it again, except the data bucket and the key, which I keep on purpose."

## 3. How a booking gets in (2:15–3:45)

[Show] Tab 4, API Gateway, the `POST /webhook` route.

"When someone books a call, three things happen.

**One:** Calendly sends the booking to this address. It's the webhook URL I sent you."

[Show] Tab 5, Lambda, click the Webhook function.

"**Two:** this small Lambda function checks the message really comes from Calendly.
Calendly signs every message with a secret key; the key is stored in Secrets Manager, not in the code.
A message with a wrong signature is rejected and nothing is saved."

[Show] Tab 6, S3: `landing/` → `calendly/`. Show the day folders only; don't open a file.

"**Three:** it saves the booking as a file in this folder, one folder per day.

That's it. If saving ever fails, the booking goes to a backup queue instead, I get an email,
and the next daily run saves it. So a booking is never lost."

## 4. How the spend gets in (3:45–4:30)

[Show] Tab 6, S3: `landing/` → `spend/`.

"The ad spend is simpler. Every morning a second Lambda function copies the new spend file into this folder.
The first time it copied all 30 published files; since then it adds one new file a day.
It never copies a file twice, so running it again is always safe."

## 5. The daily run (4:30–6:30)

[Show] Tab 7, EventBridge Scheduler.

"Every day at 7 AM US Eastern, an hour after the spend file is published, this schedule starts the daily run."

[Show] Tab 8, Step Functions. Point at the green runs at the top of the list, then open the newest one.

"The runs at the top are the daily runs, one every morning since go-live, each started by the schedule; nobody pressed a button.
Each run does four steps, in order:
replay anything in the backup queue, copy the spend file, run the Spark job, and register the tables so Athena
can find them. If a step fails, it is retried automatically; if it still fails, I get an email."

[Show] The terminal with the EMR job list.

"The Spark job runs on EMR Serverless. Serverless means there are no servers to look after:
AWS starts the computers for the job and switches them off when it's done. Each run takes about five minutes
and costs about a cent. The green ones are the daily runs. The red ones are from the first day, while I was fixing
two settings; both fixes went in through a pull request with a test."

[Show] Tab 6, S3: open `bronze/`, `silver/`, `gold/`.

"And this is what the job builds: two tables in Bronze, the raw data; three in Silver, cleaned;
and six in Gold, one for each metric."

## 6. The numbers: Athena and the dashboard (6:30–9:30)

[Show] Tab 10, Athena, the query and its result.

"Athena is the data warehouse we agreed on. It runs SQL directly on the Gold tables.
This query takes every day from go-live up to the latest day with published spend,
and for each channel divides the total spend by the total bookings.

TikTok is the cheapest, at about 124 dollars per booked call. YouTube is about 147, and Facebook about 360.
So far, TikTok gets us booked calls for the least money. That's the answer to our question,
and it will get more reliable as more days come in."

[Show] Tab 12, dashboard, period set from 2026-11-19 to yesterday.

"Here's the same in the dashboard. At the top I pick the period and the channels.
For this period: 38 booked calls, about 6,766 dollars of spend, and on average 178 dollars per booking.
The cost per booking by channel matches Athena exactly."

*(scroll through the panels, one sentence each)*

"1.1 is calls booked per day by channel. 1.2 is cost per booking by channel, lower is better.
1.3 is the trend: a running total and weekly totals; faded bars are weeks that aren't complete yet.
1.4 is the leaderboard by UTM campaign. Bookings without a campaign show as 'Unknown', as we agreed,
and cost is shown per channel, because spend only exists per channel.
1.5 shows when meetings happen, by weekday and hour, Eastern time.
And 1.6 is meeting load: marketing meetings per employee per week."

*(set the period to today for a moment)*

"If I pick today, spend says 'not published yet'. Today's spend file only comes out tomorrow morning,
so the dashboard says so, instead of pretending the bookings were free."

*(set the period back, open one "Show data table")*

"And every chart has its data table underneath, so the exact numbers are one click away."

## 7. When something breaks (9:30–11:00)

[Show] Tab 8, Step Functions; scroll down to the newest red run (the top-most red one is the failure test), open it, show the red step.

"The requirements ask for a way to recover from failures, so I broke it on purpose.
I pointed the spend step at a file that doesn't exist. It failed, retried twice, and then the run stopped here."

[Show] Tab 11, the alert email (hide the addresses).

"And I got this email, saying which step failed and why."

[Show] Tab 8, the green run right above it.

"Then I put the setting back and started the run again. It went through, and the numbers were exactly the same
as before. That's because every table is updated with a Delta MERGE: existing rows are updated, not added twice.
So re-running after a failure is always safe."

## 8. Security (11:00–12:00)

[Show] Tab 13, KMS key.

"Everything we store is encrypted with our own KMS key: the bucket, the queue, the secret, the alerts and
the Athena results. The key rotates every year. The bucket only accepts HTTPS and is never public."

[Show] Tab 14, IAM roles.

"Every part has its own role with only the access it needs. For example, the webhook function can write to
the bookings folder and nothing else in the bucket. And personal data, names, emails and phone numbers,
stays in Bronze and Silver. Gold and the dashboard only hold totals."

## 9. Testing and CI/CD (12:00–13:00)

[Show] Tab 15, GitHub Actions.

"Every change went in through a pull request, and GitHub Actions checks each one automatically:
lint, over 60 tests, and a check that the whole AWS setup still builds. The pipeline tests run on sample data
and compare Gold with numbers I calculated by hand. Nothing is merged unless it's green."

[Show] Tab 16, `src/calendly_insights/`.

"The code is split by layer, bronze, silver, gold, plus the quality checks, and the same code runs on my laptop and on AWS."

## 10. Why each tool (13:00–13:40)

[Show] Tab 1, README, **Why each tool**.

"The reasons for each tool are in this table. In short: everything is serverless and pay-per-use,
so it costs about two dollars a month. EMR Serverless and Delta Lake are option A from the requirements.
Step Functions instead of Airflow, because for one run a day Airflow would cost far more.
And Athena, because you chose it and it reads Gold where it is. Every decision is logged in `docs/decisions.md`."

## 11. Close (13:40–14:00)

[Show] Tab 1, README build plan.

"So that's the pipeline: bookings come in live, spend every morning, one Spark job builds the Delta Lake every day,
it checks its own data, emails me when something breaks, re-runs safely, and the dashboard shows all six metrics.
It's running on its daily schedule now. Thank you for watching."

---

## Likely SME questions (prepare, don't read)

| Question | Answer |
|---|---|
| How fresh is the dashboard? | Up to yesterday, refreshed after the 7 AM Eastern run, the same as the spend data. Bookings reach S3 within seconds; running the workflow more often is one schedule setting. |
| A booking is missing. Where do I look? | 1) the file in `landing/calendly/` (did the webhook arrive?); 2) the backup-queue alarm; 3) is it one of the 3 marketing event types? Others stay in Bronze by design; 4) was the daily run green? |
| What if Calendly sends the same booking twice? | Same invitee ID gives the same booking_id; Silver keeps one row (latest delivery wins). Tested. |
| What if the endpoint is down? | S3 failure → backup queue, saved on the next run. If the Lambda itself fails, we return an error, so Calendly doesn't mark the delivery as done; an alarm emails me. |
| Can you recover from a bad load? | Yes: landing files are kept, so every layer can be rebuilt, and Delta time travel can restore a table's previous version. |
| What if a spend figure is corrected later? | Every run re-reads the index; for each day and channel the newest file wins in Silver, and Gold is recalculated. |
| Why does 1.5 ignore the period? | Its Gold table is grouped by weekday and hour only, as in the approved data model. Adding a date column is a small change. |
| Why ignore days without spend in the CPB query? | The latest day has bookings but its spend comes the next morning; counting those bookings would make CPB look too low. |
| How do you know the numbers are right? | Gold equals a hand calculation on sample data (tests), quality checks run every day, and Athena and the dashboard agree. |
| What does it cost? | About 1 cent of EMR per daily run; Lambda and API calls are within the free tier; about $2 a month in total, mostly the KMS key and the secret. |
| How is the signing key changed? | `aws secretsmanager put-secret-value`; the Lambda picks up the new key within 5 minutes, no redeploy. |
| What if a fourth channel is added? | One line in `channels.py` (event type → channel), then deploy. No table changes. |
