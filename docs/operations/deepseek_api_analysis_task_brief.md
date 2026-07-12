---
last_update: 2026-07-12
status: draft
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
approved
```

The user approved DeepSeek remote processing and default context caching for the current visible message/thread and bounded supported-attachment text. DeepSeek may lead the displayed analysis, while mailbox actions remain forbidden and backend hard safety invariants remain authoritative.

## 4. Goal

Add an opt-in, backend-only DeepSeek API provider as the primary model path when configured. Let DeepSeek analyze the bounded cleaned visible thread and bounded locally extracted attachment text, and let a valid model result lead the summary, timeline, Decision Brief, risks, actions, and human-review reply draft.

Replace the current blanket deterministic projection with field-level hard safety enforcement: backend-owned attachment availability/status, schema, allowed enums, source membership, human-review flags, no-mailbox-action boundaries, and commitment safeguards remain authoritative. Return the deterministic rule result whenever the provider is disabled, unavailable, late, empty, truncated, filtered, or invalid.

Remove the current fixed 15-second frontend backend-response cutoff that expires before the configured model path can complete, while keeping a bounded synchronous user flow.

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

The current frontend aborts the backend request after 15 seconds, while the configured local Qwen route can take substantially longer. The user selected a backend DeepSeek API route with deterministic rule fallback and a synchronous timeout budget.

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

Relevant official DeepSeek documentation:

- `https://api-docs.deepseek.com/`
- `https://api-docs.deepseek.com/guides/json_mode/`
- `https://api-docs.deepseek.com/guides/thinking_mode/`
- `https://api-docs.deepseek.com/guides/kv_cache/`
- `https://api-docs.deepseek.com/api/create-chat-completion/`
- `https://api-docs.deepseek.com/quick_start/error_codes/`

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
13. Treat 35 seconds as the frontend wait for `POST /api/analyze-current-email` after browser resource collection. Use a 32-second cooperative backend target with a fixed 2-second response margin, hard 8-second parser/OCR process deadline, and hard remaining-time DeepSeek deadline. Synchronous bounded request reading, attachment storage, and SQLite persistence are not described as hard-cancellable; use monotonic checks around them and a SQLite busy timeout below the remaining response margin. Do not describe this as a strict Analyze-click total or hard end-to-end guarantee.

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

DeepSeek's current official documentation states that disk context caching is enabled by default and documents no request field to disable it. Its current privacy policy also describes collection and processing of prompts/inputs and storage in the People's Republic of China. Therefore this provider cannot be described as zero-retention or local-only. Enabling it requires acceptance of those external-processing terms; rule fallback remains the route for content that must not leave the machine.

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
13. The 32-second backend target is explicitly cooperative. Parser/OCR and provider stages have hard cancellable deadlines; bounded synchronous storage/persistence uses before/after checks and a SQLite busy timeout below the remaining margin.
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
- The written design specification still requires the Superpowers review gate before implementation planning starts.

## 16. Pre-Execution Checklist

```text
[x] AGENTS.md has been read.
[x] Project status, tooling, architecture, linter, security, prompt, API, and documentation rules have been read.
[x] Goal and non-goals are explicit.
[x] No real mailbox, secret, or customer data will be accessed during development.
[x] Expected file scope and rollback are identified.
[x] The user approved the design direction and expanded analysis boundary.
[ ] The written repository design has been reviewed by the user.
```

## 17. Execution Record

```text
Actual modified files:
- Not started.

Test results:
- Not started.

Unfinished items:
- Written design review.
- Implementation plan.
- TDD implementation and verification.

Follow-up suggestions:
- Perform any live API smoke test only with a locally configured key and a fully synthetic prompt after separate approval.
- Keep real Tencent Exmail validation as a separately authorized external release step.
```
