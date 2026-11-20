# Runbook: deploy, check, operate and remove the pipeline on AWS

Every command here creates, changes or reads AWS resources, so **Polat runs them by hand** (CI never deploys).
Run them from the project root unless a step says `cd infra`. Each step ends with a **Check** that matches the
"Done when" column of the build plan.

Words used below:
- **CDK** (Cloud Development Kit): turns `infra/calendly_infra/stack.py` into a CloudFormation template and deploys it.
- **CloudFormation**: the AWS service that creates every resource of a template as one "stack".
- **Stack output**: a value printed after deploy (webhook URL, bucket name, ...); the helper below reads them.

---

## 0. One-time setup on the laptop

```bash
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt -r dashboard/requirements.txt -r infra/requirements.txt
aws sts get-caller-identity --query Arn --output text      # which AWS user you are logged in as
aws configure get region                                     # the region the stack goes to
node --version && cdk --version                              # the cdk command needs Node.js
```

Check: `pytest -q` passes, and `cd infra && cdk synth --quiet` prints no error.

## 1. Bootstrap CDK (once per AWS account + region)

```bash
cd infra
cdk bootstrap
```
Creates the `CDKToolkit` stack: a bucket and roles CDK uses to upload Lambda and job code. Takes ~2 minutes.

## 2. Deploy the whole stack (Steps 4-9)

```bash
cd infra
cdk deploy -c alert_email=<your email address>
```
CDK lists the IAM (Identity and Access Management) changes and asks `Do you wish to deploy these changes (y/n)?`:
answer `y`. Takes ~5-10 minutes. Then **open the email from AWS Notifications and click "Confirm subscription"**,
otherwise no alerts arrive.

Save the outputs in shell variables (run this in every new terminal):
```bash
out() { aws cloudformation describe-stacks --stack-name CalendlyInsights \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
LAKE=$(out LakeBucketName); URL=$(out WebhookUrl); SECRET=$(out SigningKeySecretArn)
SPEND_FN=$(out SpendCopyFunctionName); SM=$(out StateMachineArn)
echo $LAKE $URL
```

**Check (Step 4, buckets show SSE-KMS):**
```bash
aws s3api get-bucket-encryption --bucket $LAKE \
  --query "ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault"
```
Expected: `"SSEAlgorithm": "aws:kms"` and a `KMSMasterKeyID`.

## 3. Webhook (Step 5)

Send one signed test booking (a non-marketing event type, so it stays in Bronze only):
```bash
python scripts/send_test_webhook.py --url $URL --secret-arn $SECRET
python scripts/send_test_webhook.py --url $URL --secret-arn $SECRET --bad-signature
aws s3 ls s3://$LAKE/landing/calendly/ --recursive
```
Expected: `200 {"message": "stored"}`, then `401 {"message": "invalid signature"}`, then one file
`landing/calendly/dt=<today>/test-<id>.json`.

**Hand over to the SME:** send them `$URL` (the POST endpoint). When they create the webhook subscription they send
back the signing key. Store it (the Lambda picks it up within 5 minutes, no redeploy):
```bash
read -s "KEY?Paste the Calendly signing key: " && \
aws secretsmanager put-secret-value --secret-id $SECRET --secret-string "$KEY" && unset KEY
```
(`read -s` keeps the key out of the screen and shell history.)

## 4. Spend copy (Step 6)

```bash
aws lambda invoke --function-name $SPEND_FN /tmp/spend_out.json && cat /tmp/spend_out.json; echo
aws s3 ls s3://$LAKE/landing/spend/ --recursive | wc -l
aws lambda invoke --function-name $SPEND_FN /tmp/spend_out.json && cat /tmp/spend_out.json; echo
```
Expected: first run `"copied": 30`, then `30` files, then the re-run says `"copied": 0, "skipped_already_copied": 30`
(no duplicates).

## 5. Full daily run: Spark on EMR Serverless + Athena tables (Steps 7, 8, 9)

Start the workflow now instead of waiting for 07:00 US Eastern:
```bash
EXEC=$(aws stepfunctions start-execution --state-machine-arn $SM --query executionArn --output text)
aws stepfunctions describe-execution --execution-arn $EXEC --query status --output text
```
Repeat the second command every minute or so. A full run takes **~14 minutes** (measured 2026-11-19): replay + spend
copy 5 s, Spark step ~8 min (the job itself ~5 min, the rest is EMR start-up), registering the 6 Athena tables ~1 min each.
Expected: `SUCCEEDED`. Watch it as a graph in the console: Step Functions → State machines → `DailyWorkflow…`.

