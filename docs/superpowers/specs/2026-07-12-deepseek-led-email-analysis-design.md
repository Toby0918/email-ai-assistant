---
last_update: 2026-07-12
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# DeepSeek-Led Current Email Analysis Design

## Decision Summary

The user approved a backend-only DeepSeek route that can analyze the bounded cleaned content of the currently visible email thread and bounded locally extracted text from supported visible attachments. A valid DeepSeek result may lead user-facing analytical prose and recommendations, including the summary, timeline interpretation, priority, category, Decision Brief, added risks, suggested actions, and English reply draft. Backend factual/safety skeleton fields remain authoritative as defined below.

This expands analysis authority only. It does not grant mailbox or execution authority. DeepSeek cannot read another message or folder, fetch a link, call a mailbox API, send a message, delete or archive anything, or perform an action described in its output.

The user also accepted that the approved remote context is processed by DeepSeek and is subject to DeepSeek's documented default disk context caching. This approval is operator-wide for this local installation whenever both `EMAIL_AGENT_LLM_PROVIDER=deepseek` and `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led` are configured. Every Analyze click under that configuration may send the approved current-message scope to DeepSeek. Persistent text beside the Analyze control discloses this before the click. The provider remains disabled until a backend operator deliberately configures it.

## Problem Diagnosis

The current plugin is not useful enough for three separate reasons:

1. The browser and local debug page stop waiting for the backend after 15 seconds, while a model attempt can take longer.
2. The current repair layer discards the model's Decision Brief, timeline, risks, actions, attachment interpretation, and reply draft. Only summary, priority, category, and tags can survive. Replacing local Qwen with a stronger API under that policy would leave most of the visible result rule-generated.
3. The attachment display sanitizer intentionally removes links, email addresses, paths, and long digit sequences. That output is appropriate for storage and display but removes PO, RFQ, invoice, tracking, date, and other business context that a model needs to understand the attachment.

The solution must address all three. A provider-only change is insufficient.

## Considered Approaches

### Approach A: DeepSeek-led analysis with backend hard safety guards

This is the approved approach.

- Send a bounded, source-labelled current visible thread and bounded attachment extraction.
- Preserve business context needed for analysis.
- Let DeepSeek lead analytical prose and recommendations inside explicit backend factual/safety invariants.
- Keep schema, source membership, attachment availability, human review, commitment restrictions, and mailbox-action restrictions backend-owned.
- Use field-level safe replacement when a violation is isolated, and full rule fallback when it is not.

This provides the largest usability improvement without granting operational authority.

### Approach B: DeepSeek as a five-field augmentation layer

This was rejected because it preserves the current deterministic projection of the most useful fields. It is lower risk, but a stronger model would still have little effect on the Decision Brief, risks, actions, and draft.

### Approach C: Maximum remote and mailbox permission

This was rejected. Sending attachment binaries, exposing authenticated download URLs, scanning other messages, following links, or allowing automatic email actions would materially expand privacy and operational risk and is not necessary for useful analysis.

## Product Boundary

### Allowed

- The user opens one Tencent Exmail message and explicitly clicks Analyze.
- The extension reads the currently visible subject, headers, body, visible thread segments, and visible supported attachment resources.
- The backend cleans and bounds the current thread.
- The backend validates, stores temporarily, and parses visible image, PDF, XLSX, and DOCX resources.
- The backend sends approved text context to DeepSeek.
- The extension and local debug page display persistent pre-click notice that a configured remote provider receives the current visible scope.
- DeepSeek produces structured analysis and an English reply draft.
- The user reviews, edits, and manually copies the draft.

### Forbidden

- Background or mailbox-wide analysis.
- Reading another message, folder, account, hidden resource, or server mailbox API.
- Collecting any email or attachment before the Analyze click.
- Sending attachment binary/base64, private attachment download URLs, cookies, authorization headers, tokens, local paths, macros, or embedded active content to DeepSeek.
- Letting DeepSeek fetch or follow a visible link.
- Transmitting a visible message URL; the remote context records only that a link was present.
- Automatic send, reply, forward, move, delete, archive, price confirmation, delivery commitment, payment commitment, contract acceptance, quality acceptance, or legal commitment.
- Persisting expanded remote model context in SQLite, logs, API responses, docs, tests, or repository fixtures.

