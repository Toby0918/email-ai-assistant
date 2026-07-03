---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Analysis Engine Status Task Brief

## 1. Task Name

show analysis engine status

## 2. Task Type

feature

## 3. Current Status

implemented

## 4. Goal

Show whether a completed analysis used the backend AI model path or the deterministic rule fallback, so local testing can confirm when Qwen is active.

## 5. Non-Goals

- Do not add automatic send, delete, archive, move, forward, or reply actions.
- Do not expose Ollama endpoints, model names, API keys, or environment variables in frontend code.
- Do not add mailbox scanning or real account integration.
- Do not store raw prompts or email bodies in logs.

## 6. Background

The backend can now call a local model provider and fall back to rules. The UI needs a safe, backend-authored status marker so testers can tell which path produced the result.

Related documents:

- `AGENTS.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/data/analysis_result_schema.md`
- `docs/api/backend_api_contract.md`

## 7. Scope

Expected changes:

- `backend/email_agent/analyzer.py`
- `backend/email_agent/llm_client.py`
- `frontend/browser_extension/*`
- `frontend/local_debug_page/*`
- `docs/data/analysis_result_schema.md`
- `docs/api/backend_api_contract.md`
- `tests/`

## 8. Technical Plan

1. Backend appends an `analysis_engine` metadata object after AI JSON validation, not from model output.
2. Successful validated model output is marked as model analysis; model errors or invalid output are marked as rule fallback.
3. Frontends render the label returned by the backend without knowing model endpoints or provider configuration.

## 9. Data and Interface Changes

Database changes: none.

API changes: `analysis` gains optional backend-authored `analysis_engine` metadata.

AI output JSON changes: none; AI is not trusted to provide this metadata.

Prompt changes: none.

## 10. Security and Privacy

- [x] No real mailbox account integration.
- [x] No automatic send, delete, archive, move, forward, or reply action.
- [x] No frontend API key, Ollama endpoint, or model configuration exposure.
- [x] Email content remains untrusted input.
- [x] AI output remains parsed and validated before use.
- [x] Logs must not include raw email bodies, prompts, keys, or tokens.
- [x] Tests use synthetic data only.

## 11. Acceptance Criteria

1. Validated model output returns `analysis.analysis_engine.label`.
2. Model failure or invalid output returns a visible rule fallback label.
3. Model-supplied `analysis_engine` values are ignored or overwritten by backend metadata.
4. Browser extension and local debug page display the engine label.
5. Frontend code still has no direct local-model endpoint or provider markers.

## 12. Test Plan

- Run targeted analyzer and frontend tests first.
- Run full `python -m unittest discover -s tests`.
- Run frontend JavaScript syntax checks.
- Run `scripts/maintenance_scan.py`.

## 13. Rollback

Revert the engine metadata additions and related UI rendering if the feature causes schema or rendering regressions.

## 14. Execution Notes

Actual modified files:

- `backend/email_agent/analyzer.py`
- `backend/email_agent/llm_client.py`
- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.js`
- `frontend/browser_extension/shared/render_analysis.js`
- `frontend/local_debug_page/index.html`
- `frontend/local_debug_page/app.js`
- `docs/api/backend_api_contract.md`
- `docs/data/analysis_result_schema.md`
- `tests/test_analyzer.py`
- `tests/test_browser_extension_renderer_behavior.py`
- `tests/test_browser_extension_static.py`
- `tests/test_frontend_local_debug.py`

Verification:

- Targeted analyzer and frontend tests passed after red/green implementation.
- Full test suite passed before project status regeneration.
