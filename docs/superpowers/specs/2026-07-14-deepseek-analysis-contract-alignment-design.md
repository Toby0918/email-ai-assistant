---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# DeepSeek Analysis Contract Alignment Design

## Decision Summary

Align the private `deepseek_analysis_v1` validator and the DeepSeek system
prompt behind one shared analysis-contract source. Keep the strict validator,
one-call provider route, deterministic rule fallback, public API, SQLite,
retry, model authority, and human-review boundaries unchanged.

The user approved Approach 1 and this written specification on 2026-07-14.
Implementation remains offline and uses a disabled provider; approval does not
authorize a DeepSeek request.

### Task 5 supersession note

The later master Task 5 in
`docs/superpowers/plans/2026-07-14-authorized-mailbox-ingest-knowledge-deepseek.md`
supersedes this earlier design only for three implementation concerns:

1. both remote DeepSeek routes must cross a local deidentification and residual
   gate, with optional bounded approved runtime knowledge;
2. both frontend surfaces must carry the approved persistent pre-click remote
   processing disclosure; and
3. synchronous budgets are exactly browser/local-debug POST 15 seconds,
   backend 13 seconds, provider cap 10 seconds, and minimum remaining provider
   budget 5 seconds, while the response margin remains 2 seconds and parser
   maximum remains 8 seconds.

The canonical schema/prompt contract, strict fail-closed validation, one-call
provider request shape, public interfaces, and no-live-call boundary in this
design remain authoritative. Task 5 adds only a backend-only immutable
`runtime_cards=()` seam for already verified `RuntimeKnowledgeCard` tuples; it
does not define snapshot paths, keys, authority/vault access, or frontend
fields. Privacy refusals reuse `safety_rejected_all`/`safety`; low-budget
refusals reuse `budget_exhausted`/`budget`.

## Problem And Evidence

The authorized synthetic DeepSeek verification completed in `9,859 ms` and
returned one canonical fallback event with:

```text
code=envelope_invalid stage=envelope detail=analysis_shape
```

That result proves the provider response completed with non-empty content,
decoded as JSON, contained the exact private-envelope top-level fields, and
used the correct `deepseek_analysis_v1` version. One or more requirements
inside `analysis` then failed. Attachment and evidence validation had not yet
started.

The exact offending field is intentionally unavailable. Provider responses,
JSON keys, paths, values, exception text, prompts, and email content are not
logged or persisted. This design preserves that boundary.

The local cause is a contract-alignment gap:

- The provider request uses `response_format={"type":"json_object"}`. DeepSeek
  JSON Output guarantees valid JSON, not conformance to the private nested
  schema. The official guide requires the prompt to describe and exemplify the
  desired JSON shape.
- The current system prompt contains one valid example but does not explicitly
  state all exact-key rules, complete enum domains, the no-`null` rule, or the
  `next_steps` cardinality of 1 to 4.
- The prompt example uses `source:"thread"`, while safe projection requires a
  request-local source ID such as `thread:0`.
- The prompt example always contains `open:0` and `attachment:0` placeholders,
  even when the request has no matching open item or parsed attachment.
- The prompt documentation says to use `unknown` or empty arrays when unsure,
  but `unknown` is not valid for every enum and `next_steps` may not be empty.
- Existing offline evaluation injects already-valid, hand-built envelopes. It
  verifies parsing, grounding, safety, merge, language, and fallback behavior,
  but not whether a live model can infer the full contract from the prompt.

References:

- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)
- `backend/email_agent/llm_client.py`
- `backend/email_agent/prompt_context.py`
- `backend/email_agent/deepseek_analysis_schema.py`
- `scripts/deepseek_eval_replay.py`
- `docs/operations/deepseek_envelope_subdiagnostics_task_brief.md`

## Goals

1. Make every private `analysis` structural rule visible to the model.
2. Prevent prompt and validator field/enum contracts from drifting apart.
3. Remove contradictory placeholder sources from the complete example.
4. Preserve strict local validation and exact rule fallback on any invalid,
   unsafe, ungrounded, late, or incomplete provider result.
