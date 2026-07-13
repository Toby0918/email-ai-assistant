---
last_update: 2026-07-12
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek API Analysis Task Brief

## 1. Task Name

```text
add backend-only DeepSeek analysis with deterministic rule fallback
```

## 2. Task Type

```text
feature | security | prompt | test | api_contract
```

## 3. Current Status

```text
active
```

The user approved DeepSeek remote processing and documented default context caching for the current visible message/thread and bounded supported-attachment text. Tasks 1-14 implement and verify the provider, safety, timing, persistence, frontend disclosure, offline quality-gate, and release-record contracts. DeepSeek may lead the displayed analysis, while mailbox actions remain forbidden and backend hard safety invariants remain authoritative. This task brief remains active as the operating contract; provider enablement and deployment remain opt-in and were not performed by Task 14.

## 4. Goal

Add an opt-in, backend-only DeepSeek API provider as the primary model path when configured. Let DeepSeek analyze the bounded cleaned visible thread and bounded locally extracted attachment text, and let a valid model result lead the summary, timeline, Decision Brief, risks, actions, and human-review reply draft.

Replace the current blanket deterministic projection with field-level hard safety enforcement: backend-owned attachment availability/status, schema, allowed enums, source membership, human-review flags, no-mailbox-action boundaries, and commitment safeguards remain authoritative. Return the deterministic rule result whenever the provider is disabled, unavailable, late, empty, truncated, filtered, or invalid.

Replace the original fixed 15-second frontend backend-response cutoff with the implemented bounded synchronous user flow.

## 5. Non-Goals

- Do not access or test against a real mailbox or real customer email.
- Do not automatically send, delete, archive, move, forward, or reply to email.
- Do not scan a mailbox or analyze anything before the user's explicit Analyze click.
- Do not put `DEEPSEEK_API_KEY` or provider configuration in frontend code or frontend requests.
- Do not send attachment binaries, base64, local paths, private download URLs, cookies, tokens, active content, or unbounded attachment text to DeepSeek.
- Do not add an automatic DeepSeek-to-Ollama retry chain.
- Do not implement a background job, polling API, or asynchronous result store in this task.
- Do not enable live DeepSeek calls by default or run a paid/live API smoke test without separate authorization and a locally supplied key.
- Do not change the public analysis request or response schema.
- Do not give DeepSeek permission to fetch links, call tools, read other messages, or execute any suggested action.
- Do not transmit visible message URLs; replace them with a marker that only records that a link was present.

## 6. Background And References

Before implementation, the frontend aborted the backend request after 15 seconds while the configured local Qwen route could take substantially longer. The user selected a backend DeepSeek API route with deterministic rule fallback and a synchronous timeout budget.

Current DeepSeek documentation changes the previously assumed model choice: `deepseek-chat` is scheduled to become inaccessible on 2026-07-24, so a new integration must use `deepseek-v4-flash` or `deepseek-v4-pro`. The latency-sensitive route will use `deepseek-v4-flash` with thinking explicitly disabled.

Relevant project documents:

- `AGENTS.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/security/api_key_rules.md`
- `docs/security/email_data_handling.md`
- `docs/security/privacy_rules.md`
- `docs/security/prompt_injection_rules.md`
- `docs/prompts/analyzer_prompt.md`
- `docs/api/backend_api_contract.md`
- `docs/api/frontend_backend_flow.md`
- `docs/operations/deployment_notes.md`

Relevant official DeepSeek documentation, rechecked 2026-07-12:

- `https://api-docs.deepseek.com/quick_start/pricing/`
- `https://api-docs.deepseek.com/api/create-chat-completion`
- `https://api-docs.deepseek.com/guides/thinking_mode`
- `https://api-docs.deepseek.com/guides/kv_cache/`
- `https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html`

## 7. Scope

Expected new or modified files:

