---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Analysis Contract Alignment Task Brief

## 1. Task Name

```text
align and privately gate the DeepSeek analysis contract
```

## 2. Task Type

```text
security
```

Prompt, provider-boundary, budget, frontend disclosure, test, architecture,
and documentation updates are supporting concerns of this single security fix.

## 3. Current Status

```text
implemented
```

The user approved the written design and Task 5 implementation on 2026-07-14.
The later master Task 5 supersedes the earlier design only for the private
outbound gate, persistent disclosure, and exact 15/13/10/5 budgets. Offline TDD
implementation is authorized; live API verification remains unauthorized.

## 4. Goal

Use one shared private analysis contract for the DeepSeek prompt and strict
validator, then gate both DeepSeek routes behind local deidentification,
residual scanning, bounded approved runtime knowledge, and provider-output
privacy checks without weakening fail-closed fallback or public interfaces.

## 5. Non-Goals

- Do not loosen or normalize invalid provider output.
- Do not add retries, a second provider call, asynchronous work, or a second
  model.
- Do not change the DeepSeek endpoint, model, token budget, thinking mode,
  JSON-object request mode, no-tools shape, zero-retry rule, or single-call rule.
- Do not adopt strict function calling or a beta provider endpoint.
- Do not change the public API, SQLite projection, renderer fields, mailbox
  scope, attachment parser, or model authority. Frontend changes are limited to
  the exact persistent disclosure and 15-second analysis POST timeout.
- Do not add environment variables, snapshot paths, key loading, authority or
  vault access, DPAPI/BitLocker work, frontend runtime-card fields, or Task 6.
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

Expected additions:

- `backend/email_agent/deepseek_analysis_contract.py`
- `backend/email_agent/private_context_gate.py`
- `backend/email_agent/private_knowledge_context.py`
- `tests/test_private_context_gate.py`
- `tests/test_private_knowledge_context.py`
- `docs/superpowers/plans/2026-07-14-deepseek-analysis-contract-alignment.md`

Expected modifications:

- `backend/email_agent/deepseek_analysis_schema.py`
- `backend/email_agent/prompt_context.py`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/analysis_model_routes.py`
- `backend/email_agent/model_result_safety.py`
- `backend/email_agent/analysis_budget.py`
- `backend/email_agent/config.py`
- `backend/email_agent/llm_client.py`
- `frontend/browser_extension/shared/api_client.js`
- `frontend/browser_extension/popup.html`
- `frontend/local_debug_page/app.js`
- `frontend/local_debug_page/index.html`
- `.env.example`
- `scripts/deepseek_eval_replay.py`
- `tests/test_prompt_context.py`
- `tests/test_deepseek_analysis_schema.py`
- `tests/test_analyzer.py`
- `tests/test_model_result_safety.py`
- `tests/test_analysis_budget.py`
- `tests/test_config.py`
- `tests/test_llm_client.py`
- `tests/test_browser_extension_static.py`
- `tests/test_browser_extension_task6_contracts.py`
- `tests/test_frontend_local_debug.py`
- `tests/test_architecture_constraints.py`
- `tests/test_static_linter_constraints.py`
- `tests/test_api.py`
- `tests/test_database.py`
- `tests/test_deepseek_documentation_contracts.py`
- `docs/prompts/analyzer_prompt.md`
- `docs/data/analysis_result_schema.md`
- `docs/security/email_data_handling.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/templates/agent_task_brief_template.md`
- `docs/operations/deepseek_analysis_contract_alignment_task_brief.md`

`docs/operations/project_status_log.md` is intentionally excluded because the
authorized-ingest master plan assigns regeneration to Task 7. API/database/
renderer production files, attachment parsing, mailbox ingest, vault, and Task
6 evaluation remain unchanged.

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
6. Add a backend-only immutable `runtime_cards=()` analyzer seam. It accepts
   only already verified `RuntimeKnowledgeCard` tuples (normally supplied by a
   separately controlled bootstrap) and defaults to empty; no loading path is
   invented in this task.
7. At the actual boundary in `analysis_model_routes.py`, gate both DeepSeek
   model-led and conservative prompts. Deidentify the complete outbound prompt,
   include bounded header display-name identity context, scan residuals, close
   the resolver before the client, and permit only a repr-safe plain string to
   escape. Ollama remains local and unchanged.
8. Revalidate and deterministically render at most eight whole runtime cards
   and at most 4,000 characters, omitting all identifiers and metadata.
9. Reject provider placeholders, restoration/reidentification attempts, and
   forbidden private markers before either parser. Reuse
   `safety_rejected_all`/`safety`; use `budget_exhausted`/`budget` below five
   seconds. Do not change the diagnostics schema.
10. Preserve deterministic local `decision_brief.key_facts` byte-for-byte via
   a deep copy after safe model-led projection.
11. Update Prompt and schema documentation and enforce parity through tests.
12. Render field names and enum values deterministically and keep the complete
   fixed system prompt within an 8,000-character ceiling.
13. Set exact budgets to browser/local-debug POST 15 seconds, backend 13,
   provider cap/default 10, and minimum remaining 5, while retaining response
   margin 2 and parser maximum 8.
14. Add the exact persistent pre-click disclosure to popup and local debug.

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
The fixed SDK request shape is unchanged. Only DeepSeek user content is locally
deidentified before the call and may include bounded approved knowledge cards.
The provider timeout cap changes from 25 seconds to 10 seconds.
```

