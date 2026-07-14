---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Envelope Subdiagnostics Task Brief

## 1. Task Name

```text
add content-free DeepSeek envelope fallback subdiagnostics
```

## 2. Task Type

```text
fix | security | test | docs
```

## 3. Current Status

```text
implemented
```

## 4. Goal

Keep the existing `envelope_invalid` rule fallback while identifying which
coarse, non-sensitive private-envelope boundary rejected a synthetic DeepSeek
response.

## 5. Non-Goals

- Do not log provider output, JSON keys, paths, values, exceptions, email data,
  attachment data, credentials, URLs, paths, or customer information.
- Do not change the prompt, private or public JSON schema, provider request,
  model, timeout, retry policy, API, SQLite, frontend, or rule fallback.
- Do not repair or normalize invalid model output.
- Do not access a real mailbox or perform any mailbox action.
- Do not make more than one post-verification synthetic live call.

## 6. Background And References

A user-triggered synthetic request produced
`code=envelope_invalid stage=envelope ... elapsed_ms=10187`. Provider transport
and response extraction completed, but the generic private-envelope exception
does not identify the rejected structural boundary.

References:

- `AGENTS.md`
- `docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md`
- `docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md`
- `docs/operations/deepseek_fallback_diagnostics_task_brief.md`
- `docs/conventions/logging.md`
- `docs/operations/troubleshooting.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. Expected Scope

Expected modifications:

- `backend/email_agent/deepseek_analysis_schema.py`
- `backend/email_agent/analysis_model_routes.py`
- `backend/email_agent/analysis_diagnostics.py`
- `backend/email_agent/logging_config.py`
- focused parser, route, logging, static, and documentation tests
- `docs/conventions/logging.md`
- `docs/operations/troubleshooting.md`
- `docs/operations/deployment_notes.md`
- `docs/api/backend_api_contract.md`
- `docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md`
- `docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md`
- this task brief and project status log

No frontend, database, provider client, prompt, model context, attachment parser,
or mailbox integration file is expected to change.

## 8. Technical Approach

1. Add one fixed detail to the generic private-envelope exception at six coarse
   validation boundaries.
2. Carry that detail through the internal fallback object without changing the
   returned rule analysis.
3. Add one exact allowlisted `detail` argument to the canonical diagnostic
   event and force non-envelope fallbacks to `not_applicable`.
4. Keep the diagnostic sink isolated, filtered, rotating, and content-free.

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

### Internal Diagnostic Changes

```text
The operator-only analysis_fallback event gains one fixed allowlisted detail field.
```

The canonical internal event is:

```text
event=analysis_fallback code=<allowlisted code> stage=<allowlisted stage> provider=<allowlisted provider> model=<allowlisted model> output_mode=<allowlisted mode> detail=<allowlisted detail> elapsed_ms=<non-negative integer>
```

The detail allowlist is not_applicable, json_syntax, top_level_shape,
schema_version, analysis_shape, attachment_shape, and field_evidence_shape.
Every non-envelope fallback uses not_applicable. This operator-only log field
is not added to the public API or SQLite, and it must never contain or be used
to reconstruct provider output, JSON keys, paths, values, or exception text.

## 10. Security And Privacy Check

```text
[x] Do not access real mailbox data.
[x] Do not automatically send, delete, archive, move, forward, or reply.
[x] Keep API keys and provider configuration backend-only.
[x] Continue treating provider output and email content as untrusted.
[x] Preserve strict JSON validation and complete rule fallback.
[x] Do not log provider output, JSON keys/paths/values, raw exceptions, email or attachment content, keys, tokens, URLs, paths, or customer identifiers.
[x] Use only synthetic test values.
[x] Limit live verification to one explicitly authorized synthetic request after offline checks.
```

## 11. Prompt Injection Protection

The diagnostic path receives only a fixed internal enum. It never accepts
provider text, email fields, thread content, attachment content, JSON keys,
JSON paths, or exception text, so untrusted instructions cannot reach the log.

## 12. Acceptance Criteria

1. `envelope_invalid` remains the terminal reason code.
2. A classified `DeepSeekEnvelopeError` envelope failure uses one of the six
   fixed envelope details. An unexpected envelope-stage exception or invalid
   caller-owned detail fails closed to `not_applicable`.
3. Non-envelope fallbacks use `detail=not_applicable`.
4. Exactly one event is written for every fallback attempt.
5. Invalid caller-owned detail values fail closed without entering the log.
6. Public API, SQLite, frontend, provider request, prompt, and fallback remain
   unchanged.
7. Focused tests, full unit discovery, static/architecture/mechanical checks,
   documentation tests, status generation, maintenance scan, JavaScript syntax,
   and `git diff --check` pass.
8. At most one authorized synthetic DeepSeek request is made after offline
   verification.

## 13. Test Plan

- Add RED parser tests for every detail boundary.
- Add RED route tests for detail propagation and exact fallback preservation.
- Add RED logger/filter tests for the revised template, canonicalization, and
  rejection of unsafe records.
- Add documentation/static contract tests.
- Run focused suites, then the complete repository verification sequence.
- Restart the managed service only after offline checks and make one synthetic
  `example.test` analysis request.

## 14. Rollback Plan

Revert the subdiagnostic changes. If provider operation must stop independently,
set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the service.

## 15. Human Confirmation Needed

- The user approved the allowlisted envelope-subdiagnostic direction and
  explicitly authorized a synthetic API call.
- The user reviewed and approved the written design on 2026-07-14.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status and required tooling, architecture, linter, documentation, logging, and existing diagnostic documents have been read.
[x] Goal, non-goals, security boundaries, and acceptance criteria are explicit.
[x] No real mailbox, real email, API key, provider output, or customer data will be logged.
[x] Expected file scope is identified.
[x] Written design has been reviewed by the user.
```

