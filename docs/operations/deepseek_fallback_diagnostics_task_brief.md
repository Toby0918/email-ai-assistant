---
last_update: 2026-07-21
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Fallback Diagnostics Task Brief

## 1. Task Name

```text
add sanitized DeepSeek fallback diagnostics and Windows service logging
```

## 2. Task Type

```text
fix | security | test | docs
```

## 3. Current Status

```text
active
```

The user approved the recommended diagnostic patch on 2026-07-13. Written-design review and implementation are complete; offline release verification is recorded below, and only the user-triggered synthetic live diagnostic remains deferred.

## 4. Goal

Make every model-to-rule fallback diagnosable by a safe local reason code while preserving the exact fail-closed public behavior. Ensure those diagnostics are written to a bounded local file when the service runs through the Windows WMI launcher.

## 5. Non-Goals

- Do not change the public request or response schema.
- Do not change SQLite persistence.
- Do not change prompts, model authority, safety merge rules, or fallback behavior.
- Do not add retries, asynchronous analysis, or a second provider.
- Do not add frontend diagnostics or provider details.
- Do not log raw exceptions, provider responses, prompts, emails, attachments, keys, tokens, URLs, paths, or customer data.
- Do not run a live or paid DeepSeek request during implementation or automated verification.
- Do not access a real mailbox or perform any mailbox action.

## 6. Background And References

The enabled DeepSeek configuration still produces `analysis_engine.source=rule_fallback`. Read-only diagnosis showed that configuration timing and basic network reachability are not the leading issue, but the current code collapses every provider and validation failure into the same result and the Windows-managed service log is empty.

References:

- `AGENTS.md`
- `docs/operations/deepseek_api_analysis_task_brief.md`
- `docs/conventions/logging.md`
- `docs/security/api_key_rules.md`
- `docs/security/email_data_handling.md`
- `docs/api/backend_api_contract.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. Expected Scope

Expected additions or modifications:

- `backend/email_agent/llm_client.py`
- `backend/email_agent/llm_errors.py`
- `backend/email_agent/analysis_diagnostics.py`
- `backend/email_agent/analysis_model_routes.py`
- `backend/email_agent/legacy_model_analysis.py`
- `backend/email_agent/logging_config.py`
- `scripts/run_local_debug.py`
- focused tests for client, routing, logging, and entrypoint behavior
- logging, troubleshooting, deployment, API-operational, and task/status documentation

No frontend, prompt, schema, database, attachment parser, or mailbox integration file is expected to change.

## 8. Technical Approach

1. Add allowlisted internal reason codes to sanitized client and route failures.
2. Emit one terminal safe event per model fallback without passing sensitive payload objects to the logger.
3. Configure a standard-library rotating file handler only on the dedicated diagnostic logger before the local service starts; never attach it to root.
4. Keep the public response and deterministic fallback byte-for-byte compatible with current behavior.
5. Document the operator command for reading only the newest diagnostic event.

The route/stage mapping contract remains exact. `response_incomplete` and
`response_empty` use `stage=response`; every other `LlmClientError` reason uses
`stage=provider`. In conservative mode, `parse_legacy_result` performs JSON
parsing, repair, and public schema validation only. The exported
`validate_conservative_language` validator runs in a separate route `_run_stage`,
so failures remain distinct as `public_schema_invalid` / `schema` and
`public_language_invalid` / `language`.

## 9. Data And Interface Changes

### Database Changes

```text
None.
```

### API Changes

```text
None.
```

### AI Output JSON Changes

```text
None.
```

### Prompt Changes

```text
None.
```

### Internal Diagnostics

```text
Add backend-only allowlisted reason codes and bounded local log events. They are not part of the public API or SQLite record.
```

## 10. Security And Privacy Check

```text
[x] Do not access real mailbox data.
[x] Do not automatically send, delete, archive, move, forward, or reply to email.
[x] Keep API keys and provider configuration backend-only.
[x] Continue treating email and attachment fields as untrusted input.
[x] Preserve parseable and validated AI JSON requirements.
[x] Do not log email text, customer data, prompts, provider output, API keys, tokens, URLs, paths, or raw exceptions.
[x] Use only synthetic test values.
[x] Perform no live provider call during implementation or automated verification.
```

## 11. Prompt Injection Protection

This task does not change prompt construction or model context. Diagnostic functions must not accept untrusted email, thread, attachment, provider-response, or model-output text, so prompt-injection content cannot enter the new log path.

## 12. Acceptance Criteria

1. Safe reason codes distinguish the operational failure stages defined in the design.
2. Exactly one terminal diagnostic event is emitted for each fallback attempt.
3. Raw exception and private payload content cannot appear in the event.
4. Windows-managed service runs write diagnostics to the bounded local service log.
5. Rule fallback and the public API remain unchanged.
6. Accepted model results continue to report `ai_model`.
7. Tests and documentation verify all boundaries without a live provider call.

## 13. Test Plan

- Write failing tests for client reason classification and raw-error redaction.
- Write failing route tests for each diagnostic stage and exact rule fallback.
- Write failing logging tests for rotating file output and prohibited-field absence.
- Write failing entrypoint tests proving logging configuration precedes server startup.
- Run focused tests after each minimal implementation step.
- Run full `python -m unittest discover -s tests` with the bundled Python runtime.
- Run static, architecture, mechanical, documentation, JavaScript syntax, maintenance, status-generation, and `git diff --check` verification required by project rules.

## 14. Rollback Plan

Revert the diagnostic and logging changes. If provider operation must be stopped independently, set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the service.

## 15. Human Confirmation Needed

- The user already approved implementing the sanitized diagnostics direction.
- The user completed the written-design review before implementation began.
- The user, not automated tests or Codex, will trigger the post-patch synthetic live DeepSeek request.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status and required tooling, architecture, linter, documentation, logging, security, API, and existing DeepSeek documents have been read.
[x] Goal, non-goals, security boundaries, and acceptance criteria are explicit.
[x] No real mailbox, real message, API key, or customer data will be read or logged.
[x] Expected file scope is identified.
[x] Written design has been reviewed by the user.
```

