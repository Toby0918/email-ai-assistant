---
last_update: 2026-07-13
status: draft
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
draft
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
2. The same event contains one of the six fixed envelope details.
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
- The written design must still be reviewed before implementation begins.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status and required tooling, architecture, linter, documentation, logging, and existing diagnostic documents have been read.
[x] Goal, non-goals, security boundaries, and acceptance criteria are explicit.
[x] No real mailbox, real email, API key, provider output, or customer data will be logged.
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
- Written-design review.
- Implementation and offline verification.
- One authorized synthetic live diagnostic.

Follow-up recommendation:
- Use the observed fixed detail to scope a separate root-cause correction.
```
