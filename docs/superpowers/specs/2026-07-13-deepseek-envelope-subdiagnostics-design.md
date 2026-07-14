---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# DeepSeek Envelope Subdiagnostics Design

## Decision Summary

Extend the existing backend-only `analysis_fallback` event with one fixed,
allowlisted `detail` field. Keep `code=envelope_invalid` and
`stage=envelope` unchanged while distinguishing the safe structural boundary
that rejected the provider response.

The user selected this direction on 2026-07-13 after a synthetic DeepSeek
request completed in `10,187 ms` and produced
`code=envelope_invalid stage=envelope`. The patch must not record the provider
response, JSON keys, field values, exception text, prompt, email, attachment,
API key, URL, path, or customer information.

## Approval And Implementation Status

The user approved this design on 2026-07-14. Runtime Tasks 1-3, the Task 4
operator documentation contract, and Task 5 offline verification are
implemented. Task 6 is verified from exactly one authorized synthetic request:
the result used Rule fallback with `code=envelope_invalid`, `stage=envelope`,
and `detail=analysis_shape`. The separate root-cause correction remains
unfinished and is not part of this verification task. The final post-live full
suite and maintenance scan also passed with the provider explicitly disabled.

## Evidence And Root-Cause Boundary

The live diagnostic proves that the configured DeepSeek request passed the
provider, completion-reason, and non-empty-content checks before the private
envelope parser rejected the returned string. It does not identify the exact
failed structural boundary because all private-envelope failures currently
collapse to one generic `DeepSeekEnvelopeError`.

The strict parser checks JSON syntax and duplicate keys, exact top-level keys,
the exact schema version, the complete nested analysis shape and enums,
attachment augmentation shape, and field-evidence shape. Raw provider output
is intentionally neither logged nor persisted, so the completed request cannot
be inspected further without adding a content-free subdiagnostic.

## Considered Approaches

### Approach A: Add one fixed detail field to the existing terminal event

This is the approved approach.

- Preserve `code=envelope_invalid` and `stage=envelope`.
- Add one exact built-in string selected from a closed allowlist.
- Emit the detail in the same canonical terminal event.
- Use `not_applicable` for every non-envelope fallback.
- Preserve one event per fallback attempt.

This keeps current aggregation stable and provides enough evidence for the next
root-cause correction without exposing provider content.

### Approach B: Replace envelope_invalid with several new reason codes

Rejected. It would avoid adding an event field but would break current
aggregation by `code=envelope_invalid` and weaken continuity with the first
diagnostic result.

### Approach C: Record the provider response or validation path

Rejected. Provider output, key sets, field paths, exception text, or values can
contain or reproduce untrusted email and attachment content. They are outside
the project logging boundary.

## Diagnostic Contract

The canonical event becomes:

```text
event=analysis_fallback code=<allowlisted code> stage=<allowlisted stage> provider=<allowlisted provider> model=<allowlisted model> output_mode=<allowlisted mode> detail=<allowlisted detail> elapsed_ms=<non-negative integer>
```

The detail allowlist is exactly:

```text
not_applicable
json_syntax
top_level_shape
schema_version
analysis_shape
attachment_shape
field_evidence_shape
```

The detail allowlist is not_applicable, json_syntax, top_level_shape,
schema_version, analysis_shape, attachment_shape, and field_evidence_shape.
Every non-envelope fallback uses not_applicable. This operator-only log field
is not added to the public API or SQLite, and it must never contain or be used
to reconstruct provider output, JSON keys, paths, values, or exception text.

Meanings:

- `json_syntax`: JSON decoding, unsupported raw type, duplicate object key,
  recursion, or Unicode decoding failed before a trusted object existed.
- `top_level_shape`: the decoded value was not an object or did not contain
  exactly the four private-envelope top-level fields.
- `schema_version`: the top-level object existed but the version was not
  exactly `deepseek_analysis_v1`.
