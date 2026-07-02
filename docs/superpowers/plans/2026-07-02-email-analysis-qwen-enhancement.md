---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Email Analysis Qwen Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the analysis result specific enough to understand the current email and optionally use backend-only local Qwen through Ollama for richer JSON output.

**Architecture:** Keep the Chrome / Edge extension as a thin current-email extractor and local backend caller. Put all model access in `backend/email_agent/llm_client.py`, keep deterministic rule fallback in `rule_analyzer.py`, and add a focused `email_facts.py` helper for safe fact carry-through.

**Tech Stack:** Python 3.12.13, stdlib `urllib.request`, SQLite, existing JSON schema validation, unittest, Tencent Exmail browser extension JavaScript.

---

## File Structure

- Create `backend/email_agent/email_facts.py`: deterministic fact extraction from untrusted cleaned email text.
- Modify `backend/email_agent/rule_analyzer.py`: use facts for summary, risk evidence, suggested actions, and English draft.
- Modify `backend/email_agent/analyzer.py`: strengthen the prompt and keep fallback behavior.
- Modify `backend/email_agent/llm_client.py`: add disabled-by-default Ollama provider.
- Modify `backend/email_agent/config.py`: add provider, Ollama base URL, model, and timeout config.
- Modify tests under `tests/`: cover fact extraction, rule output, Ollama request shape, config defaults, prompt wording, and frontend guardrails.
- Modify docs and `.env.example`: document backend-only Ollama and self-contained analysis output.

## Task 1: Add Deterministic Email Fact Extraction

**Files:**
- Create: `backend/email_agent/email_facts.py`
- Test: `tests/test_email_facts.py`

- [ ] **Step 1: Write failing tests**

Add tests that call `extract_email_facts(subject, sender, clean_body)` and assert extraction of:

```python
facts = extract_email_facts(
    subject="Urgent response needed - PO 10138937872 quality issue",
    sender="customer@example.test",
    clean_body=(
        "For PO 10138937872, 3,000 pcs of material 1009890-G failed inspection. "
        "The 7.21mm +/- .05 hole has burrs and is out of tolerance. "
        "Please provide RCA and corrective action within 24 hours of receipt."
    ),
)
```

Expected assertions:

- references include `PO 10138937872` and `1009890-G`.
- quantities include `3,000 pcs`.
- quality issues include `burrs` or `out of tolerance`.
- requested actions include `provide RCA` or `corrective action`.
- deadline includes `within 24 hours`.

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m unittest discover -s tests -p "test_email_facts.py"
```

Expected: fail because `backend.email_agent.email_facts` does not exist.

- [ ] **Step 3: Implement minimal extractor**

Create dataclass `EmailFacts` with list fields and helper properties. Use regex patterns for PO/reference IDs, quantities, dates/deadlines, quality issues, and requested actions. Limit returned lists to short unique values to avoid dumping full email text.

- [ ] **Step 4: Verify green**

Run:

```powershell
python -m unittest discover -s tests -p "test_email_facts.py"
```

Expected: pass.

## Task 2: Make Rule Analysis Self-Contained

**Files:**
- Modify: `backend/email_agent/rule_analyzer.py`
- Test: `tests/test_rule_analyzer.py`

- [ ] **Step 1: Write failing behavior tests**

Add tests asserting a quality/PO email returns:

- Chinese summary containing `PO 10138937872`, `3,000 pcs`, `7.21mm`, and `RCA` or `corrective action`.
- `quality_risk.evidence` grounded in the specific issue, not only the generic quality template.
- `suggested_actions` mentioning the PO/reference and requested action.
- English draft mentioning `PO 10138937872`, `RCA`, `corrective action`, and `within 24 hours`.
- Draft does not include Chinese text or auto-commit statements.

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m unittest discover -s tests -p "test_rule_analyzer.py"
```

Expected: fail because current output is generic.

- [ ] **Step 3: Implement fact-aware rule output**

Import `extract_email_facts`. Thread `facts` into summary, risk flags, suggested actions, and draft helpers. Keep schema fields unchanged. Generate multiple suggested actions only when the email includes multiple distinct actionable risk classes.

- [ ] **Step 4: Verify green**

Run:

```powershell
python -m unittest discover -s tests -p "test_rule_analyzer.py"
```

Expected: pass.

## Task 3: Add Backend-Only Ollama Provider

