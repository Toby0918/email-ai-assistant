---
last_update: 2026-07-01
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Category Reply Draft Task Brief

## 1. Task Name

category-specific safe reply drafts

## 2. Task Type

fix

## 3. Current Status

implemented

## 4. Goal

Make first-version rule-based reply drafts more specific to the detected category and suggested action.
The draft must still avoid committing to price, delivery date, payment status, contract acceptance, legal responsibility, or completed actions.

## 5. Non-goals

- Do not connect to real mailbox accounts.
- Do not send, delete, or archive emails.
- Do not add dependencies.
- Do not change the API shape or AI output JSON schema.
- Do not move API keys or secrets into the frontend.

## 6. Background

Manual evaluation showed the analyzer now classifies delivery, payment, contract, complaint, and empty-body cases correctly, but reply drafts still use a generic "confirm the details" template.
This task tightens the draft wording so it matches the selected action while preserving human-review and no-commitment boundaries.

Related files:
- AGENTS.md
- docs/operations/project_status_log.md
- docs/constraints/tooling_constraints.md
- docs/constraints/architecture_constraints.md
- docs/constraints/linter_constraints.md
- docs/knowledge_base/reply_guidelines.md
- backend/email_agent/rule_analyzer.py
- tests/test_rule_analyzer.py

## 7. Scope

Planned changes:
- backend/email_agent/rule_analyzer.py
- tests/test_rule_analyzer.py
- docs/knowledge_base/reply_guidelines.md
- docs/operations/project_status_log.md

## 8. Technical Approach

1. Add tests that assert delivery, payment, contract, quote, and complaint drafts mention the correct safe next step.
2. Pass category and risk context into the local reply draft builder.
3. Generate action-specific conservative wording from the same action selection used for suggested actions.
4. Keep `needs_human_review` true and add no new schema fields.

## 9. Data Structure or Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy Check

- [x] Does not read real mailbox data.
- [x] Does not send, delete, or archive emails.
- [x] Does not store or expose OpenAI API keys in the frontend.
- [x] Treats email subject and body as untrusted content.
- [x] Keeps AI output parseable and schema-valid.
- [x] Does not log real email bodies, customer data, API keys, or tokens.
- [x] Uses synthetic test data only.

## 11. Prompt Injection Protection

- Email content remains data, not instructions.
- Draft wording never reveals system prompts, keys, hidden configuration, or implementation details.
- Prompt injection risks remain escalation cases.
- Draft wording avoids committing to price, delivery, payment, contract, or legal positions.

## 12. Acceptance Criteria

1. Delivery drafts say the team will check delivery or shipment status before confirming timing.
2. Payment drafts say the team will verify invoice, payment, or remittance status before replying.
3. Contract drafts say the team will review terms with the responsible reviewer before replying.
4. Quote drafts say quote details will be prepared for human review before sharing price or lead time.
5. Complaint drafts say the quality issue will be escalated or reviewed by the responsible owner.
6. Existing tests and maintenance scan pass.

## 13. Test Plan

- Run targeted rule analyzer tests.
- Run full `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.

## 14. Rollback Plan

Revert the rule analyzer draft builder, the new tests, and the reply guideline addition.

## 15. Open Questions

None. The user approved executing the previously identified draft-specificity improvement.

## 16. Pre-execution Checklist

- [x] Read AGENTS.md.
- [x] Read project status log.
- [x] Read tooling, architecture, and linter constraints.
- [x] Confirmed the change stays inside first-version boundaries.
- [x] Confirmed file scope.

## 17. Post-execution Record

Actual changed files:
- backend/email_agent/rule_analyzer.py
- tests/test_rule_analyzer.py
- docs/knowledge_base/reply_guidelines.md
- docs/operations/category_reply_draft_task_brief.md

Test results:
- Targeted rule analyzer tests: 10 tests passed.
- Full unittest suite: 79 tests passed.
- Maintenance scan: no findings.

Incomplete items:
- None.

Follow-up suggestions:
- Restart the local debug service before manual browser testing so the backend loads the new draft wording.
