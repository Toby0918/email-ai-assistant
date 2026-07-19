### Task 1: Lock governance, configuration, and mechanical boundaries

**Files:**
- Modify: `AGENTS.md`
- Modify: `.env.example`
- Modify: `backend/email_agent/config.py`
- Modify: `backend/email_agent/analysis_budget.py`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `docs/product/feature_scope.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/security/privacy_rules.md`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/constraints/architecture_constraints.md`
- Modify: `docs/constraints/linter_constraints.md`
- Modify: `docs/templates/agent_task_brief_template.md`
- Modify: `tests/test_config.py`
- Modify: `tests/test_analysis_budget.py`
- Modify: `tests/test_browser_extension_task6_contracts.py`
- Modify: `tests/test_frontend_local_debug.py`
- Modify: `tests/test_architecture_constraints.py`
- Modify: `tests/test_static_linter_constraints.py`

**Interfaces:**
- `AppConfig` gains `openai_model`, `openai_timeout_seconds`, and `text_fallback_provider` with safe defaults.
- Allowed OpenAI model is exactly `gpt-5.6-sol`; allowed fallback values are `disabled` and `deepseek`.
- `AnalysisBudget` exposes the exact 55/35/10/12/5 constants without changing the separate private-evaluation 13-second dataset runner.

- [x] Write failing config, budget, frontend-timeout, architecture, and documentation-canary tests first.
- [x] Run the focused modules and preserve RED showing missing fields and stale 15/13-second constants.
- [x] Implement configuration normalization, fixed allowlists, safe defaults, exact timeouts, and no configurable OpenAI endpoint.
- [x] Update governance text with the exact persistent disclosure from task-brief section 15; frontend markup changes remain Task 7.
- [x] Run the focused tests GREEN and commit `feat: define multimodal provider boundaries`.
