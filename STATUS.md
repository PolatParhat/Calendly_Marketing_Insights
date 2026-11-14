# Status: Calendly Marketing Insights
Updated: 2026-11-14 by /new-project

## Where we are
Step 0, project created. Requirements doc moved to docs/00_requirements/ with a text copy and
the two architecture diagrams. Next: walk through the requirements, then agree the step plan.

## Done this session
- Scaffold: CLAUDE.md, STATUS.md, README.md, docs/decisions.md, .gitignore, git init.
- Checked the public spend bucket: file_index.json lists 30 files (spend_data_2026-10-15 … 2026-11-13).

## Next actions
1. Finish the requirements walkthrough (user confirms with "done").
2. Agree the step plan; write it here and into the CLAUDE.md plan table.

## Open items
- Architecture choice: option A (Delta Lake + EMR) or B (Databricks): to decide in Step 3.
- Webhook: need an AWS POST endpoint URL to send to the SME for webhook creation.
- SME written approval of architecture + data model (Step 3 gate).

## Environment gotchas
- PDF text extraction: no poppler on this Mac; use a venv with `pypdf` (already done, see requirements.txt).

## Key facts to keep straight
- Each spend_data_<day>.json holds a rolling **30-day window** (90 rows = 30 days x 3 channels), not
  just one day. Files overlap, so loads must de-duplicate / upsert on (date, channel).
- Files older than ~30 days are removed from the bucket (HTTP 403), so ingest daily or lose history.
- Only 3 channels: facebook_paid_ads, youtube_paid_ads, tiktok_paid_ads.