- `analysis_shape`: the `analysis` object or any of its nested objects, lists,
  booleans, counts, strings, or fixed enum values failed validation.
- `attachment_shape`: `attachment_augmentations` or one of its exact items
  failed structural validation.
- `field_evidence_shape`: `field_evidence` was not a string-keyed object of
  string lists.
- `not_applicable`: the fallback was not an envelope parse failure, or an
  invalid caller-owned detail was canonicalized closed.

The patch intentionally stops at these coarse structural boundaries. It does
not log a failed field name, JSON pointer, unknown enum value, key set, array
index, object representation, or exception.

## Component Design

### Private envelope parser

`DeepSeekEnvelopeError` gains one internal allowlisted detail value while
retaining the same generic public-safe exception string and suppressed cause.
The parser assigns a detail only at the six boundaries above. Existing
validation semantics remain fail-closed; no missing field is repaired, no
unknown field is dropped, and no enum is normalized.

### Analysis route

The envelope route preserves the parser detail in the internal terminal
fallback object. Every other fallback uses `not_applicable`. The complete rule
fallback returned to the public API remains unchanged.

### Diagnostic sink

`analysis_diagnostics.py` owns the detail allowlist and canonicalizes the value
before logging. The dedicated handler accepts only the revised exact template,
the exact built-in allowlisted argument tuple, no exception/stack state, and a
non-negative built-in integer. Non-envelope codes are forced to
`detail=not_applicable` even if a caller supplies another value.

The event remains operator-only in `outputs/local_debug_service.log`. It does
not enter the public API, SQLite, frontend, or model context.

## Public, Persistence, And Provider Boundaries

- No public request or response change.
- No SQLite schema or stored-analysis change.
- No frontend change.
- No provider request, timeout, retry, model, or endpoint change.
- No prompt or private envelope schema change.
- No rule fallback or model-authority change.
- No dependency change.
- No raw output or exception logging.

## Testing Strategy

Use TDD with synthetic values only:

1. Parser tests fail first for each safe detail category while preserving the
   exact generic error message and absent exception cause.
2. Route tests prove the parser detail reaches exactly one terminal event and
   that the returned analysis remains the exact rule fallback.
3. Diagnostic tests prove invalid details and non-envelope details canonicalize
   to `not_applicable`.
4. Handler tests prove only the revised exact template and exact argument types
   can reach the dedicated sink; exception, stack, string subclass, boolean,
   free-form, SDK, HTTP, and application records remain rejected.
5. Documentation and static/mechanical tests enforce the new contract.
6. Focused tests, full unit discovery, status generation, maintenance scan,
   JavaScript syntax checks, and `git diff --check` run before completion.

## Controlled Live Diagnostic

After offline verification, restart the local service and make at most one
user-authorized DeepSeek request using only a synthetic `example.test` email,
no attachment, no real mailbox, and no customer content. The request may use
the configured backend key but must never print or inspect it.

Read only the newest canonical event. If the result remains
`code=envelope_invalid`, use its fixed detail as evidence for a separate prompt
or parser correction. Do not bundle that correction into this diagnostic patch.
If the model is accepted, record only the public engine label and the absence
of a fallback event.

## Acceptance Criteria

1. Every fallback still emits exactly one canonical terminal event.
2. `code=envelope_invalid` remains stable and includes one of the six specific
   envelope details.
3. Every non-envelope fallback emits `detail=not_applicable`.
4. No provider response, key, JSON key/path/value, prompt, email, attachment,
   raw exception, traceback, URL, path, or customer identifier is logged.
5. Public API, SQLite, frontend, prompt, provider request, and deterministic
   fallback behavior are unchanged.
6. All focused and full repository checks pass without a live call.
7. At most one post-verification synthetic live call is made under the user's
   explicit authorization.

## Rollback

Revert the parser-detail, route, logger, tests, and documentation commits. The
provider can be independently disabled with `EMAIL_AGENT_LLM_PROVIDER=disabled`
and a service restart; rule analysis remains available throughout.
