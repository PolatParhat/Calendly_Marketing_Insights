# Status: Calendly Marketing Insights
Updated: 2026-11-19

## Where we are
**Deployed and running on AWS (us-west-1). Steps 0-11 done; Step 12 docs done, only the final video is left.**
Daily schedule is live: EventBridge Scheduler starts the workflow every day at 07:00 America/New_York.
Next: record the final walkthrough video with `docs/07_walkthrough/speaker_notes.md`
(fill the [fill: …] numbers on the recording day), then submit.

## Done this session (2026-11-19)
- PR #10: all Steps 4-12 code (CDK stack, 3 Lambdas, quality checks, EMR entry, Streamlit, CI cdk synth, runbook,
  walkthrough script). PRs #11-#13: fixes found on the first real runs (EMR initialExecutors, Delta jar in
  pyFiles, dashboard "spend not published yet").
- Deploy: cdk bootstrap + deploy (stack `CalendlyInsights`); alert email confirmed.
- Webhook: SME created the subscription (organization scope, invitee.created + invitee.canceled); signing key stored
  in Secrets Manager; real deliveries saved; 1 test booking per channel.
- Spend copy: 30 files, re-run copies 0. First successful run 08:52 PT (Bronze 2, Silver 3, Gold 6, 6 Glue tables).
- Athena CPB (all 60 days of spend / 1 booking each): facebook 35942.40, youtube 36270.12, tiktok 23462.13.
- Forced failure: spend URL broken → 2 retries → SendFailureAlert → FAILED (6 min); restored + drift IN_SYNC →
  re-run SUCCEEDED with identical numbers. Full run ~14 min; EMR job ~5 min, ~1 cent per run.

## Next actions
1. Record the final video on/after 2026-11-20 04:15 PT (after the 07:00 ET run brings 11-19 spend):
   `bash scripts/open_recording_tabs.sh` opens all tabs; notes in docs/07_walkthrough/speaker_notes.md.
2. After recording: decide whether to keep the stack running (≈ $2/month) or `cdk destroy` (runbook step 9;
   lake bucket + KMS key are retained and need manual deletion).
3. Optional improvements: register Gold tables in parallel (each Athena DDL takes ~1 min via .sync);
   add a date column to gold.bookings_by_time_slot so metric 1.5 can be filtered by period.

## Open items
- SME approval message text still "_to paste_" in docs/01_sme/sme_questions.md (approval received 2026-11-18).
- Confirm the forced-failure alert email arrived (workflow's SendFailureAlert step succeeded 09:35 PT).
- User's practice files test.py and webhook_demo.py untracked in project root; do not commit them.
- A separate Claude session may be writing the tutorial book in ~/Documents/DataEngineerBootcamp/Books/CalendlyMarketingInsights.

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
