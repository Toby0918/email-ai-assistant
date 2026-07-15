---
last_update: 2026-07-14
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek Private Analysis Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development and superpowers:verification-before-completion. Execute the tasks in order and preserve each recorded RED before production changes.

**Goal:** Align the strict private DeepSeek contract and gate both remote DeepSeek routes behind local deidentification, bounded approved knowledge, output privacy checks, and exact synchronous budgets.

**Architecture:** One immutable contract module feeds both the strict validator and deterministic system prompt. `analysis_model_routes.py` builds each existing local prompt, but only DeepSeek sends it through `private_context_gate.py`; the gate renders verified runtime cards through `private_knowledge_context.py`, deidentifies the complete outbound user prompt, closes the resolver, scans residuals, and returns only a repr-safe plain-string context. The public API, SQLite projection, renderer fields, disabled/local-provider behavior, and diagnostics schema remain unchanged.

**Tech Stack:** Python 3.12.13 standard library, existing `openai==2.45.0`, immutable Task 4 private-knowledge runtime schema/deidentifier/scanner, JavaScript browser/local-debug clients, `unittest`.

## Global Constraints

- Keep `EMAIL_AGENT_LLM_PROVIDER=disabled`, `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative`, and the default model `deepseek-v4-flash` during implementation and verification.
- Make no live network, DeepSeek, mailbox, vault, DPAPI, or BitLocker call.
- Use only synthetic `example.test` data; no real person, customer, supplier, employee, email, attachment, credential, or identifier.
- Preserve exactly one DeepSeek call, `max_retries=0`, JSON object mode, thinking disabled, `max_tokens=2400`, temperature `0`, no tools, and the fixed endpoint/model allowlist.
- Use exact budgets: browser/local-debug POST `15` seconds, backend `13` seconds, provider cap/default `10` seconds, minimum provider remainder `5` seconds, response margin `2` seconds, parser maximum `8` seconds.
- Keep public HTTP response, SQLite analysis projection, frontend renderer fields, and public diagnostics schema unchanged.
- Add only the backend-only immutable `runtime_cards=()` seam; do not add environment variables, snapshot paths, key loading, vault access, frontend fields, or Task 6 evaluation behavior.
- Reuse `safety_rejected_all`/`safety` for privacy refusal and `budget_exhausted`/`budget` for low budget.
- Do not regenerate `docs/operations/project_status_log.md`; the master plan defers that update to Task 7.

---

### Task 1: Resolve Task 5 governance and lock the file map

**Files:**
- Modify: `docs/superpowers/specs/2026-07-14-deepseek-analysis-contract-alignment-design.md`
- Modify: `docs/operations/deepseek_analysis_contract_alignment_task_brief.md`
- Create: `docs/superpowers/plans/2026-07-14-deepseek-analysis-contract-alignment.md`

**Interfaces:**
- The approved alignment design remains authoritative for canonical schema/prompt behavior.
- Master Task 5 supersedes it only for the private outbound gate, persistent disclosure, and exact `15/13/10/5` budgets.
- Runtime knowledge enters only as an immutable default-empty internal tuple of already verified runtime cards.

- [x] **Step 1: Record the supersession and approved decisions.**

  Update the existing design and brief in place; do not create a competing task brief.

- [x] **Step 2: Record the actual integration boundary.**

  Name `backend/email_agent/analysis_model_routes.py` as the only model-call orchestration boundary and cover both DeepSeek output modes without changing Ollama.

- [x] **Step 3: Record Task 7 ownership of status generation.**

  Keep Task 5 verification comprehensive but do not run the status generator.

### Task 2: Canonical contract RED and GREEN

**Files:**
- Create: `backend/email_agent/deepseek_analysis_contract.py`
- Modify: `backend/email_agent/deepseek_analysis_schema.py`
- Modify: `backend/email_agent/prompt_context.py`
- Modify: `tests/test_prompt_context.py`
- Modify: `tests/test_deepseek_analysis_schema.py`

**Interfaces:**
- Produces immutable `SCHEMA_VERSION`, exact-key sets, type rules, enum mappings, `APPROVED_EVIDENCE_PATTERNS`, `complete_envelope_example()`, `render_analysis_contract()`, and `MAX_SYSTEM_PROMPT_CHARACTERS`.
- `deepseek_analysis_schema.py` imports and compatibility-reexports the canonical constants.
- `DEEPSEEK_SYSTEM_PROMPT` is deterministic and no longer than 8,000 characters.

- [ ] **Step 1: Write the failing parity and example tests.**

  Assert every exact object field set, field type, enum domain, no-extra/no-`null` rule, `next_steps` 1-through-4 cardinality, mandatory human-review flag, approved evidence pattern, deterministic ordering, and prompt ceiling. Validate a fresh complete example against both production validators using only `{"thread:0": object()}`.

