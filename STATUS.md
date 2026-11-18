# Status: Calendly Marketing Insights
Updated: 2026-11-18 by /handoff

## Where we are
Steps 0 and 2 done: design docs merged (PR #4, #5), design video recorded, **SME approved the design
on 2026-11-18**. Next: Step 1 (repo skeleton + CI), then Step 3 (local PySpark + Delta). AWS steps
(4-12) are now unblocked; the user runs every deploy/destroy.

## Done this session
- Plan order changed: design (Step 2) before skeleton (Step 1); empty skeleton branch was deleted.
- docs/02_design/ (PR #4, merge 6d355d0): architecture.drawio/.png, data_model.md + data_model.drawio/.png,
  solution_design.md (approval table in section 13), speaker_notes.md (recorded-video script).
- SME answered all 10 first questions + 2 follow-ups; recorded verbatim in docs/01_sme/sme_questions.md;
  decisions logged (PR #5, merge c63bb8c).
- Verified: diagrams rendered via draw.io CLI with no overlaps; all 22 webhook JSON field names used by the
  data model exist in the requirements' sample payload; all doc links resolve.

## Next actions
1. Paste the SME's approval message into docs/01_sme/sme_questions.md "Design approval" (currently "to paste").
2. Step 1 on a new branch, one file per message: src/calendly_insights/__init__.py, tests/, infra/,
   requirements.txt + requirements-dev.txt, first pytest test, .github/workflows/ci.yml. Done = green PR check.
   Local venv already exists: `.venv` on Python 3.11.9 (`~/.pyenv/versions/3.11.9/bin/python -m venv .venv`).

## Open items
- SME approval message text not yet pasted into docs (approval itself received 2026-11-18).
- Webhook URL to the SME after Step 5 deploy; they then send the signing key. Test bookings allowed on all 3 channels.
- User's practice files test.py and webhook_demo.py untracked in project root; do not commit them.

## Environment gotchas
- PDF text extraction: no poppler on this Mac; use a venv with `pypdf`.
- Learning demos live in ~/calendly_learning/ (own .venv with deltalake, pandas, pyarrow); not part of the repo.
- `deltalake` with pandas needs `pyarrow` installed too, or writes fail with "Import pyarrow failed".
- gh CLI is logged in as PolatParhat (https). Repo is PRIVATE.
- draw.io CLI for rendering/exporting diagrams:
  `/Applications/draw.io.app/Contents/MacOS/draw.io -x -f png -s 2 -o out.png file.drawio`.
  In a drawio file, edges listed before a filled container are drawn behind it (hidden).
- pyenv default is 3.13.5; project uses 3.11.9 (PySpark 3.5 / EMR Serverless compatibility).

## Key facts to keep straight
- Each spend_data_<day>.json holds a rolling **30-day window** (90 rows = 30 days x 3 channels); files overlap,
  so MERGE on (date, channel), newest file wins. Files older than ~30 days vanish (HTTP 403).
- Only 3 channels (facebook/youtube/tiktok_paid_ads). Silver = marketing bookings only; non-marketing stays in Bronze.
- SME rules: booking date = created_at; US Eastern; channel from event_type; campaign = utm_campaign else "Unknown";
  time slot (1.5) = meeting start_time; meeting load (1.6) = marketing only, by week of start_time;
  heatmap (1.4) = bookings by channel x campaign, CPB per channel only; no cancellations, no backfill; Athena.
- Webhook failures go to an SQS **retry queue** (not Lambda's DLQ: API Gateway calls Lambda synchronously).
- Speaker notes are ALWAYS for a recorded video; copy WistiaVideoAnalytics/docs/02_design/speaker_notes.md format.
- Keep the README "Build plan" table in sync with CLAUDE.md whenever a step's status changes.