## Architecture

```text
explicit Analyze click
  -> current-message-only browser extraction
  -> bounded resource acquisition
  -> local API validation and temporary attachment storage
  -> bounded local thread cleanup and attachment parsing
  -> ephemeral DeepSeek model context
  -> backend-only DeepSeek Chat Completions call
  -> JSON/schema/language/source/grounding/safety validation
  -> field-level hard-safety merge or full rule fallback
  -> SQLite stores only the documented analysis result
  -> side panel displays suggestions and a human-review draft
```

The browser remains an acquisition and display layer. It never receives the DeepSeek key and never calls DeepSeek directly. The backend remains the only model client and the only component that can decide whether a model result is safe to display.

Focused backend units keep the orchestration layer small:

- `attachment_model_context.py` owns ephemeral remote attachment text, secret redaction, and per-item/total character budgets.
- `model_result_safety.py` owns request-source membership, critical-fact grounding, commitment/action checks, and field-level fallback.
- `analysis_budget.py` owns the monotonic backend deadline and remaining model budget.
- `analyzer.py` only coordinates cleaning, parsing, prompt construction, provider invocation, validation, safe merge, and fallback.

## Remote Context Contract

### Visible email and thread

The remote context may include:

- Current visible subject, sender, recipients, copied recipients, and sent time.
- Cleaned current body.
- Up to the existing 50 visible thread segments, with at most 2,000 characters per segment and 20,000 thread-body characters in total.
- A marker that a visible link was present. Every URL is removed before remote context construction; no scheme, host, path, query, fragment, userinfo, or signed parameter is transmitted.
- Backend-determined internal/external role labels and local parser limitations.

When visible thread segments are available, the prompt uses them as the primary source and avoids duplicating the same body as a second full source. When they are unavailable, the bounded cleaned current body is used.

### Supported attachments

The parser will produce an internal attachment analysis bundle with two projections:

1. `display_insight`: the current bounded, display-safe result used by the API, UI, and SQLite.
2. `model_context`: an ephemeral, source-labelled text projection used only while constructing the DeepSeek request.

The model projection is limited to 6,000 characters per accepted attachment and 24,000 attachment characters per request. Existing file-count, byte, type, page, sheet, row, image-pixel, OCR, and decoder limits remain in force. A parser reaching its limit records a limitation instead of claiming complete coverage.

The model projection preserves business identifiers, part numbers, names, email addresses, quantities, measurements, currency amounts, dates, deadlines, quality language, and table relationships because those elements are necessary for useful analysis. It removes or excludes:

- Attachment binary and base64.
- Browser-private attachment download URLs.
- Every other URL or URI, including signed links and values containing userinfo, query strings, or fragments.
- Cookies, authorization values, API keys, access tokens, session identifiers, and credential-shaped values.
- Local and network file paths.
- Macros, embedded executables, scripts, and other active content.
- Text beyond the per-item and total limits.

The backend assigns stable request-local sources such as `thread:0` and `attachment:0`. Source identifiers contain no mailbox ID, account token, private URL, or local path.

### Ephemeral handling

Expanded thread and attachment model context exists only in request memory. It is not logged, returned to the frontend, stored in SQLite, written to a debug output, or added to test snapshots. Existing temporary attachment retention remains a separate local lifecycle and does not authorize remote binary upload.

## DeepSeek Provider Contract

The implementation uses the existing pinned `openai==2.45.0` package with the official OpenAI-compatible DeepSeek endpoint.

Backend configuration:

```text
DEEPSEEK_API_KEY=<backend-only secret>
EMAIL_AGENT_LLM_PROVIDER=deepseek
EMAIL_AGENT_DEEPSEEK_MODEL=deepseek-v4-flash
EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS=25
EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led
```

Provider defaults and restrictions:

