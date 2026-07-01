---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Service Manager Status Inventory Task Brief

## 1. Task Name

report local service manager files in project status

## 2. Task Type

chore

## 3. Current Status

implemented

## 4. Goal

Keep the generated project status log aligned with the current local debug workflow.
The status generator should list the local service manager script, Windows command wrappers, and service manager tests as key handoff files.

## 5. Non-goals

- Do not change the local debug API.
- Do not change analysis behavior, prompts, or JSON schema.
- Do not connect to real mailbox accounts.
- Do not send, delete, archive, or scan emails.
- Do not add dependencies.

## 6. Background and References

The project now has `scripts/manage_local_service.py` plus Windows shortcuts for start, stop, restart, and status.
`scripts/generate_project_status.py` still reports the older local debug entry point but does not list the newer service management files in the key file inventory.

Related files:
- AGENTS.md
- docs/operations/project_status_log.md
- docs/constraints/tooling_constraints.md
- docs/constraints/architecture_constraints.md
- docs/constraints/linter_constraints.md
- scripts/generate_project_status.py
- tests/test_generate_project_status.py
- scripts/manage_local_service.py
- tests/test_manage_local_service.py

## 7. Scope

Planned changes:
- scripts/generate_project_status.py
- tests/test_generate_project_status.py
- docs/operations/project_status_log.md
- docs/operations/service_manager_status_inventory_task_brief.md

## 8. Technical Approach

1. Add a failing generator test that requires the service manager files to appear in the generated report.
2. Extend the status generator `KEY_FILES` list with the local service manager script, command wrappers, and tests.
3. Regenerate `docs/operations/project_status_log.md` after verification.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, archive, or scan emails.
- [x] Does not store or expose OpenAI API keys in the frontend.
- [x] Does not log real email bodies.
- [x] Uses no new dependencies.
- [x] Only updates project handoff metadata and tests.

## 11. Prompt Injection Protection

This task does not process email content or prompt text.

## 12. Acceptance Criteria

1. `build_project_status()` includes `scripts/manage_local_service.py`.
2. `build_project_status()` includes the Windows service command wrappers.
3. `build_project_status()` includes `tests/test_manage_local_service.py`.
4. Targeted status generator tests pass.
5. Full tests and maintenance scan pass.

## 13. Test Plan

- Run `python -m unittest tests.test_generate_project_status`.
- Run `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Revert the generator inventory additions, generator test additions, regenerated project status log, and this task brief.

## 15. Open Questions

None. This is an internal project handoff inventory update.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Confirmed no real mailbox or automatic email action is involved.
- [x] Confirmed no dependencies are added.

## 17. Post-execution Record

Actual changed files:
- scripts/generate_project_status.py
- tests/test_generate_project_status.py
- docs/operations/project_status_log.md
- docs/operations/service_manager_status_inventory_task_brief.md

Test results:
- `python -m unittest tests.test_generate_project_status`: 8 tests passed.
- `python -m unittest discover -s tests`: 88 tests passed.
- `python scripts/maintenance_scan.py`: no findings.

Incomplete items:
- None.

Follow-up suggestions:
- Review docs metadata status reporting next; some older task briefs use non-enum status values in front matter.