- `backend/email_agent/config.py`
- `backend/email_agent/llm_client.py`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/prompt_context.py`
- `backend/email_agent/attachment_parser.py`
- `backend/email_agent/attachment_text.py`
- `backend/email_agent/attachment_model_context.py` for ephemeral, bounded remote attachment text
- `backend/email_agent/model_result_safety.py` for source grounding and field-level hard-safety merge
- `backend/email_agent/analysis_budget.py` for monotonic remaining-budget enforcement
- `frontend/browser_extension/shared/api_client.js`
- `frontend/browser_extension/popup.html`
- `frontend/local_debug_page/app.js`
- `frontend/local_debug_page/index.html`
- `.env.example`
- `AGENTS.md`
- Focused tests under `tests/`
- Related provider, privacy, API, prompt, setup, deployment, and troubleshooting documents under `docs/`

The approved frontend scope changes the backend POST wait to 35 seconds after browser resource collection. A strict Analyze-click-to-result deadline is explicitly outside this task because it would require shared browser collection and backend execution deadlines.

## 8. Technical Approach

1. Add `deepseek` as an opt-in backend provider with a separate backend-only `DEEPSEEK_API_KEY`.
2. Call the official `https://api.deepseek.com` endpoint through the already pinned `openai==2.45.0` package. Do not expose a configurable arbitrary remote base URL.
3. Use `deepseek-v4-flash`, non-streaming JSON Output, explicit non-thinking mode, bounded `max_tokens`, zero SDK retries, and a 25-second maximum provider budget. Allow the approved `deepseek-v4-pro` model through backend configuration for later synthetic evaluation, but do not make it the default.
4. Treat the user's approval as operator-wide consent for this local installation whenever both `deepseek` and `model_led` are configured. Show a persistent pre-click disclosure that Analyze sends the current visible thread and bounded attachment extraction to the configured remote provider. Keep the public request schema unchanged.
5. Build one bounded remote context from the current visible thread plus locally extracted image/PDF/XLSX/DOCX text. Preserve business identifiers, names, dates, quantities, amounts, deadlines, and quality language. Remove every URL, secret, authorization value, private attachment download URL, cookie, token, local path, and active-content marker.
6. Keep the expanded attachment model text ephemeral and out of SQLite, logs, API responses, docs, tests, and repository fixtures. Continue returning only bounded `attachment_insights` to the UI and SQLite.
7. Define a versioned internal `deepseek_analysis_v1` response envelope with request-local source IDs and model-led fields. Validate and map it into the unchanged public response schema.
8. Require a successful completion reason and non-empty content before passing JSON through internal schema, language, source, grounding, and safety validation.
9. Let valid DeepSeek output lead user-facing analytical fields. Keep backend-owned `analysis_engine`, attachment filename/type/status/limitations, mandatory locally detected security/prompt-injection/commitment risks, schema/enums, `reply_draft.needs_human_review=true`, source membership, and no-action/no-commitment invariants authoritative. Replace only a violating field with its safe deterministic counterpart when isolation is reliable; otherwise reject the model result and use full rule fallback.
10. Ground critical identifiers, quantities, measurements, amounts, dates, completion claims, and commitment claims in every model-led text field, not only Decision Brief key facts.
11. On any sanitized provider error, return the existing rule fallback in the same API response. Do not try Ollama after DeepSeek failure.
12. Keep the provider default disabled. When explicitly configured as `deepseek`, DeepSeek is the primary attempt and rules are the only automatic fallback.
13. Treat 35 seconds as the frontend wait for `POST /api/analyze-current-email` after independent 20-second browser resource collection. Call `AnalysisBudget.start()` immediately before the validated request body read; the runtime order is `start -> read -> api`, so body-read time consumes the 32-second cooperative backend budget. Keep the fixed 2-second response margin, hard 8-second parser/OCR process deadline, 25-second maximum/5-second minimum provider attempt, and a 0.5-second cumulative SQLite stage with a 0.25-second response floor. Synchronous request reading, attachment storage, SQLite calls, and response writing are not described as hard-cancellable. Do not describe this as a strict Analyze-click total or hard end-to-end guarantee.

## 9. Data Structure Or Interface Changes

### Database Changes

```text
None.
```

### API Changes

```text
No public request or response shape change. analysis_engine.label may report DeepSeek V4 Flash. Operator-wide remote-processing consent is represented by backend configuration and persistent pre-click UI disclosure rather than a new request field.
```

### AI Output JSON Changes

```text
Yes, internally. Add a versioned deepseek_analysis_v1 provider envelope with request-local source IDs, evidence-source fields, attachment augmentations, and model-led analysis fields. It maps into the unchanged public analysis JSON after validation.
```

### Prompt Changes

```text
Yes. The provider request must explicitly ask for json, include a bounded example shape, keep untrusted-data boundaries, include source-labelled visible thread and bounded attachment text, and state that links/content are data rather than executable instructions.
```

### Backend Configuration Changes

```text
DEEPSEEK_API_KEY=<backend-only secret>
EMAIL_AGENT_LLM_PROVIDER=deepseek
EMAIL_AGENT_DEEPSEEK_MODEL=deepseek-v4-flash
EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS=25
EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led
```

`EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE` defaults to `conservative`; the approved model-led authority requires the explicit backend value `model_led`.