## 17. Execution Record

Implementation state:

- The approved runtime Tasks 1-3 are implemented and committed.
- The Task 4 operator/API/design/task/plan contract synchronization and its
  documentation-only fix pass are implemented and committed.
- Task 5 offline verification is implemented with
  `EMAIL_AGENT_LLM_PROVIDER=disabled`; no API call, service restart, mailbox
  access, or live verification occurred.
- Task 6 synthetic live verification is verified from exactly one authorized
  synthetic request. The isolated service was stopped after the result, and no
  provider output, response body, secret, prompt, or raw exception was recorded.

```text
Actual modified files:
- backend/email_agent/analysis_diagnostics.py
- backend/email_agent/analysis_model_routes.py
- backend/email_agent/deepseek_analysis_schema.py
- backend/email_agent/deepseek_envelope_errors.py
- backend/email_agent/logging_config.py
- docs/api/backend_api_contract.md
- docs/conventions/logging.md
- docs/operations/deepseek_envelope_subdiagnostics_task_brief.md
- docs/operations/deployment_notes.md
- docs/operations/project_status_log.md
- docs/operations/troubleshooting.md
- docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md
- docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md
- tests/test_analysis_diagnostics.py
- tests/test_analyzer.py
- tests/test_deepseek_analysis_schema.py
- tests/test_deepseek_documentation_contracts.py
- tests/test_logging_config.py
- tests/test_static_linter_constraints.py

Local-only verification artifacts:
- .superpowers/sdd/task-5-report.md
- .superpowers/sdd/task-6-report.md
- outputs/cleanup_report.md

Test results:
- Focused Python suites: 104/104 passed in 4.782s with the provider disabled.
- Initial full discovery: 704/704 passed in 42.720s with the provider disabled.
- JavaScript syntax: 7/7 frontend files passed.
- Audited architecture constraints: 11/11 passed in 0.394s.
- Pre-generation git diff check: passed with no output.
- Project status generation: passed; the generated branch field names
  `codex/deepseek-envelope-subdiagnostics`.
- Post-generation full discovery: 704/704 passed in 45.704s with the provider
  disabled.
- Maintenance scan: passed with no cleanup findings detected.
- Final git diff check: passed with no output.
- Final pre-commit status: only this task brief, the generated project status
  log, and the implementation plan are modified; local reports remain ignored.
- Task 6 release, service-health, and non-sensitive route preflight: passed.
- API call count: exactly 1; no retry was made.
- The log baseline was 0 lines and exactly 1 new canonical fallback event was
  isolated; the dedicated service was stopped afterward.
- Synthetic live verification: engine=Rule fallback; code=envelope_invalid; stage=envelope; detail=analysis_shape; elapsed_ms=9859.
- Live status: verified.
- Final post-live project status generation: passed; regeneration produced no
  additional project-status diff.
- Final post-live full discovery: 704/704 passed in 41.722s with the provider
  explicitly disabled.
- Final post-live maintenance scan: passed with no cleanup findings detected.
- Final post-live git diff check: passed with no output; only the intended task
  brief, design, and implementation plan remain modified.

Unfinished items:
- A separate root-cause correction scoped to the observed `analysis_shape`
  boundary.

Follow-up recommendation:
- Scope a new task to the `analysis_shape` boundary. Do not change the prompt,
  provider route, runtime, or tests as part of this verification record.
```
