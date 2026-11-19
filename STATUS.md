# Status: Calendly Marketing Insights
Updated: 2026-11-19 by /handoff

## Where we are
Steps 0, 1, 2, 3 done. Step 3 (local transformations) merged as **PR #8 (ca08946)** with green CI (4 min).
The whole pipeline runs locally: landing → Bronze → Silver → Gold, all 6 metrics equal the hand calculation.
**Next: Step 4, AWS foundation with CDK (Cloud Development Kit)**: KMS key, encrypted S3, IAM roles, SNS alert.

## Done this session
- 63e3a4b silver.py: `bookings` (4 rows: marketing only, dedupe latest webhook_created_at per booking_id,
  US Eastern `_et` columns, campaign "Unknown" for null/""/blank, phone from questions_and_answers) and
  `booking_hosts` (5 rows, explode event_memberships). tests/conftest.py sets TZ=UTC.
- 00f6be6 silver.py: `spend_daily` (9 rows, newest file_date wins → facebook 11-02 = 125.50, decimal(12,2)).
- f0176df gold.py: 6 tables (daily_bookings_by_channel, daily_spend_bookings_by_channel, weekly_bookings_by_channel,
  bookings_by_campaign, bookings_by_time_slot, weekly_meetings_by_host); delta_io.merge_into got `delete_missing`;
  pipeline.py run script; test_gold.py.
- bf8d4ea CI installs Java 17 (actions/setup-java@v6, temurin) + requirements.txt; Step 3 marked done in README + CLAUDE.md.
- Verified: `pytest -q` → 32 passed locally and in CI; `ruff check .` clean; pipeline CLI run end to end creates
  2 Bronze, 3 Silver, 6 Gold tables. CPB: facebook 167.75, youtube 240, tiktok 150, all 181.375.

## Next actions
1. Step 4 (one file per message, explain first): set up `infra/` as a CDK Python app (Python version of CDK,
   `cdk init` layout), then a stack with KMS key, S3 buckets (landing / lake) with SSE-KMS + HTTPS only + block
   public access, IAM roles, SNS alert topic. Check: `cdk synth` locally. User runs `cdk bootstrap` / `cdk deploy`.
2. Before Step 4: confirm the user has AWS CLI configured (`aws sts get-caller-identity`) and Node.js for the CDK CLI.
3. Step 11 later: add `cdk synth` to CI.

## Open items
- No open PRs. Branch handoff-2026-11-19b holds this handoff (PR to merge).
- SME approval message text still "_to paste_" in docs/01_sme/sme_questions.md (approval received 2026-11-18).
- Webhook URL to the SME after Step 5 deploy; they then send the signing key. Test bookings allowed on all 3 channels.
- User's practice files test.py and webhook_demo.py untracked in project root; do not commit them.
- Merging PRs from Claude is blocked by the auto-mode permission check: the user merges (`! gh pr merge <n> --merge`).

## Environment gotchas
- Shell profile sets JAVA_HOME to **Java 11**; Spark 4 needs 17. `spark.py` forces Java 17 via
  `/usr/libexec/java_home -v 17` on macOS. Also sets PYSPARK_PYTHON (else worker 3.13 vs driver 3.11 mismatch).
- delta-spark 4.2.0 requires pyspark<=4.1.1, so local pins 4.1.1 (EMR has 4.1.3; same minor).
- Ad-hoc scripts with plain `python` need `PYTHONPATH=src` (pytest gets it from pyproject.toml).
  Run the pipeline: `PYTHONPATH=src python -m calendly_insights.pipeline --landing tests/data/landing --lake lake`.
- `collect()` returns timestamps in the machine's local zone (this Mac = Pacific); tests force TZ=UTC in conftest.py.
- `.text(path, wholetext=True)`: pass wholetext as the argument; `.option("wholetext")` gets overridden (263 rows bug).
- `ruff format` would reformat bronze.py; CI only runs `ruff check`, so formatting is not enforced.
- Venv: `.venv` on Python 3.11.9 (`source .venv/bin/activate`); pyenv default is 3.13.5.
- PDF text extraction: no poppler on this Mac; use a venv with `pypdf`.
- Learning demos live in ~/calendly_learning/ (own .venv); not part of the repo.
- gh CLI is logged in as PolatParhat (https). Repo is PRIVATE.
- draw.io CLI: `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -s 2 -o out.png file.drawio`.
  In a drawio file, edges listed before a filled container are drawn behind it (hidden).

## Key facts to keep straight
- EMR Serverless target: emr-spark-8.2.0 = Spark 4.1.3, Delta 4.2.0, Python 3.11, Java 17. pipeline.py `--cloud`
  makes get_spark use EMR's own Spark/Delta.
- Each spend_data_<day>.json holds a rolling **30-day window**; files overlap, so newest file wins per (date, channel).
  Files older than ~30 days vanish (HTTP 403).
- Only 3 channels (facebook/youtube/tiktok_paid_ads). Silver = marketing bookings only; non-marketing stays in Bronze.
- SME rules: booking date = payload.created_at; US Eastern; channel from event_type; campaign = utm_campaign else
  "Unknown"; time slot (1.5) = meeting start_time; meeting load (1.6) = marketing only, by week (Mon) of start_time;
  heatmap (1.4) = bookings by channel x campaign, CPB per channel only; no cancellations, no backfill; Athena.
- CPB = total spend ÷ total bookings for the period (never an average of daily CPBs). Gold stores sums/counts only;
  missing spend = null (not 0). Gold has no PII.
- Webhook failures go to an SQS **retry queue** (not Lambda's DLQ: API Gateway calls Lambda synchronously).
- Speaker notes are ALWAYS for a recorded video; copy WistiaVideoAnalytics/docs/02_design/speaker_notes.md format.
- Keep the README "Build plan" table in sync with CLAUDE.md whenever a step's status changes.
