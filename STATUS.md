# Status: Calendly Marketing Insights
Updated: 2026-11-23 by /handoff

## Where we are
**Project complete and torn down (2026-11-23).** All Steps 0-12 done; final video recorded.
All AWS resources removed: stack `CalendlyInsights`, lake bucket, KMS key (PendingDeletion, gone 2026-11-30),
helper log groups, `CDKToolkit` + its staging bucket. Total AWS cost of the pipeline ≈ $0.35 (Cost Explorer).

## Done this session (2026-11-19 → 2026-11-23)
- PRs #15-#19 merged: recording-tab script, speaker notes checked against live AWS and rewritten, dashboard 1.5
  weekday fix (PR #16), handoff.
- Scheduled runs 2026-11-20..23 all SUCCEEDED. Verified go-live → 2026-11-22: CPB tiktok $124.38, youtube $147.30,
  facebook $360.05; dashboard 38 bookings, $6,765.74, $178.05.
- Final video recorded; teardown done by the user (runbook step 9 + CDKToolkit), final sweep of us-west-1 clean.

## Next actions
1. Submit the project (repo link + video).
2. Ask the SME to delete the Calendly webhook subscription (its URL no longer exists).
3. To run it again: `cdk bootstrap` + runbook from step 1 (new webhook URL and signing key needed from the SME).

## Open items
- SME approval message text still "_to paste_" in docs/01_sme/sme_questions.md (approval received 2026-11-18).
- Not from this project, still in us-west-1 (user to decide): Databricks stack `databricks-workspace-stack-ed27b`,
  unattached Elastic IP (~$3.60/month), RDS snapshot `database-1-snapshot`, 2 SQS queues.
- User's practice files test.py and webhook_demo.py untracked in project root; do not commit them.

## Environment gotchas
- AWS CLI user `polat-admin`, region **us-west-1**. Stack outputs: use the `out()` helper in docs/03_deploy/runbook.md.
- `cdk deploy` must always include `-c alert_email=<address>`, or the email subscription is removed.
- Dashboard: `AWS_REGION=us-west-1 streamlit run dashboard/app.py`; first load ~10-20 s (6 Athena queries), cached 10 min.
- `aws stepfunctions list-executions --max-items` prints a trailing "None" token in text output; use `--max-results`.
- Shell profile sets JAVA_HOME to Java 11; `spark.py` forces Java 17 on macOS. Venv `.venv` = Python 3.11.9.
- Ad-hoc scripts need `PYTHONPATH=src`; pytest gets src, lambdas, dashboard, infra, scripts from pyproject.toml.
- Run `cdk` from `infra/` with the venv active. gh CLI logged in as PolatParhat; repo is PRIVATE.
- Streamlit headless screenshots come out blank; use streamlit.testing AppTest for automated checks.

## Key facts to keep straight
- SME rules: booking date = payload.created_at; US Eastern; channel from event_type; campaign = utm_campaign else
  "Unknown"; time slot = meeting start_time; meeting load = marketing only, by week of start_time; heatmap = bookings
  by channel x campaign, CPB per channel only; no cancellations, no backfill; Athena.
- CPB = total spend ÷ total bookings for the period; unknown spend is never 0. Gold has no PII.
- Bookings start 2026-11-19 (webhook go-live); spend goes back 60 days, so full-range CPB is not meaningful yet.
- Speaker notes are ALWAYS for a recorded video; format = docs/02_design/speaker_notes.md.
- Keep the README "Build plan" table in sync with CLAUDE.md whenever a step's status changes.
- CPB for a period = only days whose spend is published (`spend_usd IS NOT NULL`); the latest day has bookings but no spend.
- EMR Serverless console needs an EMR Studio (none exists); list job runs with `aws emr-serverless list-job-runs`.