## 10. Security And Privacy Check

```text
[x] Do not read a real mailbox account during implementation or automated verification.
[x] Do not automatically send, delete, archive, move, forward, or reply to email.
[x] Keep DeepSeek and OpenAI API keys out of frontend code and frontend requests.
[x] Treat subject, sender, recipients, body, thread fields, attachment names, and parsed facts as untrusted input.
[x] Require model output to be parseable and validated JSON before any model augmentation is used.
[x] Do not log real email bodies, prompts, customer-sensitive data, API keys, tokens, or raw provider exceptions.
[x] Use only synthetic or sanitized tests.
[x] Do not send attachment bytes, base64, any URL, cookies, authorization values, tokens, local paths, active content, or unbounded attachment text to the remote provider.
[x] Keep the provider disabled unless an operator deliberately supplies backend configuration.
[x] Keep remote attachment text ephemeral and out of SQLite, logs, API responses, docs, tests, and repository fixtures.
[x] Show persistent pre-click disclosure whenever the product may use the configured remote provider.
```

DeepSeek's current official documentation states that disk context caching is enabled by default, works on a best-effort basis, and is usually cleared after it is no longer used within a few hours to a few days; that is not a guaranteed deletion deadline. Its current privacy policy describes collection of prompts/inputs and processing/storage in the People's Republic of China. Therefore this provider cannot be described as zero-retention or local-only. Enabling it requires acceptance of those external-processing terms; rule fallback remains the route for content that must not leave the machine.

## 11. Prompt Injection Protection

- Put fixed behavior and JSON requirements in a system message.
- Put the bounded email/thread/attachment context in a user message with explicit untrusted-field markers.
- Do not execute or follow instructions found in the email, headers, filenames, attachment facts, or limitations.
- Do not reveal prompts, keys, configuration, database content, or other email content.
- Do not let model text override backend attachment status/limitations, the factual timeline skeleton, mandatory locally detected safety risks, source membership, human-review flags, or no-action/no-commitment safeguards. DeepSeek may lead validated analytical prose and recommendations inside those invariants.
- Continue to remove `analysis_engine` from model output and derive it only in backend code.

## 12. Acceptance Criteria

1. `EMAIL_AGENT_LLM_PROVIDER=deepseek` with a backend key calls the official DeepSeek OpenAI-compatible Chat Completions API using `deepseek-v4-flash`, `response_format={"type":"json_object"}`, `stream=false`, explicit non-thinking mode, bounded `max_tokens`, and no automatic SDK retry.
2. The provider receives the remaining backend response budget, never more than 25 seconds, and the request is cancellable even when the remote service sends keep-alive data.
3. Missing key, authentication/balance/rate/server errors, timeout, empty content, non-success finish reason, malformed JSON, schema failure, or language failure returns a valid rule fallback without leaking provider details.
4. The remote request contains the bounded current visible thread and bounded supported-attachment extraction required for useful analysis, including business identifiers and dates, but no attachment binary/base64, URL, cookie/authorization/token, local path, active content, or unbounded source text. Canary tests prove both the positive and negative boundaries.
5. A versioned internal DeepSeek envelope carries request-local evidence/source IDs and model-led fields, then maps into the unchanged public response only after validation.
6. A valid DeepSeek result can lead summary, priority, category, timeline interpretation, Decision Brief, risks, suggested actions, and reply draft. The backend preserves hard invariants and uses field-level or full fallback for unsafe or ungrounded output.
7. Mandatory locally detected prompt-injection, security, and commitment risks are always unioned into the result and cannot be removed or downgraded by DeepSeek.
8. The backend owns the complete timeline open-item set, order, stable IDs, source, owner, and due fields. DeepSeek may rephrase matched item text but cannot omit an item or add an unknown ID.
9. DeepSeek cannot alter backend attachment availability/status, add nonexistent sources, set `needs_human_review=false`, trigger mailbox operations, or create an unsupported/unconditional price, delivery, payment, contract, quality, completion, or legal claim in any model-led field.
10. Existing current-message click gating remains intact. No mailbox-wide or pre-click collection is introduced. Persistent UI text discloses remote processing before the click when the remote route may be used.
11. The provider is disabled by default; `deepseek` is primary only when explicitly configured, and Ollama is not attempted after DeepSeek failure.
12. The browser extension and local debug page no longer abort a normal provider attempt at 15 seconds. Documentation identifies 35 seconds as the POST wait after resource collection, not a strict click total.
13. The 32-second backend target is explicitly cooperative and starts immediately before request-body read, in the documented `start -> read -> api` order; body-read time therefore consumes that target. Parser/OCR and provider stages have hard cancellable deadlines; bounded synchronous storage uses before/after checks. SQLite uses one 0.5-second cumulative lock/INSERT/commit stage, a 0.25-second response floor, recomputed busy timeouts, rollback on save error, and connection quarantine on rollback failure.
14. Public API/schema and SQLite persistence remain backward compatible; ephemeral expanded model context is never persisted.
15. Focused tests, full Python suite, frontend JavaScript syntax checks, architecture/static/mechanical guards, maintenance scan, status generation, and `git diff --check` pass.