5. Add an offline quality gate that fails when the prompt contract and
   validator contract diverge.

## Non-Goals

- Do not guarantee that every generated response will be accepted.
- Do not loosen, repair, normalize, or guess missing provider fields.
- Do not add a retry, second provider call, second model, or asynchronous job.
- Do not change the provider endpoint, model, `max_tokens`, thinking mode,
  output mode, `response_format`, retry count, or no-tools request shape.
- Do not adopt DeepSeek strict function calling or the beta endpoint.
- Do not change the public analysis schema, API, SQLite, renderer fields,
  attachment parsing, mailbox scope, or mailbox actions. Frontend changes are
  limited to the approved disclosure and 15-second analysis POST timeout.
- Do not add snapshot/key/bootstrap configuration, vault access, Task 6
  evaluation behavior, or a public runtime-card input.
- Do not log or persist the raw/private provider response, private envelope,
  or finer field-level diagnostics. The validated safe public projection
  continues to use the existing SQLite path.
- Do not use a real mailbox, real email, real attachment, or customer data.

## Considered Approaches

### Approach 1: Shared contract source plus generated prompt guidance

This is the approved approach.

- Add one small private contract module.
- Reuse its structural constants in the validator.
- Render the system prompt's structural rules from the same constants and the
  existing public enum constants.
- Keep the parser fail-closed and add parity tests.

This is slightly larger than a prose-only change, but it prevents the same
drift from recurring and fits the current dependency and architecture rules.

### Approach 2: Append more hand-written prompt prose

Rejected. It is the smallest immediate diff, but the prompt, example, and
validator would remain three independently maintained contracts. A future
schema change could silently reintroduce the same failure.

### Approach 3: DeepSeek strict function calling with JSON Schema

Deferred to a separate architecture decision. DeepSeek documents strict
function calling as a beta feature requiring the `/beta` endpoint and a tool
definition. It would change the fixed endpoint, response extraction,
finish-reason handling, provider contract, and current no-tools design.

Reference:

