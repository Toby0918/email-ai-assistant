---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Docs Status Metadata Task Brief

## 1. Task Name

enforce allowed docs status metadata values

## 2. Task Type

fix

## 3. Current Status

implemented

## 4. Goal

Fix docs metadata drift where task execution states were written into YAML front matter `status`.
Front matter `status` must stay within the documented values `draft`, `active`, and `deprecated`; task execution state belongs in the body.

## 5. Non-goals

- Do not change product scope or first-phase safety boundaries.
- Do not change backend behavior, API shape, database schema, prompts, or AI JSON schema.
- Do not connect to real mailbox accounts.
- Do not send, delete, archive, or scan emails.
- Do not add dependencies.

## 6. Background and References

`docs/operations/documentation_rules.md` defines the only allowed front matter `status` values.
The generated project status log currently reports non-enum status values as `missing_front_matter`, which is misleading during Agent handoff.

Related files:
- AGENTS.md
- docs/operations/project_status_log.md
- docs/operations/documentation_rules.md
- docs/constraints/linter_constraints.md
- scripts/generate_project_status.py
- tests/test_static_linter_constraints.py
- docs/operations/category_reply_draft_task_brief.md
- docs/operations/internal_marketing_category_task_brief.md
- docs/operations/local_service_manager_task_brief.md

## 7. Scope

Planned changes:
- tests/test_static_linter_constraints.py
- docs/operations/category_reply_draft_task_brief.md
- docs/operations/internal_marketing_category_task_brief.md
- docs/operations/local_service_manager_task_brief.md
- docs/operations/docs_status_metadata_task_brief.md
- docs/operations/project_status_log.md

## 8. Technical Approach

1. Add a static linter test that fails when any docs Markdown file uses a front matter status outside `draft`, `active`, or `deprecated`.
2. Update existing task briefs to use a valid document status in front matter.
3. Preserve task execution state in each task brief body.
4. Regenerate the project status log.

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
- [x] Only updates documentation metadata and guardrail tests.

## 11. Prompt Injection Protection

This task does not process email content or prompt text.

## 12. Acceptance Criteria

1. Static linter tests reject non-enum docs front matter status values.
2. Existing docs task briefs use valid front matter status values.
3. Project status log docs metadata summary no longer counts these task briefs as missing front matter.
4. Full tests and maintenance scan pass.

## 13. Test Plan

- Run `python -m unittest tests.test_static_linter_constraints`.
- Run `python -m unittest tests.test_generate_project_status`.
- Run `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Revert the static linter test, task brief metadata changes, regenerated project status log, and this task brief.

## 15. Open Questions

None. This follows the existing documentation rules.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Read docs/operations/documentation_rules.md.
- [x] Confirmed no real mailbox or automatic email action is involved.

## 17. Post-execution Record

Actual changed files:
- tests/test_static_linter_constraints.py
- docs/operations/category_reply_draft_task_brief.md
- docs/operations/internal_marketing_category_task_brief.md
- docs/operations/local_service_manager_task_brief.md
- docs/operations/docs_status_metadata_task_brief.md
- docs/operations/project_status_log.md

Test results:
- `python -m unittest tests.test_static_linter_constraints`: 7 tests passed.
- `python -m unittest tests.test_generate_project_status`: 8 tests passed.
- `python -m unittest discover -s tests`: 89 tests passed.
- `python scripts/maintenance_scan.py`: no findings.

Incomplete items:
- None.

Follow-up suggestions:
- Continue checking first-version local debug UI and persisted-analysis review workflows.
