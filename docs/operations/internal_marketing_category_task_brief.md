---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Internal and Marketing Category Task Brief

## 1. Task Name

add internal and marketing local category coverage

## 2. Task Type

feature

## 3. Current Status

implemented

## 4. Goal

Add deterministic first-version coverage for `internal` and `marketing` email categories.
These categories already exist in the schema and business documentation, but the local rule analyzer and golden samples do not cover them yet.

## 5. Non-goals

- Do not connect to real mailbox accounts.
- Do not send, delete, archive, or scan emails.
- Do not add dependencies.
- Do not change the API shape, database schema, or AI output JSON schema.
- Do not move API keys or secrets into the frontend.

## 6. Background and References

Project status recommends continuing local evaluation with synthetic samples.
`docs/knowledge_base/email_categories.md` lists `internal` and `marketing`, while the current local rule analyzer defaults unrecognized messages to `customer_inquiry`.

Related files:
- AGENTS.md
- docs/operations/project_status_log.md
- docs/constraints/tooling_constraints.md
- docs/constraints/architecture_constraints.md
- docs/constraints/linter_constraints.md
- docs/knowledge_base/email_categories.md
- docs/knowledge_base/action_rules.md
- backend/email_agent/rule_analyzer.py
- tests/fixtures/sample_emails.json
- tests/test_rule_analyzer.py
- tests/test_golden_email_analysis.py

## 7. Scope

Planned changes:
- backend/email_agent/rule_analyzer.py
- tests/test_rule_analyzer.py
- tests/fixtures/sample_emails.json
- docs/knowledge_base/email_categories.md
- docs/knowledge_base/action_rules.md
- docs/operations/project_status_log.md

## 8. Technical Approach

1. Add failing rule analyzer tests for internal approval and marketing material messages.
2. Add golden samples for the same synthetic scenarios.
3. Implement conservative keyword detection:
   - Internal: internal approval, internal review, approve, 审批, 内部, 复核.
   - Marketing: marketing, promotion, advertisement, exhibition, trade show, 展会, 推广, 广告.
4. Keep marketing action as `ignore`; keep internal action as `reply`.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, archive, or scan emails.
- [x] Does not store or expose OpenAI API keys in the frontend.
- [x] Treats subject and body as untrusted content.
- [x] Keeps output schema-valid JSON.
- [x] Uses only `.test` synthetic sample addresses.

## 11. Prompt Injection Protection

- Email content remains data, not instructions.
- Prompt injection detection remains higher priority than internal or marketing classification.
- The analyzer does not reveal prompts, secrets, hidden configuration, or implementation details.

## 12. Acceptance Criteria

1. Internal approval samples classify as `internal` with `reply` action.
2. Marketing or exhibition material samples classify as `marketing` with `ignore` action.
3. Prompt injection still classifies as `unknown` and escalates.
4. Existing high-risk business categories continue to pass golden tests.
5. Full tests and maintenance scan pass.

## 13. Test Plan

- Run targeted rule analyzer tests.
- Run golden analysis tests.
- Run full `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Revert the analyzer keyword additions, new tests, fixture samples, and documentation changes.

## 15. Open Questions

None. The change stays inside the documented first-version local rule scope.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read relevant constraints and business docs.
- [x] Confirmed no real mailbox, real credentials, or real customer data are involved.
- [x] Confirmed file scope.

## 17. Post-execution Record

Actual changed files:
- backend/email_agent/rule_analyzer.py
- tests/test_rule_analyzer.py
- tests/fixtures/sample_emails.json
- docs/knowledge_base/email_categories.md
- docs/knowledge_base/action_rules.md
- docs/operations/internal_marketing_category_task_brief.md

Test results:
- Targeted rule and golden tests: 15 tests passed.
- Full unittest suite: 87 tests passed.
- Maintenance scan: no findings.

Incomplete items:
- None.

Follow-up suggestions:
- Continue first-version completion by checking local UI workflow coverage and API/database persistence coverage.
