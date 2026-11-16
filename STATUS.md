# Status: Calendly Marketing Insights
Updated: 2026-11-16

## Where we are
Step 0 done: scaffold, requirements walkthrough (4 parts), architecture + metric decisions recorded,
12-step plan agreed (table in CLAUDE.md). Next: Step 1, repo and skeleton.

## Done this session
- Requirements walkthrough: data sources, architecture, six metrics, gaps (2026-11-14 to 2026-11-16).
- docs/decisions.md: option A (EMR Serverless), API Gateway + Lambda webhook, Athena, Step Functions,
  CDK, GitHub Actions, metric definitions, SME working assumptions (commit 21107f0).
- SME question message drafted (in chat); user to send it.

## Next actions
1. Step 1: create the private GitHub repo, open a PR for branch docs/architecture-decisions, then build
   the skeleton (src/, tests/, infra/, venv, requirements, CI workflow running pytest).
2. Step 2: architecture diagram (draw.io), Bronze/Silver/Gold data model, solution design doc → SME approval.
3. Step 3 (can start while waiting for the SME): local PySpark + Delta transformations with tests.

## Open items
- SME questions sent? Answers pending: webhook signing key, test bookings, booking date, time zone,
  campaign source, time slot meaning, meeting-load scope, cancellations, backfill, Athena vs Redshift.
- Branch docs/architecture-decisions not merged yet (needs the GitHub repo + PR).
- User's practice files test.py and webhook_demo.py are untracked in the project root (not committed).

## Environment gotchas
- PDF text extraction: no poppler on this Mac; use a venv with `pypdf` (already done, see requirements.txt).
- Learning demos live in ~/calendly_learning/ (own .venv with deltalake, pandas, pyarrow); not part of the repo.

## Key facts to keep straight
- Each spend_data_<day>.json holds a rolling **30-day window** (90 rows = 30 days x 3 channels), not
  just one day. Files overlap, so loads must de-duplicate / MERGE on (date, channel).
- Files older than ~30 days are removed from the bucket (HTTP 403), so ingest daily or lose history.
- Only 3 channels: facebook_paid_ads, youtube_paid_ads, tiktok_paid_ads.
- The doc's sample webhook (event_type d639ecd3…, "Info Session") is NOT a marketing booking; it is filtered out.
- Steps 4-12 (AWS resources) only after written SME approval; user runs every deploy/destroy.