## 13. Test Plan

- Add red/green config tests for DeepSeek key/model/timeout defaults and environment overrides.
- Add red/green client tests for exact request shape, fixed official base URL, non-thinking JSON mode, zero retries, wall-clock cancellation, finish reasons, empty content, and sanitized exceptions.
- Add analyzer tests for DeepSeek label, model-led consequential fields, field-level hard-safety fallback, full model-to-rule fallback, no Ollama chaining, and valid JSON/schema/language handling.
- Add internal provider-envelope tests for versioning, evidence/source IDs, attachment augmentation mapping, and public response projection.
- Add safety-union tests proving model output cannot remove/downgrade locally detected prompt-injection, security, or commitment risks.
- Add all-field grounding tests for identifiers, quantities, measurements, amounts, dates, completion claims, and commitments.
- Add timeline open-item tests proving stable backend IDs/set/order/source/owner/due fields survive omission, reordering, and unknown model IDs while accepted wording can improve.
- Add prompt positive tests for visible thread, business identifiers, dates, amounts, attachment text, and source labels.
- Add prompt privacy canaries for attachment bytes, base64, paths, every URL shape, cookies, authorization values, tokens, active content, and text beyond the approved bounds.
- Add frontend behavior/static tests for the approved timeout semantics.
- Add persistent pre-click remote-processing disclosure tests.
- Add process-isolation tests proving a stuck synthetic decoder is terminated within the hard parser deadline, plus provider cancellation, cooperative storage checks, and SQLite busy-timeout tests.
- Run `python -m unittest discover -s tests` with the bundled Python 3.12 runtime.
- Run all JavaScript syntax checks listed by the phase-two release checklist.
- Run `python scripts/maintenance_scan.py` and regenerate the project status log before final verification.
- Do not call the live DeepSeek API in automated tests.

## 14. Rollback Plan

Set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the backend to immediately restore rule-only behavior. A second feature flag will retain the conservative projection path during rollout so model-led consequential fields can be disabled independently. Code rollback removes the DeepSeek branch, expanded ephemeral model context, configuration, timeout changes, tests, and provider documentation while preserving the existing rule and optional local Ollama paths.

## 15. Human Confirmation Needed

- The user accepted DeepSeek remote processing and the documented default context caching for the current visible thread and bounded attachment extraction on 2026-07-12.
- The user approved DeepSeek-led analysis while keeping all mailbox operation permissions forbidden on 2026-07-12.
- The approval is operator-wide for this local installation whenever both `deepseek` and `model_led` are configured; every Analyze click under that configuration may send the current visible message scope to DeepSeek and is disclosed persistently before the click.
- The written design specification passed the Superpowers review gate and the user instructed implementation to start.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status, tooling, architecture, linter, security, prompt, API, and documentation rules have been read.
[x] Goal and non-goals are explicit.
[x] No real mailbox, secret, or customer data will be accessed during development.
[x] Expected file scope and rollback are identified.
[x] The user approved the design direction and expanded analysis boundary.
[x] The written repository design has been reviewed by the user.
```

## 17. Execution Record

```text
Actual implementation file groups and commits:
- Task 1 configuration/dependency boundary: .env.example, backend/email_agent/config.py, tooling/deployment docs, and configuration/static tests in 7a188ca (feat: configure backend DeepSeek provider).
- Task 2 cooperative budget: backend/email_agent/analysis_budget.py and tests/test_analysis_budget.py in 9918356 (feat: define cooperative analysis budget).
- Task 3 fixed-endpoint provider client: backend/email_agent/llm_client.py plus configuration/client tests in 31a4f1f (feat: add bounded DeepSeek provider client).
- Task 4 backend timeline ownership: backend/email_agent/thread_timeline.py and timeline tests in e5def31 and cf55fde.
- Task 5 ephemeral attachment model context: backend/email_agent/attachment_model_context.py, attachment_parser.py, and attachment tests in 5d70587, 722b400, and b94019f.
- Task 6 hard-deadline attachment isolation: backend/email_agent/attachment_docx.py, attachment_parser.py, attachment_text.py, and parser/process tests in 95e47f7 and 3f05aba.
- Task 7 private DeepSeek envelope: backend/email_agent/deepseek_analysis_schema.py and schema tests in 9286b42 and d050c23.
- Task 8 source-labelled prompt and all-field grounding: backend/email_agent/prompt_context.py, model_grounding.py, and their tests in 4c4aea7 and fc26f18.
- Task 9 local/schema safety and model-led merge: backend/email_agent/analysis_schema.py, rule_analyzer.py, model_result_safety.py, model_text_safety.py, and related schema/rule/database/safety tests in 515cc03, b78b4f0, a8386bd, bbbe542, and 73f27d3.
- Task 10 request-path routing/deadlines: backend/email_agent/analysis_model_routes.py, analyzer.py, api.py, server.py, llm_client.py, and routing/provider tests in 6afcfc1 and e880da3.
- Task 11 bounded persistence and failed-transaction quarantine: backend/email_agent/database.py, server.py, and database/server tests in fc77a7c, e584991, and 6fb7cd4.
- Task 12 frontend wait/disclosure contracts: browser popup/API client, local-debug UI, and frontend contract tests in 9f014c2 and 259a2fa.
- Task 13 offline evaluator/contracts: scripts/evaluate_deepseek_analysis.py, the 50-case fixture, evaluator support and three split test modules, plus prompt/schema/API/security/ADR/design/task-brief contracts in 9c9fcdb and 478be85.