### Runtime Injection Changes

```text
Backend-only keyword seam: runtime_cards=(). No public HTTP field, environment
variable, snapshot path, key source, or vault reader is added.
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
[x] Deidentify the complete DeepSeek outbound prompt locally and fail closed on residuals.
[x] Close and clear the placeholder resolver before the provider boundary.
[x] Keep mappings, placeholders, raw values, card/snapshot/vault IDs, paths, URLs, and binary data out of public, SQLite, renderer, log, diagnostic, and exception surfaces.
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
6. Both DeepSeek modes cross the private gate; disabled and local Ollama routes
   retain existing behavior.
7. The resolver is closed before the single client call; residual, ambiguous,
   context-invalid, late, placeholder-bearing, restoration-bearing, and private
   marker output fail closed with content-free existing diagnostics.
8. Knowledge selection is deterministic, revalidates cards, includes at most
   eight whole cards and 4,000 rendered characters, and emits no identifiers or
   hidden metadata.
9. Exact local key facts survive model-led safe merge byte-for-byte and by deep
   copy.
10. Invalid output still returns the exact complete rule fallback and one
   sanitized terminal event.
11. Public API, SQLite projection, renderer fields, diagnostics schema, retries,
    model authority, and fixed provider request shape are unchanged.
12. Budgets are exactly browser/local-debug 15, backend 13, provider cap 10,
    minimum remaining 5, response margin 2, and parser maximum 8.
13. Both frontend surfaces show the exact approved persistent disclosure before
    click without endpoint or key details.
14. Prompt, schema, security, architecture, linter, and task-template docs match
    production behavior.
15. All required offline checks pass with the provider disabled; project-status
    generation remains deferred to Task 7.
16. No DeepSeek call occurs without a new explicit authorization.

## 13. Test Plan

- Write the prompt/validator parity test first and confirm RED.
- Write example source-consistency and no-placeholder tests first and confirm
  RED.
- Add deterministic-rendering and 8,000-character prompt-ceiling assertions.
- Add validator behavior-parity coverage for all shared field groups.
- Add deidentifier-class, residual, context, resolver-lifecycle, 8/9-card,
  4,000/4,001-character, output-placeholder/restoration, both-route, Ollama,
  local-key-fact, and under-five-second RED tests.
- Add exact 15/13/10/5 budget tests and one-call provider request assertions.
- Add exact persistent-disclosure and narrow dependency-allowlist tests.
- Add public/SQLite/renderer/log/diagnostic/exception canaries proving no Task 4
  identifier, mapping, placeholder, card metadata, or raw value escapes.
- Add an offline production-route no-attachment regression with an injected,
  contract-compliant envelope.
- Retain malformed and `analysis_shape` fallback coverage.
- Run focused prompt, private-schema, analyzer, provider-client,
  documentation-contract, and evaluator tests.
- Run the 50-case DeepSeek offline evaluator.
- Run full `python -m unittest discover -s tests` with the bundled Python
  runtime and provider explicitly disabled.
- Run JavaScript syntax, architecture, static, mechanical, documentation,
  transport, `git diff --check`, and maintenance checks required by the
  repository. Do not regenerate project status until Task 7.
- Make no live verification call in Task 5.

## 14. Rollback Plan

Revert the contract module, prompt, validator-constant, tests, and documentation
commits. Independently set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the
service if the provider route must be stopped; rule analysis remains available.

## 15. Human Confirmation Needed

- The user approved Approach 1, the written design, the master Task 5
  supersession, the empty-default runtime-card seam, and existing-diagnostic
  reuse on 2026-07-14.
- The user must separately authorize any post-implementation DeepSeek call.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status and required tooling, architecture, linter, task-brief, and documentation rules have been read.
[x] Relevant DeepSeek prompt, schema, route, diagnostics, and offline evaluator files have been inspected.
[x] Goal, non-goals, security boundaries, and acceptance criteria are explicit.
[x] No real mailbox, email, attachment, API key, or customer data will be read or logged.
[x] Expected file scope is identified.
[x] The user has reviewed and approved the written design document.
```