- The application default remains `EMAIL_AGENT_LLM_PROVIDER=disabled`.
- The application default for `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE` is `conservative`; model-led consequential fields require the explicit backend value `model_led`.
- The base URL is fixed to `https://api.deepseek.com`; arbitrary remote base URLs are not supported.
- Allowed model names are `deepseek-v4-flash` and `deepseek-v4-pro`.
- `deepseek-v4-flash` is the default because the user requires a bounded synchronous response.
- `deepseek-v4-pro` is available only through backend configuration for synthetic quality/latency evaluation.
- Thinking is explicitly disabled.
- `temperature` is `0`, `stream` is `false`, JSON Output is enabled, and `max_tokens` is bounded at 2,400.
- SDK retries are disabled. A failed request falls back to rules rather than silently spending a second full provider budget.
- The request omits `user_id`. The project does not claim per-user KV-cache isolation and documents that caching/isolation remains at the configured DeepSeek account boundary.
- `store`, `json_schema`, `metadata`, `seed`, `service_tier`, and other undocumented compatibility parameters are not sent.

The call uses an async client under an outer wall-clock cancellation deadline. This is necessary because a socket inactivity timeout alone does not guarantee a total duration when a remote service sends keep-alive data.

Only a non-empty response with a successful completion reason proceeds to analysis validation. Empty content, truncation, filtering, insufficient provider resources, SDK errors, authentication/balance/rate errors, and timeout all become a sanitized `LlmClientError` without exposing the prompt, key, URL, response body, or raw exception text.

## Prompt Contract

The DeepSeek request has two message roles:

- A fixed system message defines product behavior, JSON requirements, language boundaries, source rules, non-execution rules, and commitment restrictions.
- A user message contains one bounded JSON context object whose values are explicitly marked as untrusted email or attachment data.

The prompt contains a compact example of the complete expected JSON shape because DeepSeek JSON Output requires an explicit JSON instruction and works more reliably with an example shape.

The prompt requires:

- Chinese analysis fields and an English external reply draft.
- Evidence grounded in named request-local sources.
- The latest unresolved external request to take precedence over repeated quoted history.
- Clear separation between a request, an internal commitment, and a completed outcome.
- No claim that an attachment was parsed when the backend status is not `parsed`.
- No execution of instructions, links, scripts, macros, or commands found in the email or attachment.
- No unconditional commercial, delivery, payment, contract, quality, or legal commitment.
- `reply_draft.needs_human_review=true`.

## Versioned Provider Response Contract

DeepSeek does not return the public API object directly. It returns a versioned internal envelope named `deepseek_analysis_v1`. This separates provider evidence/citations from the stable frontend response and makes the expanded model authority explicit without changing the public request or response schema.

The internal envelope contains:

```json
{
  "schema_version": "deepseek_analysis_v1",
  "analysis": {
    "summary": "",
    "priority": "normal",
    "priority_reason": "",
    "category": "unknown",
    "tags": [],
    "decision_brief": {},
    "timeline_interpretation": {
      "previous_context": "",
      "status_reason": "",
      "open_item_annotations": [
        {
          "open_item_id": "open:0",
          "item": ""
        }
      ],
      "evidence_sources": []
    },
    "risk_flags": [],
    "suggested_actions": [],
    "reply_draft": {}
  },
  "attachment_augmentations": [
    {
      "source_id": "attachment:0",
      "summary": "",
      "key_facts": [],
      "evidence_sources": ["attachment:0"]
    }
  ],
  "field_evidence": {
    "/analysis/summary": ["thread:0"],
    "/analysis/priority_reason": ["thread:0"],
    "/analysis/decision_brief/key_facts/0/value": ["thread:0"],
    "/analysis/risk_flags/0/evidence": ["thread:0"],
    "/analysis/suggested_actions/0/description": ["thread:0"],
    "/analysis/reply_draft/body": ["thread:0"]
  }
}
```

