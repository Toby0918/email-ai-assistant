---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# First Version Task Brief

## Task

Build the first local version of the enterprise email AI assistant window.

## Goals

- Provide a local debug assistant window under `frontend/local_debug_page/`.
- Provide local backend endpoints for health check and current-email analysis.
- Generate structured analysis, suggested actions, risk flags, and a reply draft.
- Persist analysis results to local SQLite for debug and review.

## Non-goals

- Do not connect to a real mailbox account.
- Do not read real mailbox data.
- Do not automatically scan multiple emails.
- Do not automatically send, remove, or file emails.
- Do not put backend secrets in frontend files.

## Scope

- Backend: `backend/email_agent/`.
- Frontend: `frontend/local_debug_page/`.
- Scripts: `scripts/run_local_debug.py`.
- Tests: `tests/`.

## Acceptance

- `python -m unittest discover -s tests` passes.
- `python scripts/maintenance_scan.py` reports no cleanup findings.
- Local debug page calls only the local backend API.
- Analysis drafts always require human review.
