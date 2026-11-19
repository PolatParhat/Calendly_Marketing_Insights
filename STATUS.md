# Status: Calendly Marketing Insights
Updated: 2026-11-19 by /handoff

## Where we are
Steps 0, 1, 2 done (design SME-approved 2026-11-18; Step 1 merged as PR #7 with green CI).
**Step 3 in progress** on branch `step3/local-transformations` (not pushed, no PR yet): Spark+Delta
setup, sample landing data and the Bronze load are done. Next: Silver, then Gold, run script, CI update.

## Done this session
- Step 1 (PR #7, merge 8c6befd): src/calendly_insights/ (channels.py + 4 tests), pyproject.toml (pytest + ruff),
  requirements-dev.txt, .github/workflows/ci.yml (ruff + pytest), infra/README.md placeholder.
- Step 3 commit f4dbf4e: requirements.txt (pyspark 4.1.1, delta-spark 4.2.0), spark.py (get_spark, UTC,
  forces Java 17 on macOS), tests/conftest.py (session `spark` fixture), test_spark.py, sample data
  tests/data/landing/ + expected answers in tests/data/README.md.
- Step 3 commit 8cdde4a: delta_io.py (`merge_into`: first run writes, later runs MERGE with null-safe `<=>`),
  bronze.py (calendly_events_raw = 6 rows, spend_raw = 15 rows; re-run still 6/15), test_bronze.py.
- Verified 2026-11-19: `pytest -q` → 11 passed; `ruff check .` → all checks passed.
- Explained to the user: campaigns/UTM, `<=>`, `isDeltaTable`, the merge chain, `.text(path, wholetext=True)`.

## Next actions
1. Step 3 file 5: `src/calendly_insights/silver.py` for bookings + booking_hosts (marketing only, dedupe on
   booking_id = payload.uri, ET conversion, campaign "Unknown" for null/""), with tests vs tests/data/README.md
   (bookings 4, booking_hosts 5). One file per message; wait for "done".
2. File 6: Silver spend_daily (9 rows; newest file_date wins → facebook 11-02 = 125.50).
3. File 7: Gold, 6 tables, tests = hand calc in tests/data/README.md (e.g. CPB all = 725.50/4 = 181.375).
4. File 8: pipeline run script (landing → Bronze → Silver → Gold). File 9: CI adds `actions/setup-java` 17
   + `pip install -r requirements.txt`. Then push branch, open PR, set Step 3 done in README + CLAUDE.md.

## Open items
- Branch step3/local-transformations: 2 commits + this handoff, not pushed; PR after file 9.
- SME approval message text still "_to paste_" in docs/01_sme/sme_questions.md (approval received 2026-11-18).
- Webhook URL to the SME after Step 5 deploy; they then send the signing key. Test bookings allowed on all 3 channels.
- User's practice files test.py and webhook_demo.py untracked in project root; do not commit them.

## Environment gotchas
- Shell profile sets JAVA_HOME to **Java 11**; Spark 4 needs 17. `spark.py` forces Java 17 via
  `/usr/libexec/java_home -v 17` on macOS. Also sets PYSPARK_PYTHON (else worker 3.13 vs driver 3.11 mismatch).
- delta-spark 4.2.0 requires pyspark<=4.1.1, so local pins 4.1.1 (EMR has 4.1.3; same minor).
- Ad-hoc scripts with plain `python` need `PYTHONPATH=src` (pytest gets it from pyproject.toml).
- `.text(path, wholetext=True)`: pass wholetext as the argument; `.option("wholetext")` gets overridden (263 rows bug).
- Venv: `.venv` on Python 3.11.9 (`source .venv/bin/activate`); pyenv default is 3.13.5.
- PDF text extraction: no poppler on this Mac; use a venv with `pypdf`.
- Learning demos live in ~/calendly_learning/ (own .venv); not part of the repo.
- gh CLI is logged in as PolatParhat (https). Repo is PRIVATE.
- draw.io CLI: `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -s 2 -o out.png file.drawio`.
  In a drawio file, edges listed before a filled container are drawn behind it (hidden).

## Key facts to keep straight
- EMR Serverless target: emr-spark-8.2.0 = Spark 4.1.3, Delta 4.2.0, Python 3.11, Java 17.
- Each spend_data_<day>.json holds a rolling **30-day window**; files overlap, so MERGE on (date, channel),
  newest file wins. Files older than ~30 days vanish (HTTP 403).
- Only 3 channels (facebook/youtube/tiktok_paid_ads). Silver = marketing bookings only; non-marketing stays in Bronze.
- SME rules: booking date = payload.created_at; US Eastern; channel from event_type; campaign = utm_campaign else
  "Unknown"; time slot (1.5) = meeting start_time; meeting load (1.6) = marketing only, by week (Mon) of start_time;
  heatmap (1.4) = bookings by channel x campaign, CPB per channel only; no cancellations, no backfill; Athena.
- CPB = total spend ÷ total bookings for the period (never an average of daily CPBs).
- Webhook failures go to an SQS **retry queue** (not Lambda's DLQ: API Gateway calls Lambda synchronously).
- Speaker notes are ALWAYS for a recorded video; copy WistiaVideoAnalytics/docs/02_design/speaker_notes.md format.
- Keep the README "Build plan" table in sync with CLAUDE.md whenever a step's status changes.
