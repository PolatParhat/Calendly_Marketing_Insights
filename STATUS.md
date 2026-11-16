# Status: Calendly Marketing Insights
Updated: 2026-11-16 by /handoff

## Where we are
Step 0 done: scaffold, requirements walkthrough, architecture + metric decisions, 12-step plan agreed
and merged to main (plan table in CLAUDE.md and README.md). Next: Step 1, repo skeleton. No code yet.

## Done this session
- Private GitHub repo PolatParhat/Calendly_Marketing_Insights created; main pushed (9360d23).
- PR #1 merged (6941fef): docs/decisions.md (option A / EMR Serverless, API Gateway + Lambda webhook,
  spend Lambda, Athena + Glue, EventBridge Scheduler + Step Functions, SSE-KMS, SQS DLQ + SNS, CDK,
  GitHub Actions, metric definitions, SME working assumptions) + plan in CLAUDE.md/STATUS.md.
- PR #2 merged (20011b1): architecture sketch + build plan table + metric list in README.md.
- SME question message saved: docs/01_sme/sme_questions.md (this handoff branch).
- Verified against the public bucket: file_index.json lists 30 files (oldest rolls forward daily);
  each file = 90 rows; appending 2 consecutive files = 180 rows, MERGE on (date, channel) = 93 rows.

## Next actions
1. Merge the handoff PR, then Step 1: on a new branch build the skeleton one file at a time:
   folders src/ tests/ infra/, venv + requirements, a first pytest test, .github/workflows/ci.yml
   running pytest on every PR. Done when the PR shows a green check.
2. User sends the SME message (docs/01_sme/sme_questions.md); record answers in that file.
3. Step 2: draw.io architecture diagram, Bronze/Silver/Gold data model, solution design doc → SME approval.
   Step 3 (local PySpark + Delta) may start while waiting.

## Open items
- Handoff PR (branch handoff-2026-11-16) to merge.
- SME message not yet sent; all 10 answers pending (signing key, test bookings, booking date, time zone,
  campaign source, time slot meaning, meeting-load scope, cancellations, backfill, Athena vs Redshift).
- User's practice files test.py and webhook_demo.py are untracked in the project root; suggested moving
  them to ~/calendly_learning/. Do not commit them.

## Environment gotchas
- PDF text extraction: no poppler on this Mac; use a venv with `pypdf` (already done, see requirements.txt).
- Learning demos live in ~/calendly_learning/ (own .venv with deltalake, pandas, pyarrow); not part of the repo.
- `deltalake` with pandas needs `pyarrow` installed too, or writes fail with "Import pyarrow failed".
- gh CLI is logged in as PolatParhat (https).

## Key facts to keep straight
- Each spend_data_<day>.json holds a rolling **30-day window** (90 rows = 30 days x 3 channels), not
  just one day. Files overlap, so loads must de-duplicate / MERGE on (date, channel).
- Files older than ~30 days are removed from the bucket (HTTP 403), so ingest daily or lose history.
- Only 3 channels: facebook_paid_ads, youtube_paid_ads, tiktok_paid_ads.
- The doc's sample webhook (event_type d639ecd3…, "Info Session") is NOT a marketing booking; it is filtered out.
- Steps 4-12 (AWS resources) only after written SME approval; user runs every deploy/destroy.
- Keep the README "Build plan" table in sync with CLAUDE.md whenever a step's status changes.