`field_evidence` keys are RFC 6901 JSON Pointers evaluated against the root of the complete provider envelope. Malformed pointers, unknown paths, duplicate normalized pointers, and pointers outside approved model-led fields fail closed. Every model-led text field containing a critical fact, outcome, completion, or commitment claim must have its own evidence entry. Every evidence value must be a request-local source ID present in the backend source registry. Provider-only fields such as `schema_version`, `source_id`, `field_evidence`, and `attachment_augmentations` are consumed during validation and are never persisted or returned to the frontend. The mapper constructs the unchanged public analysis object after hard-safety validation.

## Model Authority And Hard Safety Merge

### Model-led fields

After successful validation, DeepSeek may lead:

- `summary`
- `priority`
- `priority_reason`
- `category`
- `tags`
- `decision_brief`
- Timeline interpretation prose and matched open-item wording around the backend factual skeleton
- `risk_flags`
- `suggested_actions`
- `reply_draft.subject`
- `reply_draft.body`
- `reply_draft.review_reasons`
- Parsed attachment summaries and key facts that pass source and grounding checks

### Backend-owned invariants

The backend always owns:

- `analysis_engine.source` and `analysis_engine.label`.
- The set and order of accepted/limited attachments.
- Attachment filename, type, parse status, and parser limitations.
- The requirement that only a backend-`parsed` attachment can contribute model attachment facts.
- The factual timeline skeleton: ordered source registry, `current_status`, `latest_external_request`, `latest_internal_commitment`, and source membership. DeepSeek may improve interpretation, explanation, and wording but cannot erase or replace this skeleton.
- The complete timeline open-item skeleton: stable `open_item_id`, item set, order, source, owner, and due fields. DeepSeek may rephrase the `item` text for a known ID, but unknown IDs are rejected, omitted backend items are restored, and model ordering is ignored.
- Mandatory locally detected `prompt_injection_risk`, `security_risk`, and `commitment_risk` entries. DeepSeek may add validated risks or improve prose, but it cannot remove or downgrade those backend risks.
- Schema enums, object/list shapes, count limits, text limits, and language boundaries.
- `reply_draft.needs_human_review=true`.
- The absence of automatic mailbox operations.
- The absence of unconditional price, delivery, payment, contract, quality, or legal commitments.

### Grounding checks

The backend treats model JSON as untrusted and applies these checks before display:

1. Every referenced attachment source must match one accepted request-local attachment source.
2. A fact attributed to an attachment must come from an attachment whose backend status is `parsed`.
3. Critical identifiers, quantities, amounts, measurements, dates, completion claims, and commitment claims in every model-led text field must normalize to evidence present in the claimed source context. This includes summary, priority reason, timeline prose/open items, Decision Brief, risk evidence/recommendations, suggested actions, attachment augmentations, draft subject/body, and review reasons.
4. A model cannot add, rename, or change the status of an attachment.
5. Model-provided source strings are projected to an allowlist of current request sources.
6. Model output cannot introduce HTML, executable links, scripts, or tool-call instructions into the displayed result.
7. The final risk list is a union in which mandatory backend safety risks retain at least their backend severity and recommendation. A model cannot remove or downgrade them.
8. The backend factual timeline skeleton is projected after model validation so model JSON cannot change its source membership or authoritative status/request/commitment fields.
9. Open-item annotations are joined only by stable backend `open_item_id`. The mapper preserves every backend item and its order/source/owner/due fields, applies only grounded wording for matched IDs, rejects unknown IDs, and restores original wording for missing or invalid annotations.

These checks reduce fabricated critical facts but do not claim perfect semantic accuracy. Human review remains mandatory.

### Field-level fallback

When a violation is isolated, the backend keeps safe model analysis and replaces only the unsafe field:

- Unsafe or unconditional reply commitment: use the deterministic fallback draft and add a review reason.
- Unauthorized or auto-executing suggested action: use deterministic fallback actions.
- Invalid Decision Brief action/reply recommendation: use the deterministic fallback Decision Brief.
- Invalid attachment summary/fact/source: keep the backend attachment status and use the deterministic attachment insight.
- Invalid timeline structure or source: use the deterministic timeline.
- Unsupported critical fact, completion claim, or commitment in summary/priority reason/risk/action/draft prose: replace that individual public field with its deterministic counterpart; if safe isolation is not possible, reject the full model result.

