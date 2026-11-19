# Status: Calendly Marketing Insights
Updated: 2026-11-19

## Where we are
Steps 0-3 done and merged. **Steps 4-12: all code written and tested locally** on branch `build/steps-4-12`
(PR open, see below). **Nothing is deployed to AWS yet.** Next: merge the PR, then Polat follows
`docs/03_deploy/runbook.md` (bootstrap, deploy, checks, forced failure), then records the final video
(`docs/07_walkthrough/speaker_notes.md`).

## Done this session (branch build/steps-4-12)
- Lambdas (`lambdas/`): webhook.py (Calendly HMAC-SHA256 signature, 180 s max age, S3 landing, SQS retry on failure,
  500 if both fail), retry_replay.py, spend_copy.py (file_index.json, skip already copied, dt = publish day).
- `quality.py` data-quality checks, called at the end of `pipeline.run()`; `jobs/run_pipeline.py` EMR entry point.
- `infra/`: CDK app, one stack `CalendlyInsights` (KMS, 2 S3 buckets, SNS, API Gateway HTTP API, 3 Lambdas, SQS,
  Secrets Manager, EMR Serverless emr-spark-8.2.0 ARM64, Glue db `calendly_gold`, Athena workgroup
  `calendly-insights`, Step Functions `DailyWorkflow`, Scheduler 07:00 America/New_York, 3 alarms). infra/tests.
- `dashboard/`: Streamlit app (6 panels + KPIs), metrics.py, data_source.py (athena | local).
- CI: test job installs dashboard + infra libs; new `cdk-synth` job.
- Docs: runbook, final walkthrough speaker notes, README (layout, run, why each tool), decisions.
- Verified locally: `pytest -q` 64 passed; `ruff check .` clean; `cdk synth` OK; Streamlit AppTest on the local
  lake: no exceptions, KPIs 4 calls / $725.50 / CPB $181.38. Headless-Chrome screenshot came out blank (Streamlit
  needs a live browser), so the visual layout was not checked by Claude.

## Next actions
1. Polat merges the PR once CI is green (`! gh pr merge <n> --merge`).
2. Polat runs `docs/03_deploy/runbook.md` steps 0-7 (cdk bootstrap, cdk deploy -c alert_email=..., checks).
3. Send the webhook URL to the SME; store their signing key (runbook step 3); ask for 1 test booking per channel.
4. Forced failure test (runbook step 6), then fill the [fill: …] numbers in the walkthrough notes and record.
5. Then mark Steps 4-12 done in README + CLAUDE.md tables.

## Open items / risks
- First EMR run confirms the Delta jar path (`DELTA_JARS` in stack.py); fix described in runbook "Known risks".
- Athena Delta registration runs only after the first successful Spark run.
- SME approval message text still "_to paste_" in docs/01_sme/sme_questions.md (approval received 2026-11-18).
- User's practice files test.py and webhook_demo.py untracked in project root; do not commit them.
- Merging PRs from Claude is blocked by the auto-mode permission check: the user merges.

## Environment gotchas
- AWS CLI user `polat-admin`, default region **us-west-1** (stack deploys there unless AWS_REGION is set).
- Shell profile sets JAVA_HOME to **Java 11**; `spark.py` forces Java 17 on macOS. Venv `.venv` = Python 3.11.9.
- delta-spark 4.2.0 requires pyspark<=4.1.1 (EMR has 4.1.3; same minor).
- Ad-hoc scripts need `PYTHONPATH=src`; pytest gets src, lambdas, dashboard, infra, scripts from pyproject.toml.
- Run `cdk` from `infra/` with the venv active (cdk.json runs `python3 app.py`).
- `collect()` returns timestamps in local zone; tests force TZ=UTC in conftest.py.
- `.text(path, wholetext=True)`: pass wholetext as an argument, not `.option`.
- Streamlit: `use_container_width` is deprecated → `width="stretch"`.
- gh CLI logged in as PolatParhat (https). Repo is PRIVATE.

## Key facts to keep straight
- SME rules: booking date = payload.created_at; US Eastern; channel from event_type; campaign = utm_campaign else
  "Unknown"; time slot = meeting start_time; meeting load = marketing only, by week of start_time; heatmap = bookings
  by channel x campaign, CPB per channel only; no cancellations, no backfill; Athena.
- CPB = total spend ÷ total bookings for the period. Gold stores sums/counts only; missing spend = null. Gold has no PII.
- Webhook failures go to an SQS **retry queue**, replayed by the first workflow step.
- Speaker notes are ALWAYS for a recorded video; format = docs/02_design/speaker_notes.md.
- Keep the README "Build plan" table in sync with CLAUDE.md whenever a step's status changes.