**Files:**
- Modify: `backend/email_agent/config.py`
- Modify: `backend/email_agent/llm_client.py`
- Test: `tests/test_config.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing config and client tests**

Add tests for:

- Defaults: provider `disabled`, base URL `http://127.0.0.1:11434`, model `qwen3.6:latest`, timeout `30`.
- Environment overrides for `EMAIL_AGENT_LLM_PROVIDER`, `EMAIL_AGENT_OLLAMA_BASE_URL`, `EMAIL_AGENT_OLLAMA_MODEL`, and `EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS`.
- Disabled provider raises `LlmClientError`.
- Ollama provider posts JSON to `/api/generate` with `stream: false`, `format: "json"`, and configured model.
- Non-200, invalid JSON, empty response, and timeout-style failures become sanitized `LlmClientError`.

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m unittest discover -s tests -p "test_config.py"
python -m unittest discover -s tests -p "test_llm_client.py"
```

Expected: fail because provider config and Ollama client do not exist.

- [ ] **Step 3: Implement provider**

Use stdlib `urllib.request` to call Ollama. Do not add dependencies. Keep OpenAI path disabled unless later separately implemented. Never include prompt text or raw backend exception strings in `LlmClientError`.

- [ ] **Step 4: Verify green**

Run:

```powershell
python -m unittest discover -s tests -p "test_config.py"
python -m unittest discover -s tests -p "test_llm_client.py"
```

Expected: pass.

## Task 4: Strengthen Prompt And Validation Tests

**Files:**
- Modify: `backend/email_agent/analyzer.py`
- Test: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing prompt tests**

Assert the prompt asks for self-contained Chinese feedback including key facts, references, requested actions, deadlines, and risks. Assert English draft must be grounded in those facts and avoid commitments.

- [ ] **Step 2: Verify red**

Run:

```powershell
python -m unittest discover -s tests -p "test_analyzer.py"
```

Expected: fail because the current prompt does not include the stronger fact requirements.

- [ ] **Step 3: Update prompt builder**

Add explicit instructions for summary, risk evidence, suggested actions, and English draft. Preserve untrusted-input and language-boundary instructions.

- [ ] **Step 4: Verify green**

Run:

```powershell
python -m unittest discover -s tests -p "test_analyzer.py"
```

Expected: pass.

## Task 5: Update Guardrails And Documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `.env.example`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/constraints/architecture_constraints.md`
- Modify: `docs/constraints/linter_constraints.md`
- Modify: `docs/data/analysis_result_schema.md`
- Modify: `docs/prompts/analyzer_prompt.md`
- Modify: `docs/security/api_key_rules.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/security/privacy_rules.md`
- Modify: `tests/test_static_linter_constraints.py`
- Modify: `tests/test_architecture_constraints.py`

- [ ] **Step 1: Write failing frontend guard tests**

Add forbidden frontend patterns for:

- `127.0.0.1:11434`
- `/api/generate`
- `/api/chat`
- `ollama`
- `qwen3.6`

- [ ] **Step 2: Verify guard tests**

Run:

```powershell
python -m unittest discover -s tests -p "test_static_linter_constraints.py"
python -m unittest discover -s tests -p "test_architecture_constraints.py"
```

Expected: pass after code remains backend-only; fail only if frontend contains local model calls.

- [ ] **Step 3: Update docs**

Document that local Qwen/Ollama is optional, backend-only, disabled by default, and subject to the same JSON and human-review constraints.

- [ ] **Step 4: Verify docs**

Run:

```powershell
python -m unittest discover -s tests -p "test_static_linter_constraints.py"
python -m unittest discover -s tests -p "test_architecture_constraints.py"
```

Expected: pass.

## Task 6: Final Verification And Status Log

**Files:**
- Modify: `docs/operations/project_status_log.md`
- Modify: `docs/operations/local_qwen_analysis_task_brief.md`

- [ ] **Step 1: Regenerate status log**

Run:

```powershell
python scripts/generate_project_status.py --output docs/operations/project_status_log.md
```

- [ ] **Step 2: Run full verification**

Run:

```powershell
python -m unittest discover -s tests
python scripts/maintenance_scan.py
node --check frontend/browser_extension/popup.js
node --check frontend/browser_extension/content/exmail_adapter.js
node --check frontend/browser_extension/shared/api_client.js
node --check frontend/browser_extension/shared/render_analysis.js
git diff --check
```

- [ ] **Step 3: Update execution record**

Record modified files, verification commands, and remaining manual steps in `docs/operations/local_qwen_analysis_task_brief.md`.

- [ ] **Step 4: Commit**

Use one commit:

```powershell
git add .
git commit -m "feat: add backend local qwen analysis provider"
```

## Self-Review

- Spec coverage: the plan covers self-contained analysis, better deterministic fallback, backend-only Ollama, docs, tests, and final verification.
- Placeholder scan: the plan contains no deferred implementation placeholders.
- Type consistency: new names are `EmailFacts`, `extract_email_facts`, `EMAIL_AGENT_LLM_PROVIDER`, and `qwen3.6:latest`.