If JSON parsing, required schema, language boundaries, or overall source integrity fails, the entire model result is rejected and the complete deterministic rule result is returned.

## Timeout Semantics

The approved synchronous budgets are:

- Browser extension and local debug page: wait up to 35 seconds for `POST /api/analyze-current-email`.
- Backend analysis target: 32 seconds from the start of local API handling, measured by one monotonic clock across storage, parsing, provider work, validation, persistence preparation, and response construction. This is a cooperative target rather than a hard end-to-end guarantee because bounded request reading, local attachment writes, and SQLite calls are synchronous.
- Fixed validation/response margin: 2 seconds reserved at the end of the backend deadline.
- Attachment parse/OCR budget within the backend request: at most 8 seconds in total for model-context preparation. PDF, XLSX, DOCX, image decoding, and OCR run in spawn-based worker processes. At deadline, the backend terminates and joins the worker, discards partial private output, and emits a safe limitation for that attachment. Remaining attachments degrade without starting another worker.
- DeepSeek attempt: `min(25 seconds, remaining backend time minus the fixed 2-second validation/response margin)`.
- If less than 5 seconds remains for DeepSeek, skip the model and immediately return rule fallback.
- Bounded synchronous attachment storage and SQLite persistence receive monotonic before/after checks. SQLite uses a busy timeout below the remaining 2-second response margin. These checks reduce overruns but are not described as cancellation of an in-progress operating-system write.

The 35-second frontend wait begins after browser resource collection. Current browser resource collection has its own maximum 20-second budget, so this design does not claim a strict 35-second Analyze-click-to-result guarantee. That distinction is documented in the UI/API operations guidance.

The browser abort does not reliably cancel server work. The backend therefore enforces its own deadline and must not depend on the frontend timer for cancellation.

## Failure Handling

The deterministic rule result is built before accepting model output and is always available for fallback.

Rule fallback is returned when:

- The provider is disabled or its key is missing.
- The backend request has insufficient remaining time.
- DeepSeek times out or returns an API/SDK error.
- Content is empty, truncated, filtered, or otherwise incomplete.
- JSON parsing, schema, language, source, or global safety validation fails.
- A field-level violation cannot be isolated safely.

DeepSeek failure does not trigger Ollama. This avoids another long model attempt after the response budget has already been consumed.

The frontend receives a successful analysis response with `analysis_engine.source=rule_fallback` whenever the rule result is valid. Provider details and secret-bearing error text are not returned.

## Privacy And External Processing

DeepSeek is an external processor. Its current API documentation says disk context caching is enabled by default and does not document a request option that disables it. Its current public privacy policy describes collection of prompts/inputs and processing/storage in the People's Republic of China. The project therefore does not describe this route as local-only or zero-retention.

The user accepted this condition for every Analyze click in this local installation while both `deepseek` and `model_led` are configured. Persistent pre-click disclosure states that the current visible thread and bounded attachment extraction will be sent to the configured remote provider. Operators must disable or switch the backend to conservative/rule-only mode before analyzing any message that is not authorized for external processing. The application does not silently choose DeepSeek when provider configuration is absent.

## Accuracy And Evaluation Gate

No generative model can guarantee semantic correctness. Before recommending real-mail use, the implementation must support a synthetic evaluation run covering at least 50 representative business scenarios, including orders, RFQs, delivery, payment, contracts, complaints, quality issues, new-product development, internal messages, long threads, prompt injection, and supported attachments.

Release evidence targets:

- Valid model result or valid rule fallback: 100 percent.
- Fabricated critical identifier/amount/date accepted into grounded key facts: 0.
- Unsafe automatic action or unconditional commercial/legal commitment accepted: 0.
- Category and priority agreement with the reviewed synthetic gold set: at least 90 percent.
- Reply draft remains English and requires human review: 100 percent.
- Provider attempt respects the backend deadline: 100 percent.

