---
last_update: 2026-07-13
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
- `docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md`
- `docs/superpowers/specs/2026-07-12-deepseek-led-email-analysis-design.md`
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
3. Configure a standard-library rotating file handler before the local service starts.
4. Keep the public response and deterministic fallback byte-for-byte compatible with current behavior.
5. Document the operator command for reading only the newest diagnostic event.

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
- docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md
- docs/operations/project_status_log.md (generator only)

Actual commits before the Task 5 documentation commit:
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
- Task 5 uses subject: docs: document fallback diagnostics. Its SHA is recorded in the ignored Task 5 report because a commit cannot embed its own stable hash.

Test results:
- Task-level RED/GREEN evidence is recorded in `.superpowers/sdd/task-1-report.md` through `task-4-report.md`.
- Task 5 documentation RED: 8 tests ran; the new contract produced 17 expected missing-marker failures while the other 7 tests passed.
- Task 5 documentation GREEN: 8 tests ran, all passed.
- Focused documentation and mechanical verification: 49 tests ran, all passed.
- Full suite: the first 683-test run had the known shared 8-second XLSX boundary downgrade on the fifth synthetic file; the unchanged test then passed alone in 7.653 seconds, and a fresh complete run passed all 683 tests.
- Maintenance scan: `No cleanup findings detected.`
- JavaScript syntax: all 7 files under `frontend/` passed `node --check`.
- Isolated service smoke: provider `disabled`, `127.0.0.1:8878`, and `outputs/local_debug_service_verify.pid`; start/status succeeded, only `GET /api/health` was called and returned `ok=true`, `finally` stop succeeded, the PID file was removed, and no 8878 listener remained.
- No automated analysis POST, live DeepSeek request, real mailbox operation, or main-checkout `.env` access occurred.

Unfinished items:
- User-triggered synthetic live diagnostic after branch integration and normal-service restart.

Follow-up recommendation:
- After the user performs one synthetic Analyze action, read only the newest event with `Get-Content outputs\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'` and use the first emitted reason code to select one root-cause correction.
```
