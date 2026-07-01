---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Local Debug Metadata Fields Task Brief

## 1. Task Name

add local debug recipient and time fields

## 2. Task Type

feature

## 3. Current Status

implemented

## 4. Goal

Bring the local debug assistant window in line with the first-phase field flow.
The debug page should let the user provide recipient and sent-time metadata and submit it with the current email analysis request.

## 5. Non-goals

- Do not connect to real mailbox accounts.
- Do not read real mailbox data.
- Do not send, delete, archive, or scan emails.
- Do not change the AI output JSON schema.
- Do not change the SQLite schema or persist additional personal metadata.
- Do not add dependencies.

## 6. Background and References

`AGENTS.md` and `docs/product/feature_scope.md` describe the first-phase current-email fields as subject, sender, recipients, time, and body.
`docs/api/backend_api_contract.md` already includes `to` and `sent_at`, but the local debug page currently submits only subject, from, and body text.

Related files:
- AGENTS.md
- docs/product/feature_scope.md
- docs/product/user_flow.md
- docs/api/backend_api_contract.md
- docs/api/frontend_backend_flow.md
- frontend/local_debug_page/index.html
- frontend/local_debug_page/app.js
- tests/test_frontend_local_debug.py

## 7. Scope

Planned changes:
- frontend/local_debug_page/index.html
- frontend/local_debug_page/app.js
- tests/test_frontend_local_debug.py
- docs/api/frontend_backend_flow.md
- docs/operations/local_debug_metadata_fields_task_brief.md
- docs/operations/project_status_log.md

## 8. Technical Approach

1. Add static frontend tests requiring recipient and sent-time inputs.
2. Add `To` and `Sent At` fields to the local debug form.
3. Submit `to` as a trimmed array split on comma or semicolon, and submit `sent_at` as the entered text.
4. Keep analysis behavior unchanged; metadata is request context only for this first local version.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: aligns local debug request payload with the existing documented `to` and `sent_at` fields.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, archive, or scan emails.
- [x] Does not store or expose OpenAI API keys in the frontend.
- [x] Does not persist recipient or sent-time metadata to SQLite.
- [x] Treats all form input as untrusted email metadata.
- [x] Uses no new dependencies.

## 11. Prompt Injection Protection

Email metadata remains request data and is not treated as system instruction.
This task does not change prompt construction or AI output parsing.

## 12. Acceptance Criteria

1. The local debug page includes `To` and `Sent At` fields.
2. The frontend request body includes `to` and `sent_at` when the user clicks Analyze.
3. The frontend still calls only the local backend API and never calls OpenAI directly.
4. Full tests and maintenance scan pass.

## 13. Test Plan

- Run `python -m unittest tests.test_frontend_local_debug`.
- Run `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Revert the local debug page field additions, frontend test additions, docs update, regenerated project status log, and this task brief.

## 15. Open Questions

None. The task follows the existing documented API payload fields.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Read API and product docs for first-phase field flow.
- [x] Confirmed no real mailbox or automatic email action is involved.

## 17. Post-execution Record

Actual changed files:
- frontend/local_debug_page/index.html
- frontend/local_debug_page/app.js
- tests/test_frontend_local_debug.py
- docs/api/frontend_backend_flow.md
- docs/operations/local_debug_metadata_fields_task_brief.md
- docs/operations/project_status_log.md

Test results:
- `python -m unittest tests.test_frontend_local_debug`: 6 tests passed.
- `python -m unittest discover -s tests`: 90 tests passed.
- `python scripts/maintenance_scan.py`: no findings.
- Browser smoke at `http://127.0.0.1:8765/`: submitted `to` and `sent_at`, received `order_followup` with `delivery_risk`, saved as local record `#48`.

Incomplete items:
- None.

Follow-up suggestions:
- Restart the local debug service before browser smoke testing so the page serves the updated frontend files.
