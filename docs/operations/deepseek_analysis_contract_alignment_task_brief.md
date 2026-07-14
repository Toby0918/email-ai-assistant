---
last_update: 2026-07-14
status: draft
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Analysis Contract Alignment Task Brief

## 1. Task Name

```text
align the DeepSeek analysis prompt with the strict private validator
```

## 2. Task Type

```text
fix
```

Prompt, security, test, and documentation updates are supporting concerns of
this single fix.

## 3. Current Status

```text
draft
```

The user approved Approach 1 on 2026-07-14. The committed written design still
requires user review before implementation planning; implementation and live
API verification have not started.

## 4. Goal

Use one shared private analysis contract for the DeepSeek prompt and strict
validator so the model receives every required key, type, enum, cardinality,
source-ID, and mandatory-review rule without weakening fail-closed fallback.

## 5. Non-Goals

- Do not loosen or normalize invalid provider output.
- Do not add retries, a second provider call, asynchronous work, or a second
  model.
- Do not change the DeepSeek endpoint, model, timeout, token budget, thinking
  mode, or JSON-object request mode.
- Do not adopt strict function calling or a beta provider endpoint.
- Do not change the public API, SQLite, frontend, extension, mailbox scope,
  attachment parser, or model authority.
- Do not log or persist raw/private provider responses, private envelopes,
  JSON paths/values, prompts, emails, attachments, exceptions, keys, tokens,
  URLs, or customer identifiers. Preserve existing persistence of the
  validated safe public analysis projection.
- Do not call DeepSeek during implementation or automated verification.
- Do not use real mailbox, email, attachment, customer, supplier, or employee
  data.

## 6. Background And References

One authorized synthetic request completed in `9,859 ms` but returned the
complete rule fallback with `code=envelope_invalid`, `stage=envelope`, and
`detail=analysis_shape`. Offline inspection found that the provider is asked
for a JSON object while the system prompt does not completely state the strict
nested analysis contract enforced after the call.

References:

- `AGENTS.md`
- `docs/superpowers/specs/2026-07-14-deepseek-analysis-contract-alignment-design.md`
- `docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md`
- `docs/operations/deepseek_envelope_subdiagnostics_task_brief.md`
- `docs/prompts/analyzer_prompt.md`
- `docs/data/analysis_result_schema.md`
- `docs/security/api_key_rules.md`
- `docs/security/email_data_handling.md`
- `docs/security/prompt_injection_rules.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

## 7. Expected Scope

Expected addition:

- `backend/email_agent/deepseek_analysis_contract.py`

Expected modifications:

- `backend/email_agent/deepseek_analysis_schema.py`
- `backend/email_agent/prompt_context.py`
- `tests/test_prompt_context.py`
- `tests/test_deepseek_analysis_schema.py`
- `tests/test_analyzer.py`
- `tests/test_deepseek_documentation_contracts.py`
- `docs/prompts/analyzer_prompt.md`
- `docs/data/analysis_result_schema.md`
- `docs/operations/deepseek_analysis_contract_alignment_task_brief.md`
- `docs/superpowers/plans/2026-07-14-deepseek-analysis-contract-alignment.md`
- `docs/operations/project_status_log.md` through the generator after
  implementation

No `llm_client.py`, provider configuration, frontend, API, database,
attachment parser, or mailbox integration change is expected.

## 8. Technical Approach

1. Add a pure backend contract module containing the private version, exact
   structural field sets, approved evidence-target patterns, complete valid
   example, and rendered prompt rules.
2. Import public enum domains from `analysis_schema.py` instead of duplicating
   values.
3. Make the private validator consume the shared structural constants without
   changing accepted or rejected behavior.
4. Make the DeepSeek system prompt consume the same contract and explicitly
   state exact keys, complete enum domains, no `null`, 1-to-4 `next_steps`,
   request-local sources, conditional open-item annotations, conditional
   attachment augmentations, and mandatory human review.
5. Correct the complete example to use `thread:0` and no fabricated
   attachment/open-item placeholder.
6. Update Prompt and schema documentation and enforce parity through tests.
7. Render field names and enum values deterministically and keep the complete
   fixed system prompt within an 8,000-character ceiling.

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
None. The existing deepseek_analysis_v1 contract becomes explicit to the model.
```

### Prompt Changes

```text
Yes. The fixed backend-only DeepSeek system prompt will render the complete
private analysis contract from shared constants.
```

### Provider Request Changes