These are release gates for the evaluated set, not a promise that future unseen email will be error-free or that every local filesystem/database operation will complete within the cooperative backend target.

## Testing Strategy

Implementation follows test-driven development. Tests use only synthetic or generated content.

Required coverage:

- DeepSeek config defaults, model allowlist, backend-only key, fixed official endpoint, and output-mode opt-in.
- Exact provider request shape, non-thinking JSON mode, zero retries, output limit, total cancellation, completion reasons, and sanitized exceptions.
- Positive remote-context coverage for visible thread, business identifiers, quantities, amounts, dates, deadlines, table relationships, and OCR text.
- Negative canaries for binary/base64, every URL/URI shape, cookies, authorization values, tokens, local paths, active content, logs, SQLite, API responses, and text beyond limits.
- Persistent pre-click external-processing disclosure under the operator-wide consent model.
- Versioned provider-envelope parsing, evidence/source registry validation, attachment augmentation mapping, and unchanged public response projection.
- Model-led Decision Brief, timeline, risks, actions, and draft.
- Stable timeline open-item identity/set/order/source/owner/due projection with grounded model wording only.
- Attachment status/source ownership, all-field critical-fact/completion/commitment grounding, mandatory backend safety-risk union, field-level replacement, and full rule fallback.
- Terminable parser/OCR worker-process behavior, partial-output disposal, hard 8-second parser deadline, cooperative 32-second backend target, SQLite busy timeout, and fixed 2-second response margin.
- No DeepSeek-to-Ollama chain.
- 35-second frontend POST deadline and bounded backend remaining-budget behavior.
- Existing current-message click gate, current-message-only DOM trust, no automatic mailbox actions, architecture guards, linter guards, and mechanical constraints.

Automated tests never call the live DeepSeek service. A live A/B evaluation of Flash and Pro uses only synthetic prompts, a locally supplied backend key, and separate operator approval after deterministic tests pass.

## Documentation And Decision Records

Implementation must update:

- `AGENTS.md`
- `.env.example`
- `README.md`
- Provider, architecture, linter, API, prompt, privacy, email-data, setup, deployment, troubleshooting, testing, feature-scope, and roadmap documents
- An ADR recording the approved remote provider, expanded model authority, privacy acceptance, and rollback
- The task brief execution record
- The generated project status log

No public request or response schema change is required. The existing `analysis_engine.source` values remain `ai_model` and `rule_fallback`; the backend label identifies DeepSeek without exposing endpoint or key details.

## Rollout

1. Implement provider and safety/context boundaries with the provider and model-led output disabled by default.
2. Complete focused tests, full regression tests, architecture/static/mechanical guards, JavaScript syntax checks, maintenance scan, and status generation.
3. Run the synthetic evaluation gate with mocked provider responses. A live synthetic Flash/Pro comparison remains a separately approved optional step.
4. Enable `deepseek` and `model_led` only in the backend local environment after a key is configured and the operator accepts external processing.
5. Perform a user-controlled Tencent Exmail smoke test only after separate authorization. It is not part of automated development verification.

## Rollback

Immediate operational rollback is:

```text
EMAIL_AGENT_LLM_PROVIDER=disabled
```

Restarting the backend then restores deterministic rule-only analysis. Setting the output mode back to the conservative projection disables DeepSeek-led consequential fields while retaining the provider integration for comparison. Code rollback removes the DeepSeek provider, ephemeral expanded attachment context, model-led merge, and timeout changes without altering the no-action mailbox boundary.

## Official DeepSeek References

- First API call and current models: `https://api-docs.deepseek.com/`
- JSON Output: `https://api-docs.deepseek.com/guides/json_mode/`
- Thinking mode: `https://api-docs.deepseek.com/guides/thinking_mode/`
- Chat Completions reference: `https://api-docs.deepseek.com/api/create-chat-completion/`
- Error codes: `https://api-docs.deepseek.com/quick_start/error_codes/`
- Context caching: `https://api-docs.deepseek.com/guides/kv_cache/`
- Current privacy policy: `https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html`
