---
last_update: 2026-07-03
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# New Product Classification and Attachment Metadata Task Brief

## 1. Task Name

new product classification and attachment metadata preview

## 2. Task Type

feature | fix | data_schema | api_contract | prompt

## 3. Current Status

completed

## 4. Goal

Fix the current-email analysis so product development and cost-optimization project emails are not treated as quality complaints. Add a first safe attachment preview path that extracts attachment metadata from the currently opened Tencent Exmail message and sends that metadata to the backend for combined analysis.

## 5. Non-goals

- Do not download, open, parse, or upload attachment file contents.
- Do not connect to a real mailbox account outside the current opened page.
- Do not auto-send, delete, archive, move, forward, or reply to emails.
- Do not store OpenAI, Ollama, Qwen, mailbox credentials, or local model settings in frontend code.
- Do not add new dependencies.

## 6. Background

The user reported that a "Bottle trap Cost optimisation project-Delifu" email is a new product development request, not a quality complaint. The email also includes an attached PDF project scope document, so attachment metadata should be visible in the assistant and included in backend analysis context.

Related documents:

- `AGENTS.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/data/analysis_result_schema.md`
- `docs/api/backend_api_contract.md`
- `docs/prompts/analyzer_prompt.md`

## 7. Scope

Expected changes:

- `backend/email_agent/analysis_schema.py`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/rule_analyzer.py`
- `backend/email_agent/rule_draft.py`
- `frontend/browser_extension/content/exmail_adapter.js`
- `frontend/browser_extension/shared/api_client.js`
- `frontend/browser_extension/shared/render_analysis.js`
- `frontend/browser_extension/popup.html`
- `frontend/local_debug_page/*`
- `docs/data/analysis_result_schema.md`
- `docs/api/backend_api_contract.md`
- `docs/prompts/analyzer_prompt.md`
- `docs/operations/*`
- `tests/*`

## 8. Technical Plan

1. Add a `new_product_development` category and Chinese UI label.
2. Add rule-based detection for new product, cost optimization, project scope, feasibility, prototype, and target-cost requests.
3. Make quality complaint detection more precise so "quality standards" in a development request does not become a complaint by itself.
4. Normalize attachment metadata as untrusted text in the backend prompt and rule fallback.
5. Extract and preview attachment metadata in the Tencent Exmail extension without downloading or opening attachment content.
6. Send attachment metadata in the existing user-clicked analyze request.

## 9. Data and API Changes

Database changes: none.

API changes: add optional `attachments` array to the current-email request payload. Each item may include `filename`, `name`, `size`, and `type`. The backend treats these values as untrusted metadata only.

AI output JSON changes: add `new_product_development` to the allowed `category` enum.

Prompt changes: include attachment metadata and new-product classification guidance.

## 10. Safety and Privacy Check

- [x] Does not read real mailbox data outside the user-opened current message.
- [x] Does not auto-send, delete, archive, move, forward, or reply.
- [x] Does not store or expose model credentials in frontend code.
- [x] Treats email text and attachment names as untrusted input.
- [x] Keeps AI output parseable and schema-validated.
- [x] Does not log real email body or attachment content.
- [x] Uses synthetic test samples only.

## 11. Prompt Injection Protection

- Email body and attachment names are analyzed as content, not instructions.
- Attachment metadata is never treated as a trusted command source.
- The assistant does not open or execute attachments.
- Draft replies must not commit price, target cost, delivery, contract, quality conclusion, or legal responsibility.

## 12. Acceptance Criteria

1. A bottle-trap cost-optimization project email is categorized as `new_product_development`, not `complaint`.
2. Attachment metadata is shown in the extension popup before/after analysis.
3. Attachment metadata is included in the backend prompt and rule fallback context.
4. The API accepts optional `attachments` without requiring file contents.
5. Tests cover the new category, attachment extraction, attachment payload, and renderer labels.
6. Full tests, maintenance scan, and JS syntax checks pass.

## 13. Test Plan

- Add analyzer tests for new product development classification and prompt attachment context.
- Add schema tests for the new category enum.
- Add browser extension behavior/static tests for attachment metadata extraction and API payload.
- Add renderer/local debug tests for attachment preview labels.
- Run `python -m unittest discover -s tests`.
- Run `python scripts/maintenance_scan.py`.
- Run `node --check` for touched frontend scripts.

## 14. Rollback Plan

Revert the category enum, rule changes, attachment extraction/payload changes, docs, and tests from this task. Existing current-email analysis and extension flow should continue to work without attachments.

## 15. Human Confirmation Questions

None blocking. The first attachment version is limited to metadata preview and analysis context.

## 16. Pre-execution Check

- [x] Read `AGENTS.md`.
- [x] Read relevant constraints and project status docs.
- [x] Defined task goal and non-goals.
- [x] Confirmed no new dependency and no real mailbox account integration.
- [x] Confirmed file scope.

## 17. Execution Record

Actual changed files:

- `backend/email_agent/analysis_schema.py`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/analysis_repair.py`
- `backend/email_agent/rule_analyzer.py`
- `backend/email_agent/rule_draft.py`
- `backend/email_agent/rule_keywords.py`
- `frontend/browser_extension/content/exmail_adapter.js`
- `frontend/browser_extension/shared/api_client.js`
- `frontend/browser_extension/shared/render_analysis.js`
- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.js`
- `frontend/local_debug_page/index.html`
- `frontend/local_debug_page/app.js`
- `docs/data/analysis_result_schema.md`
- `docs/api/backend_api_contract.md`
- `docs/prompts/analyzer_prompt.md`
- `docs/knowledge_base/email_categories.md`
- `docs/constraints/tooling_constraints.md`
- Related tests under `tests/`.

Test results:

- `python -m unittest tests.test_analysis_schema tests.test_rule_analyzer tests.test_analyzer tests.test_browser_extension_behavior tests.test_browser_extension_renderer_behavior tests.test_frontend_local_debug tests.test_browser_extension_static` passed.
- `python -m unittest discover -s tests` passed: 149 tests.
- `python scripts/maintenance_scan.py` passed with no cleanup findings.
- `node --check` passed for touched browser extension and local debug scripts.
- Live local API check with `Bottle trap Cost optimisation project-Delifu` plus `Bottle trap Project_Imported.pdf` metadata returned `category: new_product_development` and `analysis_engine.label: Local Qwen`.

Open items:

- The first attachment version only previews and sends metadata. It does not read PDF contents.

Follow-up:

- If later approved, attachment content extraction should be a separate opt-in feature with explicit file selection and a dedicated privacy review.