```text
None.
```

## 10. Security And Privacy Check

```text
[x] Do not access real mailbox data.
[x] Do not automatically send, delete, archive, move, forward, or reply to email.
[x] Keep DeepSeek/OpenAI keys and provider configuration backend-only.
[x] Continue treating email, thread, and attachment fields as untrusted input.
[x] Preserve parseable, strictly validated AI JSON requirements.
[x] Preserve grounding, language, commitment, action, and human-review safeguards.
[x] Do not log or persist raw/private provider responses, private envelopes, or sensitive content.
[x] Preserve existing SQLite persistence of the validated safe public projection.
[x] Use synthetic-only tests and offline injected generators.
[x] Perform no live provider call during implementation or automated verification.
```

## 11. Prompt Injection Protection

- Email and attachment content remains untrusted data in the user message.
- The static system contract does not execute instructions, links, scripts,
  macros, commands, or tools found in that data.
- The provider receives no mailbox tools or mailbox-action authority.
- Prompt content cannot disclose keys, other messages, databases, or system
  internals.
- Provider text cannot create an unconditional price, delivery, payment,
  contract, quality, or legal commitment.
- Existing grounding and universal provider-text safety checks remain after
  structural validation.

## 12. Acceptance Criteria

1. Prompt and validator use one shared private structural contract, including
   approved `field_evidence` target patterns.
2. Every `analysis_shape` field, type, enum, exact-key, cardinality, and
   mandatory boolean rule is explicitly represented in the system prompt.
3. With a synthetic registry containing only `thread:0`, the complete example
   passes both production structural and evidence validators and uses no
   fabricated attachment/open-item entries.
4. Contract rendering is deterministic and the complete fixed system prompt
   is no longer than 8,000 characters.
5. Validator behavior remains strict and backward compatible.
6. Invalid output still returns the exact complete rule fallback and one
   sanitized terminal event.
7. Public API, SQLite, frontend, provider request, timeout, retries, and model
   authority are unchanged.
8. Prompt and schema documentation match production behavior.
9. All required offline checks pass with the provider disabled.
10. No DeepSeek call occurs without a new explicit authorization.

## 13. Test Plan

- Write the prompt/validator parity test first and confirm RED.
- Write example source-consistency and no-placeholder tests first and confirm
  RED.
- Add deterministic-rendering and 8,000-character prompt-ceiling assertions.
- Add validator behavior-parity coverage for all shared field groups.
- Add an offline production-route no-attachment regression with an injected,
  contract-compliant envelope.
- Retain malformed and `analysis_shape` fallback coverage.
- Run focused prompt, private-schema, analyzer, provider-client,
  documentation-contract, and evaluator tests.
- Run the 50-case DeepSeek offline evaluator.
- Run full `python -m unittest discover -s tests` with the bundled Python
  runtime and provider explicitly disabled.
- Run JavaScript syntax, architecture, static, mechanical, documentation,
  `git diff --check`, status generation, and maintenance checks required by
  the repository.
- After all offline gates, request separate permission for at most one
  synthetic live verification call.

## 14. Rollback Plan

Revert the contract module, prompt, validator-constant, tests, and documentation
commits. Independently set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the
service if the provider route must be stopped; rule analysis remains available.

## 15. Human Confirmation Needed

- The user approved Approach 1 on 2026-07-14.
- The user must review this written design before implementation planning.
- The user must separately authorize any post-implementation DeepSeek call.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status and required tooling, architecture, linter, task-brief, and documentation rules have been read.
[x] Relevant DeepSeek prompt, schema, route, diagnostics, and offline evaluator files have been inspected.
[x] Goal, non-goals, security boundaries, and acceptance criteria are explicit.
[x] No real mailbox, email, attachment, API key, or customer data will be read or logged.
[x] Expected file scope is identified.
[ ] The user has reviewed and approved the written design document.
```

## 17. Execution Record

```text
Actual modified files:
- docs/operations/deepseek_analysis_contract_alignment_task_brief.md
- docs/superpowers/specs/2026-07-14-deepseek-analysis-contract-alignment-design.md

Test results:
- Design-document checks pending before commit.

Live API calls:
- 0 for this task.

Unfinished items:
- User written-design review.
- Implementation plan.
- TDD implementation and offline verification.
- Optional separately authorized single synthetic live verification.

Follow-up recommendation:
- After written-design approval, create the implementation plan with the
  Superpowers writing-plans workflow.
```