## 17. Execution Record

```text
Actual modified files:
- backend/email_agent/deepseek_analysis_contract.py
- backend/email_agent/private_context_gate.py
- backend/email_agent/private_knowledge_context.py
- backend/email_agent/private_analysis_route.py
- backend/email_agent/{analysis_model_routes,analyzer,model_result_safety,prompt_context,deepseek_analysis_schema,analysis_budget,config,llm_client}.py
- frontend/browser_extension/{popup.html,shared/api_client.js}
- frontend/local_debug_page/{index.html,app.js}
- scripts/deepseek_eval_replay.py and .env.example
- corresponding prompt/schema/API/security/architecture/linter/operations/design/plan/template docs
- corresponding canonical-contract, privacy, routing, budget, frontend, API, SQLite, architecture, documentation, provider, and evaluator tests

Test results:
- Canonical contract RED: 2 import errors; GREEN: 40 tests OK.
- Private knowledge/gate RED: 2 import errors; GREEN: 12 tests OK.
- Selected analyzer/model-safety integration GREEN: 7 tests OK.
- Exact budget/disclosure RED: 108 tests ran with 14 expected failures and 1 expected Node timeout while production still used the old constants; GREEN: 98 tests OK.
- Model-led escaped-newline/local-path regression RED: 1 failure; related GREEN: 15 tests OK.
- `python -B -m unittest tests.test_evaluate_deepseek_analysis`: 13 tests OK.
- `python -B scripts/evaluate_deepseek_analysis.py`: exit 0, 50 cases, schema/risk retention 1.0, unsupported facts 0, commitment/action violations 0, fallback rate 0.20.
- The 0.20 replay fallback rate is expected for this existing 40 accepted + 10 adversarial/fallback synthetic gate. It is not the Task 6 private 200-sample `<=0.10` target, and no safety gate was bypassed to reduce it.
- First full suite: 942 tests with 2 mechanical line-count failures; after the route-adapter refactor, final full suite: 942 tests OK.
- Architecture/static/mechanical/dependency/docs/transport guards: 92 tests OK.
- Both modified JavaScript files passed `node --check`; `git diff --check` passed.
- `scripts/maintenance_scan.py --fail-on-high`: exit 0, no cleanup findings.
- `docs/operations/project_status_log.md` remained unchanged as required.

Live API calls:
- 0 for this task.

Unfinished items:
- Optional separately authorized single synthetic live verification.
- Task 6 private 200-sample release contract and Task 7 project-status regeneration.

Follow-up recommendation:
- Preserve the Task 5 gate and exact budgets while Task 6 consumes the frozen
  contract; defer project-status regeneration to Task 7.
```
