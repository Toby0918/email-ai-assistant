---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Local Debug Network Error Task Brief

## 1. Task Name

handle local debug backend unavailable errors

## 2. Task Type

fix

## 3. Current Status

implemented

## 4. Goal

Make the local debug page handle a failed analysis request gracefully.
If the local backend is unavailable or the request fails before JSON is returned, the page should clear stale analysis and show a clear local-service unavailable message.

## 5. Non-goals

- Do not change backend API routes or response schema.
- Do not connect to real mailbox accounts.
- Do not send, delete, archive, or scan emails.
- Do not add dependencies.
- Do not store additional email metadata.

## 6. Background and References

`docs/product/user_flow.md` lists backend unavailable as an exception flow.
The current frontend handles backend JSON errors but does not catch network-level `fetch` failures.

Related files:
- AGENTS.md
- docs/product/user_flow.md
- docs/api/frontend_backend_flow.md
- frontend/local_debug_page/app.js
- tests/test_frontend_local_debug.py

## 7. Scope

Planned changes:
- frontend/local_debug_page/app.js
- tests/test_frontend_local_debug.py
- docs/operations/local_debug_network_error_task_brief.md
- docs/operations/project_status_log.md

## 8. Technical Approach

1. Add a frontend static test requiring a `try/catch` around the analysis request and a local-service unavailable message.
2. Wrap the fetch and JSON parsing path in `try/catch`.
3. On failure, clear stale analysis and set a concise status message.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, archive, or scan emails.
- [x] Does not store or expose OpenAI API keys in the frontend.
- [x] Does not log email body or metadata.
- [x] Uses no new dependencies.

## 11. Prompt Injection Protection

This task does not change prompt construction or email content handling.

## 12. Acceptance Criteria

1. Frontend tests require local backend unavailable handling.
2. Failed fetch or invalid request completion clears stale results.
3. The visible status says the local analysis service is unavailable.
4. Full tests and maintenance scan pass.

## 13. Test Plan

- Run `python -m unittest tests.test_frontend_local_debug`.
- Run `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Revert the frontend error handling change, test addition, regenerated project status log, and this task brief.

## 15. Open Questions

None. This follows the documented first-version exception flow.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Read product user flow exception handling.
- [x] Confirmed no real mailbox or automatic email action is involved.

## 17. Post-execution Record

Actual changed files:
- frontend/local_debug_page/app.js
- tests/test_frontend_local_debug.py
- docs/operations/local_debug_network_error_task_brief.md
- docs/operations/project_status_log.md

Test results:
- `python -m unittest tests.test_frontend_local_debug`: 7 tests passed.
- `python -m unittest discover -s tests`: 91 tests passed.
- `python scripts/maintenance_scan.py`: no findings.
- `python scripts/manage_local_service.py status`: service running at `http://127.0.0.1:8765`.
- `GET /api/health`: returned `ok: true`.

Incomplete items:
- Browser-control network-failure smoke could not be completed because the browser control connection timed out while opening/reloading a local tab. The automated regression test covers the intended frontend branch.

Follow-up suggestions:
- If browser control is stable in a later session, repeat a manual smoke by loading the page, stopping the local service, clicking Analyze, and confirming the unavailable-service message.
