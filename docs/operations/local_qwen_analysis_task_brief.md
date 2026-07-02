---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Local Qwen Analysis Task Brief

## 1. Task Name

```text
enhance email analysis with backend-only optional local Qwen
```

## 2. Task Type

```text
feature | prompt | security | test
```

## 3. Current Status

```text
in_progress
```

## 4. Goal

Improve current-email analysis so the Chinese feedback explains what the email says, which facts matter, and what action is needed. Add an optional backend-only Ollama provider for local `qwen3.6:latest`, while keeping the deterministic rule fallback usable when the local model is disabled or unavailable.

## 5. Non-Goals

- Do not connect to a real mailbox account.
- Do not automatically send, delete, archive, forward, move, or reply to email.
- Do not scan the mailbox or analyze messages without a user click.
- Do not call Ollama, OpenAI, or any model directly from frontend code.
- Do not change the public `/api/analyze-current-email` request or response shape.
- Do not store real email bodies in docs, tests, or logs.

## 6. Background And References

The current browser extension can extract Tencent Exmail content and call the local backend, but rule fallback output is still too generic for real business use. The user confirmed a local Ollama model is available at the backend machine and allowed backend calls to `qwen3.6:latest`.

Relevant documents:

- `AGENTS.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/data/analysis_result_schema.md`
- `docs/prompts/analyzer_prompt.md`
- `docs/security/api_key_rules.md`
- `docs/security/email_data_handling.md`
- `docs/security/privacy_rules.md`

## 7. Scope

Expected new or modified files:

- `backend/email_agent/email_facts.py`
- `backend/email_agent/rule_analyzer.py`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/llm_client.py`
- `backend/email_agent/config.py`
- `.env.example`
- `tests/test_email_facts.py`
- `tests/test_rule_analyzer.py`
- `tests/test_llm_client.py`
- `tests/test_config.py`
- `tests/test_analyzer.py`
- `tests/test_static_linter_constraints.py`
- `tests/test_architecture_constraints.py`
- Related docs under `docs/`

## 8. Technical Approach

1. Add a small deterministic fact extractor for references, quantities, dates, deadlines, issues, and requested actions.
2. Use extracted facts to make rule fallback summaries, risk evidence, suggested actions, and English drafts self-contained and specific.
3. Add a backend-only LLM provider switch: disabled by default, `ollama` when explicitly configured.
4. Call Ollama with JSON-mode output through `llm_client.py`; if it fails, keep falling back to rule analysis.
5. Update docs and executable guards so the frontend cannot call Ollama directly.

## 9. Data Structure Or Interface Changes

### Database Changes

```text
None.
```

### API Changes

```text
None. The backend route and response schema remain unchanged.
```

### AI Output JSON Changes

```text
None. Existing fields become more specific, but no field is added or removed.
```

### Prompt Changes

```text
Yes. The prompt will require self-contained Chinese feedback and an English draft grounded in extracted email facts.
```

## 10. Security And Privacy Check

```text
[x] Do not read a real mailbox account unless separately authorized.
[x] Do not automatically send, delete, or archive email.
[x] Do not store or expose OpenAI API keys in frontend code.
[x] Treat email subject, sender, attachment names, and body as untrusted input.
[x] Require AI output to be parseable and validated JSON.
[x] Do not log real email bodies, customer-sensitive data, API keys, or tokens.
[x] Keep test samples synthetic or sanitized.
```

## 11. Prompt Injection Protection

- Email content is analyzed as data, never executed as instructions.
- Do not reveal system prompts, secrets, database content, or other email content.
- Do not let AI commit price, lead time, payment, contract, legal, delivery, or quality responsibility.
- If a model result fails JSON or language validation, fall back to deterministic rules.

## 12. Acceptance Criteria

1. A multi-fact quality email produces Chinese feedback that mentions the important PO/reference, quantity, issue, requested action, and deadline when present.
2. The English draft uses the same facts and avoids generic “confirm the details” wording.
3. `EMAIL_AGENT_LLM_PROVIDER=ollama` sends backend-only requests to `http://127.0.0.1:11434/api/generate` with model `qwen3.6:latest`.
4. Disabled or unavailable local LLM still falls back to deterministic analysis.
5. Frontend static and architecture tests forbid direct Ollama endpoints and local model calls.
6. Full unit tests, maintenance scan, JS syntax checks, and diff whitespace checks pass before completion.

## 13. Test Plan

- `python -m unittest discover -s tests -p "test_email_facts.py"`
- `python -m unittest discover -s tests -p "test_rule_analyzer.py"`
- `python -m unittest discover -s tests -p "test_llm_client.py"`
- `python -m unittest discover -s tests -p "test_config.py"`
- `python -m unittest discover -s tests -p "test_analyzer.py"`
- `python -m unittest discover -s tests`
- `python scripts/maintenance_scan.py`
- `node --check frontend/browser_extension/popup.js`
- `node --check frontend/browser_extension/content/exmail_adapter.js`
- `node --check frontend/browser_extension/shared/api_client.js`
- `node --check frontend/browser_extension/shared/render_analysis.js`
- `git diff --check`

## 14. Rollback Plan

Revert this task commit to remove the local Ollama provider, fact extractor, prompt changes, and related docs/tests. The backend will return to existing rule-only fallback behavior.

## 15. Human Confirmation Needed

```text
None. The user confirmed B plan and allowed backend local model calls.
```

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Relevant docs have been read.
[x] Goal and non-goals are explicit.
[x] This task does not touch real mailbox credentials, real secrets, or real customer data.
[x] File scope is identified.
```

## 17. Execution Record

```text
Actual modified files:
- .env.example
- AGENTS.md
- backend/email_agent/analyzer.py
- backend/email_agent/config.py
- backend/email_agent/email_facts.py
- backend/email_agent/llm_client.py
- backend/email_agent/rule_analyzer.py
- backend/email_agent/rule_draft.py
- docs/api/backend_api_contract.md
- docs/api/frontend_backend_flow.md
- docs/constraints/architecture_constraints.md
- docs/constraints/linter_constraints.md
- docs/constraints/tooling_constraints.md
- docs/data/analysis_result_schema.md
- docs/operations/deployment_notes.md
- docs/operations/project_status_log.md
- docs/operations/setup_checklist.md
- docs/operations/troubleshooting.md
- docs/prompts/analyzer_prompt.md
- docs/security/api_key_rules.md
- docs/security/email_data_handling.md
- docs/security/privacy_rules.md
- tests/test_analyzer.py
- tests/test_architecture_constraints.py
- tests/test_config.py
- tests/test_email_facts.py
- tests/test_llm_client.py
- tests/test_rule_analyzer.py
- tests/test_static_linter_constraints.py

Test results:
- python -m unittest discover -s tests: 140 tests passed.
- python scripts/maintenance_scan.py: no cleanup findings detected.
- node --check frontend/browser_extension/popup.js: passed.
- node --check frontend/browser_extension/content/exmail_adapter.js: passed.
- node --check frontend/browser_extension/shared/api_client.js: passed.
- node --check frontend/browser_extension/shared/render_analysis.js: passed.
- git diff --check: passed with Windows line-ending warnings only.
- Synthetic local Ollama probe with EMAIL_AGENT_LLM_PROVIDER=ollama: returned {"ok":true}.

Unfinished items:
- None for this B-plan implementation. To use local Qwen in the running service, set backend environment variables and restart the local service.

Follow-up suggestions:
- Evaluate a few real-but-redacted business samples after enabling EMAIL_AGENT_LLM_PROVIDER=ollama.
- If Qwen output is still too broad, add a smaller domain prompt fixture set before changing the browser extension.
```
