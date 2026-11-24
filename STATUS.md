# Status: Calendly Marketing Insights
Updated: 2026-11-23 by /handoff

## Where we are
**Project complete. All Steps 0-12 done; final walkthrough video recorded 2026-11-23.**
The stack `CalendlyInsights` is still deployed in us-west-1 and runs every day at 07:00 America/New_York
(about $2/month). Whether to keep it or tear it down is the user's decision (see Next actions).

## Done this session (2026-11-19 → 2026-11-23)
- PRs #15-#18 merged (main 5af759c): `scripts/open_recording_tabs.sh`; speaker notes checked line by line
  against live AWS and rewritten (3-step booking flow, short EMR part, no clock times, self-updating CPB query).
- PR #16 bug fix: dashboard 1.5 weekday names (`Monday`, not `Mon`); the time-slot table was empty. Test added.
- Scheduled runs 2026-11-20, -21, -22, -23 all SUCCEEDED (no hand-started runs needed).
- Verified 2026-11-23, go-live → 2026-11-22: CPB tiktok $124.38 (14), youtube $147.30 (17), facebook $360.05 (7);
  dashboard 38 bookings, $6,765.74, $178.05 (matches Athena). 34 spend files; 3 alarms OK; drift IN_SYNC.
- Final video recorded by the user.

## Next actions
1. Submit the project (repo link + video) as the bootcamp asks.
2. Decide: keep the stack running (≈ $2/month, live data keeps coming) or tear it down with runbook step 9
   (`docs/03_deploy/runbook.md`); the lake bucket and KMS key are retained and must be deleted by hand.
3. Optional improvements: add a date column to gold.bookings_by_time_slot (filter 1.5 by period);
   register Gold tables in parallel (each Athena DDL ≈ 1 min).

## Open items
- SME approval message text still "_to paste_" in docs/01_sme/sme_questions.md (approval received 2026-11-18).
- Not confirmed in chat whether the forced-failure alert email reached the inbox.
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