Task 14 final verification evidence:
- Complete focused DeepSeek suite, including the split fixture and documentation contract modules: 358 tests passed in 20.502 seconds.
- Offline evaluator exited 0 with exactly: case_count 50; schema_pass_rate 1.0; mandatory_risk_retention_rate 1.0; unsupported_critical_fact_count 0; commitment_action_violation_count 0; fallback_rate 0.2; latency_samples_ms [100.0, 101.0, 102.0, 103.0, 104.0].
- The bundled Python status generator exited 0. It emitted the host-local 2026-07-13 date; the two generated date fields were normalized to the Task 14 project date 2026-07-12 without changing generator code. Generated documentation counts are active 66, draft 27, deprecated 0, missing_front_matter 0.
- Post-generation full unittest discovery: 650 tests passed in 85.451 seconds.
- Post-generation maintenance scan: exit 0; No cleanup findings detected.
- All seven listed node --check commands exited 0; the extension manifest JSON parse printed manifest json: OK.
- The exact brief manifest/architecture/static guard ran 24 tests in 12.736 seconds and passed. The expanded browser static/resource-timeout/local-debug/mechanical guard ran 58 tests in 1.184 seconds and passed.
- Explicit frontend scan found no DeepSeek/OpenAI/Ollama/Qwen/Gemma endpoint, key, SDK, environment, or direct-provider markers.
- Current frontend constants were verified as MAX_ANALYZE_TIMEOUT_MS = 35000, ANALYZE_TIMEOUT_MS = 35000, and MAX_OVERALL_RESOURCE_TIMEOUT_MS = 20000; the 35-second POST wait remains independent of the 20-second resource collection limit.
- The post-edit Task 14 date/front-matter assertion passed. DeepSeek documentation, static, architecture, mechanical, and status-generator guards then ran 44 tests and passed.
- git diff --check passed before this execution-record edit. Final post-edit diff and staged-snapshot evidence is recorded in .superpowers/sdd/task-14-report.md.

Rollback flags and release state:
- EMAIL_AGENT_LLM_PROVIDER=disabled restores rule-only behavior and remains the default.
- EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative disables model-led consequential fields independently and remains the default.
- No provider flag, API key, deployment setting, mailbox permission, or frontend request schema was enabled or changed by Task 14.
- Written design review: complete.
- Implementation plan: complete through Task 14.
- Final release verification: complete in Task 14.
- Historical Task 13 handoff marker: Final release verification: pending Task 14.

Unfinished and explicitly deferred items:
- A live paid DeepSeek API smoke test was not run; it requires separate authorization and a locally supplied backend key with fully synthetic input.
- Real mailbox or real mail-data testing was not run and remains forbidden by the current task boundary.
- Manual Chrome/Edge pixel/CSS verification of persistent notice visibility remains deferred; automated static/behavior contracts passed.
- Deployment and provider enablement remain opt-in operator actions and were not performed.
- No push or pull request was performed.
```