## 17. Execution Record

```text
Actual modified files:
- backend/email_agent/__init__.py
- backend/email_agent/analysis_diagnostics.py
- backend/email_agent/analysis_model_routes.py
- backend/email_agent/legacy_model_analysis.py
- backend/email_agent/llm_client.py
- backend/email_agent/llm_errors.py
- backend/email_agent/logging_config.py
- scripts/run_local_debug.py
- tests/test_analysis_diagnostics.py
- tests/test_analyzer.py
- tests/test_llm_client.py
- tests/test_logging_config.py
- tests/test_run_local_debug.py
- tests/test_static_linter_constraints.py
- tests/test_deepseek_documentation_contracts.py
- docs/conventions/logging.md
- docs/operations/troubleshooting.md
- docs/operations/deployment_notes.md
- docs/api/backend_api_contract.md
- docs/operations/deepseek_fallback_diagnostics_task_brief.md
- docs/operations/project_status_log.md (generator only)

Actual commits:
- 0fc6f56cc3c1f9dac8af8160389356f0085cebfc docs: correct diagnostics execution plan
- 5cc34e29dd0ec9e2b5b4617eac0c9d9c40c98c09 feat: add sanitized fallback diagnostics
- 0369a36c75d038900ebb70c0a2d013310ec58bab fix: canonicalize diagnostic fields
- d05ac33805051ba2eabdd023daad3ea4f505ad50 fix: classify DeepSeek client failures
- 02e5a81736243717c956e35fc3015cdb81669d20 docs: amend client classification scope
- 2c8a140fc1c42ab56a62d15fc87b135eb952961e refactor: extract client failure classification
- d4d758b4ad9ac11a7e49fb4610528c2e55ed2ad2 docs: expand route diagnostics scope
- deb4949d66d0ad6aa0f434bac03222566b0c1de2 fix: diagnose model fallback stages
- c4117d9a5b7d30f18bd96ceebab63d2e5e989b61 fix: close terminal route error boundary
- 3363a40e2d81403def10beca723c3caa154f53ec fix: persist sanitized service diagnostics
- d921bb6534ba3f87cf32ab75be38cd0c78876c96 docs: document fallback diagnostics
- 001e3441fcc39ccf42d5800842bde8d90930886a docs: strengthen fallback event contract
- f4a75ddfc58377ccf214d78d57ebf54aab69310f fix: isolate fallback diagnostic logging
- 9378c8d2903d77afbc310ad361d257f43c10c163 fix: reject cached diagnostic exceptions
- 7d832dffc3d9efc3b47ae646f44e770d641e0576 docs: require cached exception filtering
- e10c480fd440a48f64ed8598e92e2959a5ff0678 fix: distinguish fallback response and language stages

Final review closure:
- C1 is closed by the dedicated non-root diagnostic sink in `f4a75dd`; OpenAI, HTTPX, HTTP core, arbitrary backend, and non-canonical direct records cannot write the bounded diagnostic log.
- I1 is closed by the fixed `WARNING` diagnostic logger and handler threshold in `f4a75dd`, independent of the general DEBUG/INFO/WARNING/ERROR/CRITICAL/invalid level. The later cached-`exc_text` review gap is closed in production and tests by `9378c8d`; its canonical documentation contract is recorded in this brief and `docs/conventions/logging.md`.
- I2 and I3 are closed by `e10c480`: incomplete/empty responses now use `stage=response`, and conservative language failures now use `public_language_invalid/language` separately from schema failures.
- The final logging review found no remaining Critical or Important issue after those remediations. The final route independent review passed spec compliance and code quality with no findings. Therefore C1, I1, I2, and I3 are closed in the canonical task record.

Test results:
- Historical task-level RED/GREEN evidence remains recoverable from Git history; this brief retains the canonical acceptance and release record.
- Task 5 documentation RED: 8 tests ran; the new contract produced 17 expected missing-marker failures while the other 7 tests passed.
- Task 5 documentation GREEN: 8 tests ran, all passed.
- Focused documentation and mechanical verification: 49 tests ran, all passed.
- Full suite: the first 683-test run had the known shared 8-second XLSX boundary downgrade on the fifth synthetic file; the unchanged test then passed alone in 7.653 seconds, and a fresh complete run passed all 683 tests.
- Logging remediation release verification: the latest complete logging-remediation suite passed all 685 tests; the focused privacy, lifecycle, cached-exception, entrypoint, static, analyzer, and documentation checks also passed.
- Route remediation release verification: 98 focused tests passed and the complete suite passed all 691 tests.
- Maintenance scans for the Task 5, logging-remediation, and route-remediation release gates reported `No cleanup findings detected.`
- The corresponding `git diff --check` commands exited `0`; the route status generator also exited `0` and left `docs/operations/project_status_log.md` unchanged.
- JavaScript syntax: all 7 files under `frontend/` passed `node --check`.
- Isolated service smoke: provider `disabled`, `127.0.0.1:8878`, and `outputs/local_debug_service_verify.pid`; start/status succeeded, only `GET /api/health` was called and returned `ok=true`, `finally` stop succeeded, the PID file was removed, and no 8878 listener remained.
- Automated verification never called DeepSeek. No automated analysis POST, live provider request, real mailbox operation, or main-checkout `.env` access occurred.
- This branch has not been integrated, and this work did not start or restart the normal service on port 8765.

Unfinished items:
- The only unfinished item within this diagnostic task is the user-triggered synthetic live diagnostic. Branch integration and any normal-service restart on port 8765 are external user-controlled prerequisites and were not performed or claimed here.

Follow-up recommendation:
- After the user performs one synthetic Analyze action, read only the newest event with `Get-Content outputs\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'` and use the first emitted reason code to select one root-cause correction.
```
