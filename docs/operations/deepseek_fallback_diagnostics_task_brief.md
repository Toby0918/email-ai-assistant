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
approved
```

The user approved the recommended diagnostic patch on 2026-07-13. Implementation waits only for review of the written design specification.

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
- `backend/email_agent/analysis_model_routes.py`
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
- The user must review the written design before the implementation plan begins.
- The user, not automated tests or Codex, will trigger the post-patch synthetic live DeepSeek request.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status and required tooling, architecture, linter, documentation, logging, security, API, and existing DeepSeek documents have been read.
[x] Goal, non-goals, security boundaries, and acceptance criteria are explicit.
[x] No real mailbox, real message, API key, or customer data will be read or logged.
[x] Expected file scope is identified.
[ ] Written design has been reviewed by the user.
```

## 17. Execution Record

```text
Actual modified files:
- Pending implementation.

Test results:
- Pending implementation.

Unfinished items:
- Written design review.
- Test-driven implementation and verification.
- User-triggered synthetic live diagnostic after restart.

Follow-up recommendation:
- Use the first emitted reason code to select one root-cause correction rather than changing multiple provider settings at once.
```