**Check (Step 7, Delta tables in all 3 layers):**
```bash
aws s3 ls s3://$LAKE/bronze/ && aws s3 ls s3://$LAKE/silver/ && aws s3 ls s3://$LAKE/gold/
```
Expected: 2 Bronze, 3 Silver, 6 Gold folders, each with a `_delta_log/`.

**Check (Step 9, Athena returns CPB by channel):** Athena console → workgroup `calendly-insights` → run:
```sql
SELECT channel,
       SUM(spend_usd)                                        AS spend_usd,
       SUM(bookings)                                         AS bookings,
       ROUND(SUM(spend_usd) / NULLIF(SUM(bookings), 0), 2)  AS cpb_usd
FROM calendly_gold.daily_spend_bookings_by_channel
GROUP BY channel
ORDER BY cpb_usd;
```
(CPB is empty, shown as "no bookings", for a channel without bookings yet.)

If the run fails, the email alert says which step. Logs:
- Lambda: CloudWatch → Log groups → `CalendlyInsights-…FunctionLogs…`
- Spark: `aws s3 ls s3://$LAKE/emr-logs/ --recursive | grep stderr` (the driver's `stderr.gz` holds the Python error)

## 6. Forced failure and reload (Step 8 "done when")

Break the spend Lambda on purpose by pointing it at a folder that does not exist:
```bash
aws lambda update-function-configuration --function-name $SPEND_FN \
  --environment "Variables={LAKE_BUCKET=$LAKE,SPEND_BASE_URL=https://dea-data-bucket.s3.us-east-1.amazonaws.com/does-not-exist}"
EXEC=$(aws stepfunctions start-execution --state-machine-arn $SM --query executionArn --output text)
```
Expected after ~6 minutes (2 retries with back-off): status `FAILED` and an email
"Calendly Insights: daily run failed" with the error.

Fix it and reload: put the correct setting back (the same value the stack defines), check CloudFormation agrees,
then run again:
```bash
aws lambda update-function-configuration --function-name $SPEND_FN \
  --environment "Variables={LAKE_BUCKET=$LAKE,SPEND_BASE_URL=https://dea-data-bucket.s3.us-east-1.amazonaws.com/calendly_spend_data}"
aws cloudformation detect-stack-drift --stack-name CalendlyInsights
EXEC=$(aws stepfunctions start-execution --state-machine-arn $SM --query executionArn --output text)
```
(`cdk deploy -c alert_email=<your email>` also restores it. Always pass the same `alert_email`: a `cdk deploy`
without it removes the email subscription.)

Expected: `SUCCEEDED`, and the Athena query above returns the same numbers as before (MERGE: no duplicates).
Result 2026-11-19: failure → 2 retries → alert email at +6 min; re-run SUCCEEDED with identical spend and bookings.

## 7. Dashboard (Step 10)

```bash
AWS_REGION=$(aws configure get region) streamlit run dashboard/app.py
```
Opens http://localhost:8501 with the 6 panels on the Athena data. Without AWS (sample data):
```bash
PYTHONPATH=src python -m calendly_insights.pipeline --landing tests/data/landing --lake lake
DASHBOARD_SOURCE=local LAKE_PATH=lake streamlit run dashboard/app.py
```

## 8. Schedule

Nothing to do: EventBridge Scheduler starts the workflow every day at **07:00 America/New_York**.
Check it in the console: EventBridge → Scheduler → Schedules → `CalendlyInsights-DailySchedule…` (state Enabled).

## 9. Remove everything

```bash
cd infra
cdk destroy
```
The **lake bucket and the KMS key are kept on purpose** (booking data cannot be fetched again). To remove them too:
```bash
aws s3 rb s3://$LAKE --force
aws kms schedule-key-deletion --key-id alias/calendly-insights --pending-window-in-days 7
```

## First-deploy problems found and fixed (2026-11-19)
| Symptom | Cause | Fix |
|---|---|---|
| EMR job FAILED before starting: "initialExecutors: 3 must be between … maxExecutors 2" | EMR Serverless starts 3 executors by default; we capped at 2 | `spark.dynamicAllocation.initialExecutors=1` (PR #11) |
| `ModuleNotFoundError: No module named 'delta'` | Delta's Python API is inside the Delta jar, which was not on Python's path | add `/usr/share/aws/delta/lib/delta-spark.jar` to `spark.submit.pyFiles` (PR #12) |
| Dashboard showed $0 spend / $0.00 CPB for today | today's spend file is published tomorrow; nulls were summed as 0 | show "spend not published yet" (PR #13) |

The Delta jar paths (`DELTA_JARS`) and the Athena Delta registration worked on the first try.
Where to look when a run fails: the email names the step; Spark errors are in
`aws emr-serverless list-job-runs --application-id <EmrApplicationId>` (stateDetails) and the driver `stderr.gz` under `emr-logs/`.