- [ ] **Step 2: Run RED.**

  Run:

  ```powershell
  python -m unittest tests.test_prompt_context tests.test_deepseek_analysis_schema
  ```

  Expected: failure because `deepseek_analysis_contract.py` and its canonical exports do not exist and the old example fabricates sources.

- [ ] **Step 3: Implement the immutable contract.**

  Use `frozenset`, tuples, and read-only mappings; return a fresh example dictionary each time. The example uses `thread:0`, empty `open_item_annotations`, and empty `attachment_augmentations`.

- [ ] **Step 4: Refactor the validator and prompt consumers.**

  Preserve fail-closed parsing, duplicate-key rejection, exact enums, no normalization, no `null`, no extras, 1-through-4 `next_steps`, and `needs_human_review is True`.

- [ ] **Step 5: Run GREEN and refactor within line guidance.**

  Re-run the two focused modules and confirm all tests pass with the complete system prompt at or below 8,000 characters.

### Task 3: Private knowledge and outbound gate RED and GREEN

**Files:**
- Create: `backend/email_agent/private_knowledge_context.py`
- Create: `backend/email_agent/private_context_gate.py`
- Create: `tests/test_private_knowledge_context.py`
- Create: `tests/test_private_context_gate.py`

**Interfaces:**
- `render_private_knowledge_context(cards, rule_result) -> RenderedKnowledgeContext` revalidates each card through `RuntimeKnowledgeCard.from_mapping(card.to_mapping())`, selects deterministically from local category/priority/risk/action signals, and emits at most 8 whole cards and 4,000 characters.
- `build_private_model_context(request, rule_result, cards, budget) -> PrivateModelContext | PrivateContextFallbackCode` returns only a deidentified plain string plus a non-sensitive count, or fixed `safety`/`budget` fallback.
- `provider_output_is_private_safe(raw) -> bool` rejects placeholders, restoration/reidentification language, and fixed forbidden private metadata markers before parsing.

- [ ] **Step 1: Write knowledge-renderer RED tests.**

  Cover forged dataclass rejection, deterministic relevance/order, 8-versus-9 cards, 4,000-versus-4,001 whole-card selection, and absence of card/snapshot/vault IDs, schema/envelope metadata, paths, URLs, binaries, placeholders, mappings, and locators.

- [ ] **Step 2: Write context-gate RED tests.**

  Cover all Task 4 identity/transaction patterns, bounded header display names, ambiguous/residual/context failures, resolver closure before the client boundary, plain-string-only escape, under-5-second refusal, fixed repr/error behavior, and provider placeholder/restoration/private-marker rejection.

- [ ] **Step 3: Run RED.**

  Run:

  ```powershell
  python -m unittest tests.test_private_knowledge_context tests.test_private_context_gate
  ```

  Expected: import failures for the two missing production modules.

- [ ] **Step 4: Implement the pure modules.**

  `private_context_gate.py` may use only the Task 4 deidentifier, residual scanner, and entity patterns from `backend.private_knowledge`; `private_knowledge_context.py` may use only `runtime_schema` from that namespace. Catch failures without retaining input-bearing exception text.

- [ ] **Step 5: Run GREEN.**

  Re-run both focused modules and confirm the resolver/mapping is closed before any returned context can be consumed.

### Task 4: DeepSeek route integration and local-fact authority

