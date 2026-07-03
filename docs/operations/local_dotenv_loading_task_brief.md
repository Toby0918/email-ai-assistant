---
last_update: 2026-07-03
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Local Dotenv Loading Task Brief

## 1. Task Name

load backend dotenv configuration

## 2. Task Type

fix

## 3. Current Status

implemented

## 4. Goal

Fix local service configuration so `.env` values such as `EMAIL_AGENT_LLM_PROVIDER=ollama` are loaded by the backend process. This should allow the explicitly enabled local Qwen path to be attempted before rule fallback.

## 5. Non-Goals

- Do not expose `.env`, Ollama endpoints, model names, or API keys to frontend code.
- Do not add automatic send, delete, archive, move, forward, or reply actions.
- Do not add real mailbox account integration.
- Do not bypass JSON schema validation or language boundary checks.

## 6. Root Cause Evidence

- `.env` contains `EMAIL_AGENT_LLM_PROVIDER=ollama`.
- `load_config()` currently returned `disabled` in a process without inherited environment variables.
- `/api/analyze-current-email` returned `analysis_engine.source=rule_fallback` for a normal test email.
- `config.py` used `os.getenv()` but did not call `python-dotenv` to load local `.env`.

## 7. Scope

Expected changes:

- `backend/email_agent/config.py`
- `tests/test_config.py`
- Relevant docs if behavior changes need clarification.

## 8. Technical Plan

1. Add a failing test showing `load_config()` can load backend values from a dotenv file.
2. Use `python-dotenv` in `config.py` with `override=False` so explicit process environment variables still win.
3. Keep tests isolated from the real workspace `.env` by allowing test callers to disable dotenv loading or pass a temporary dotenv path.

## 9. Data and Interface Changes

Database changes: none.

API changes: none.

AI output JSON changes: none.

Prompt changes: none.

## 10. Security and Privacy

- [x] Secrets remain backend-only.
- [x] Frontend still does not read `.env`.
- [x] Existing environment variables override `.env` values.
- [x] No real email content is added to docs or tests.

## 11. Acceptance Criteria

1. `load_config()` loads `EMAIL_AGENT_*` values from `.env` when process env does not provide them.
2. Explicit process environment variables override `.env`.
3. Existing config defaults remain testable without reading the real workspace `.env`.
4. Full test suite passes.

## 12. Test Plan

- `python -m unittest tests.test_config`
- `python -m unittest discover -s tests`
- Optional live check after service restart: `/api/analyze-current-email` shows `Local Qwen` when the model returns valid JSON.

## 13. Execution Notes

Actual changes:

- `backend/email_agent/config.py` loads backend `.env` with process environment override.
- `backend/email_agent/config.py` includes a minimal dotenv fallback for local interpreters without `python-dotenv` installed.
- `backend/email_agent/analysis_repair.py` repairs parseable partial model JSON before final schema validation.
- `backend/email_agent/llm_client.py` limits Ollama generation length with `num_predict=1200`.
- Tests cover dotenv loading, environment override, and partial model JSON repair.

Live check:

- After service restart, synthetic `/api/analyze-current-email` returned `analysis_engine.source=ai_model` and `analysis_engine.label=Local Qwen`.
- When Ollama was stuck, `ollama stop qwen3.6:latest` unloaded the model session; after backend restart, the synthetic API check returned `Local Qwen` again.