- [DeepSeek strict tool mode](https://api-docs.deepseek.com/guides/tool_calls)

Parser-side repair or enum normalization is explicitly rejected because it
would accept meanings the provider did not express within the approved
contract and would weaken the existing fail-closed boundary.

## Architecture

The shared dependency direction is:

```text
analysis_schema.py public enum constants
                    |
                    v
deepseek_analysis_contract.py
        |                         |
        v                         v
deepseek_analysis_schema.py   prompt_context.py
strict local validation       fixed system prompt
```

`deepseek_analysis_contract.py` is pure, static, backend-only data. It does
not receive email content, call a provider, log data, or persist data. It
exists because both current consumer files are already near the project's
300-line guidance and because a separate module provides one testable contract
boundary.

## Component Design

### Shared private contract module

The new module owns the private schema version and exact structural field sets
used by both the validator and prompt renderer. Expected field groups include:

- envelope
- analysis
- decision brief
- next step
- key fact
- reply recommendation
- timeline interpretation
- open-item annotation
- risk
- suggested action
- reply draft
- attachment augmentation
- approved `field_evidence` JSON-pointer patterns

The module imports the existing public priority, category, risk, action,
reply-type, and confidence enum sets from `analysis_schema.py`; it does not
duplicate those values. It also owns `APPROVED_EVIDENCE_PATTERNS`, which the
validator imports and re-exports for compatibility while the prompt renderer
uses the same patterns as its complete target allowlist.

It also owns the complete private-envelope example and a compact rendered
analysis-shape instruction. With a synthetic source registry containing only
`thread:0`, the example must pass both `validate_deepseek_analysis_v1()` and
`validate_envelope_evidence()`. Every field set, enum, and evidence pattern is
rendered in sorted order so the system prompt is deterministic across
processes. The complete fixed system prompt must remain at or below 8,000
characters to prevent accidental contract bloat inside the existing
synchronous timeout path.

### Strict private validator

`deepseek_analysis_schema.py` consumes the shared version and field-set
constants. Its observable behavior is unchanged:

- every required key remains required;
- every extra key remains rejected;
- `null` remains rejected where a string, list, object, or boolean is required;
- enum membership remains exact;
- `next_steps` remains limited to 1 through 4 entries;
- `needs_human_review` remains exactly `true`;
- duplicate JSON keys and all existing evidence checks remain fail-closed.

No tolerant normalization layer is added before validation.

### DeepSeek system prompt

`prompt_context.py` imports the shared example and structural instruction while
retaining the existing untrusted-input, grounding, language, commitment, and
mailbox-action protections.

The delivered system prompt explicitly states:

1. All listed object keys are required; no key may be added or omitted.
2. `null` is never a substitute for a required string, list, object, or
   boolean.
3. Every enum domain is complete and uses the existing English machine values.
4. `decision_brief.next_steps` contains 1 to 4 exact objects.
5. Lists may be empty only where the validator permits an empty list.
6. `reply_draft.needs_human_review` is always `true`.
7. `next_steps[].source` and `key_facts[].source` use an exact request-local
   source ID from the supplied `sources` collection, such as `thread:0`.
8. `open_item_annotations` contains only IDs supplied in the timeline skeleton;
   it is empty when no matching ID exists.
9. `attachment_augmentations` contains only supplied parsed attachment source
   IDs; it is empty when there is no parsed attachment.
10. `field_evidence` uses only supplied source IDs and approved text targets.

The complete example uses `thread:0`, an empty attachment augmentation list,
and an empty open-item annotation list. It does not invite the model to copy a
nonexistent attachment or open-item placeholder.

### Documentation

`docs/prompts/analyzer_prompt.md` will distinguish valid JSON from private
schema conformance and list the private analysis rules above.

`docs/data/analysis_result_schema.md` will clarify that `unknown` is used only
for enums that explicitly include it and that empty arrays are used only where
the corresponding schema permits them. `next_steps` always contains 1 to 4
items.

The task brief, implementation plan, and generated project status will record
the bounded scope and verification evidence.

## Data Flow

The Task 5 runtime flow is:

```text
user click after persistent remote-processing disclosure
-> bounded current-visible-email context and optional verified runtime cards
-> build the existing local prompt
-> locally deidentify the complete outbound prompt and scan residuals
-> close the resolver and retain only a plain string
-> one DeepSeek JSON-object request when at least 5 seconds remain
-> reject placeholders, restoration attempts, or private markers before parsing
-> strict deepseek_analysis_v1 parsing
-> evidence, grounding, language, and safety checks
-> safe public merge or complete rule fallback
-> user-reviewed draft only
```

Externally observable changes are limited to the persistent disclosure and the
15-second frontend analysis POST timeout. The remote user prompt is now locally
deidentified and may include at most eight whole approved knowledge cards in at
most 4,000 rendered characters. The provider request count, fixed endpoint,
model, JSON-object body contract, public response, SQLite projection, and
renderers remain unchanged.

## Error Handling And Safety

- Any structural mismatch continues to return the complete deterministic rule
  result and one sanitized terminal fallback event.
- No invalid result is partially repaired before validation.
- No retry is made after a provider, response, envelope, evidence, grounding,
  safety, schema, or language failure.
- No raw/private provider response, private envelope, JSON key/path/value,
  prompt, email, attachment, exception, key, token, URL, or customer identifier
  enters logs or SQLite. The existing validated safe public analysis projection
  may continue to be persisted to SQLite.
- Prompt injection remains untrusted email data and cannot alter the system
  contract or authorize tools or mailbox actions.
- Provider-authored commitments, unsafe actions, unsupported critical facts,
  and ungrounded sources remain subject to the existing field-level or complete
  fallback rules after structural validation.

The patch improves structural adherence. It does not make semantic model output
authoritative and does not replace human review.

## Testing Strategy

Implementation uses TDD with synthetic data only.

1. Add a failing prompt-contract parity test before production changes. It
   checks the exact structural groups, complete enum domains, no-extra/no-null
   rules, `next_steps` cardinality, and mandatory review flag.
2. Add failing example tests proving all request-local sources are consistent
   and that the neutral example has no fabricated attachment or open-item ID.
   With a synthetic `{"thread:0": object()}` registry, the example must pass
   both structural and evidence validation. The tests also require
   deterministic ordering and enforce the 8,000-character fixed-system-prompt
   ceiling.
3. Move the private structural constants into the shared module and update the
   validator without changing validation behavior.
4. Render the prompt guidance from the shared contract and make the RED tests
   pass.
5. Add an offline production-route regression using a synthetic no-attachment
   email and a contract-compliant injected envelope. It must produce
   `analysis_engine.source=ai_model` without network access.
6. Retain existing malformed and `analysis_shape` fallback tests to prove the
   strict rejection path is unchanged.
7. Update documentation-contract tests.
8. Add RED coverage for the private gate, runtime-card limits, both DeepSeek
   modes, provider-output refusal, exact local key facts, budgets, disclosure,
   dependency allowlists, and public/storage/render/log/exception canaries.
9. Run the focused prompt, private-schema, gate, knowledge, analyzer, budget,
   provider-client, frontend, documentation, architecture, static, and public
   interface tests with the provider disabled.
10. Run the 50-case offline evaluation, full unit discovery, JavaScript syntax
    checks, architecture/static/mechanical/transport checks, `git diff --check`,
    and maintenance scan. Project-status generation is deferred to Task 7 by
    the authorized-ingest master plan.

Tests may not inspect a real key, call a provider, read a real mailbox, or use
real email or attachment content.

## Controlled Live Verification

Live verification is not authorized by approval of this design. After all
offline gates pass, ask separately for permission to make exactly one
DeepSeek request using only:

- one synthetic `example.test` sender and recipient;
- one synthetic purchase-order reference and date;
- no attachment;
- no mailbox connection or customer content;
- the existing backend-only configured key without printing or inspecting it.

If authorized, isolate exactly one new canonical event. Success is an accepted
DeepSeek engine result with no fallback event. Any fallback or request failure
is recorded only by fixed engine/code/stage/detail/elapsed fields; no retry is
made. A second live request requires new explicit authorization.

## Acceptance Criteria

1. Prompt and validator consume one private structural contract source,
   including the approved `field_evidence` target patterns.
2. The system prompt explicitly represents every `analysis_shape` key, type,
   enum, cardinality, and mandatory boolean rule.
3. With a synthetic registry containing only `thread:0`, the complete example
   passes both production structural and evidence validators and contains no
   nonexistent attachment/open-item placeholder or non-local source alias.
4. Contract rendering is deterministic and the complete fixed system prompt
   is no longer than 8,000 characters.
5. The strict private validator accepts and rejects the same envelopes as
   before this refactor.
6. Both DeepSeek routes locally deidentify the complete outbound prompt, close
   the resolver before the client, enforce 8-card/4,000-character whole-card
   limits, and reject unsafe provider output before either parser.
7. Budgets are exactly 15/13/10/5 with 2-second response margin and 8-second
   parser maximum; the DeepSeek provider request shape and single-call/no-retry
   behavior remain unchanged.
8. Public API, SQLite projection, renderer fields, diagnostics schema, disabled
   defaults, Ollama behavior, model authority, and rule fallback remain
   unchanged.
9. Invalid, residual-bearing, late, placeholder-bearing, or unsafe output
   remains fail-closed without raw-output logging.
10. Focused, offline evaluation, full-suite, documentation, static,
    architecture, mechanical, transport, JavaScript, maintenance, and diff
    checks pass with the provider disabled; status generation remains deferred
    to Task 7.
11. No live DeepSeek request occurs without separate explicit authorization.

## Rollback

Revert the shared contract, prompt, validator-constant, tests, and documentation
commits. The provider can be disabled independently with
`EMAIL_AGENT_LLM_PROVIDER=disabled`; deterministic rule analysis remains
available throughout.