**Files:**
- Modify: `backend/email_agent/analyzer.py`
- Modify: `backend/email_agent/analysis_model_routes.py`
- Modify: `backend/email_agent/model_result_safety.py`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_model_result_safety.py`

**Interfaces:**
- `analyze_current_email(..., runtime_cards=())` is backend-only, keyword-only, immutable-default, and absent from HTTP input/output.
- Only DeepSeek `model_led` and DeepSeek `conservative` prompts cross the private gate; Ollama and disabled providers keep their current route behavior.
- Provider raw text is privacy-gated before `parse_deepseek_analysis_v1` and before `parse_legacy_result`.
- Model-led safe merge deep-copies the exact deterministic `fallback["decision_brief"]["key_facts"]` back into the merged brief.

- [ ] **Step 1: Write route RED tests.**

  Assert both DeepSeek modes receive locally deidentified prompts, the resolver is closed before the injected generator, runtime cards are optional/default-empty, residuals and provider placeholders skip both parsers, low budget skips the client, Ollama remains raw/local, and no private object or raw canary reaches fallback, diagnostics, logs, or exceptions.

- [ ] **Step 2: Write key-fact RED test.**

  Use a deterministic local key-fact list and assert equality plus distinct object identity after an otherwise safe model merge.

- [ ] **Step 3: Run RED.**

  Run the named analyzer and model-safety tests and confirm failures reflect the missing gate/seam and current whole-brief replacement.

- [ ] **Step 4: Implement minimal integration.**

  Route both DeepSeek modes through one helper, recompute the provider timeout immediately before the single call, reject unsafe raw output before either parser, and leave public diagnostics unchanged.

- [ ] **Step 5: Run GREEN and existing analyzer/model-safety suites.**

### Task 5: Exact budget/provider contract RED and GREEN

**Files:**
- Modify: `backend/email_agent/analysis_budget.py`
- Modify: `backend/email_agent/config.py`
- Modify: `backend/email_agent/llm_client.py`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `.env.example`
- Modify: `scripts/deepseek_eval_replay.py`
- Modify: `tests/test_analysis_budget.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_llm_client.py`
- Modify: `tests/test_browser_extension_task6_contracts.py`
- Modify: `tests/test_frontend_local_debug.py`

**Interfaces:**
- Exact values are browser/local-debug POST 15, backend 13, DeepSeek maximum/default/config/client cap 10, minimum remaining 5, response margin 2, parser maximum 8.
- Browser visible-resource collection remains 20 seconds.
- The DeepSeek SDK request remains one awaited call with zero retries, JSON object mode, temperature 0, non-streaming, 2,400 tokens, thinking disabled, and no tools.

- [ ] **Step 1: Change exact-value assertions first and run RED.**

  Expected failures report stale `35/32/25` values.

- [ ] **Step 2: Implement only the approved constants/defaults.**

  Do not change provider endpoint, models, request body, output modes, or retry behavior.

- [ ] **Step 3: Run GREEN for budget/config/client/frontend timeout tests.**

### Task 6: Persistent disclosure, docs, architecture, and public canaries

**Files:**
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/local_debug_page/index.html`
- Modify: `docs/prompts/analyzer_prompt.md`
- Modify: `docs/data/analysis_result_schema.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/constraints/architecture_constraints.md`
- Modify: `docs/constraints/linter_constraints.md`
- Modify: `docs/templates/agent_task_brief_template.md`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_frontend_local_debug.py`
- Modify: `tests/test_deepseek_documentation_contracts.py`
- Modify: `tests/test_architecture_constraints.py`
- Modify: `tests/test_static_linter_constraints.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_database.py`

**Interfaces:**
- Both pages show exactly: `After you click Analyze, a configured remote AI provider receives locally deidentified current visible content and, when available, bounded approved knowledge cards. Processing is not local-only, and no zero-retention guarantee is made.`
- Only `private_context_gate.py` may import Task 4 deidentifier/residual/entity-pattern primitives, and only `private_knowledge_context.py` may import `runtime_schema`; all repository/review/candidate/key/publisher/snapshot-writer/mailbox imports remain forbidden.
- No `private_context`, `knowledge_cards`, resolver/mapping, placeholder, card/snapshot/vault identifier, raw value, or new field enters HTTP, SQLite, renderer, log, diagnostic, or exception surfaces.

- [ ] **Step 1: Write exact disclosure, architecture, and canary assertions first and run RED.**

- [ ] **Step 2: Update visible text and documentation.**

  Clarify local deidentification, optional bounded approved cards, non-local-only processing, no zero-retention guarantee, exact facts remaining local/deterministic, enum-specific `unknown`, schema-specific empty arrays, and 1-through-4 `next_steps`.

- [ ] **Step 3: Update narrow executable dependency rules.**

  Do not grant a broad `backend.email_agent -> backend.private_knowledge` dependency.

- [ ] **Step 4: Run GREEN across frontend/docs/architecture/static/public-interface tests.**

### Task 7: Offline verification, report, and commit

**Files:**
- Create ignored: `.superpowers/sdd/task-5-implementer-report.md`

**Interfaces:**
- The report records exact RED failures, GREEN commands/counts, provider-disabled state, zero live calls, and the final commit.

- [ ] **Step 1: Run all focused Task 5 suites.**

- [ ] **Step 2: Run the existing 50-case evaluator offline.**

  Run the repository evaluator with an injected replay/fake only and verify 50 cases; do not enable DeepSeek.

- [ ] **Step 3: Run full and executable constraints.**

  Run full `unittest`, JavaScript syntax checks for changed JS, architecture/static/mechanical/transport tests, `git diff --check`, and `scripts/maintenance_scan.py`.

- [ ] **Step 4: Audit the diff and defaults.**

  Confirm no Task 6 implementation, status-log regeneration, key/path/bootstrap invention, live call, public field, or forbidden private identifier appears.

- [ ] **Step 5: Write the ignored implementation report.**

  Include exact test counts and RED→GREEN evidence without sensitive values.

- [ ] **Step 6: Commit only after every required gate passes.**

  ```powershell
  git commit -m "feat: gate DeepSeek with private deidentification"
  ```
