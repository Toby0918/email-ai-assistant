---
last_update: 2026-07-12
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0005: DeepSeek-led current-email analysis

## Status

Accepted and active. The written design review completed on 2026-07-12. Final release verification remains a separate Task 14 activity.

## Context

The previous 15-second frontend wait was shorter than useful model execution, and the conservative repair route discarded most consequential model fields. The approved change allows a stronger remote model to lead analysis while preserving the first-phase boundary: one explicit Analyze click, one currently visible email scope, no mailbox scan, and no automatic mailbox action.

DeepSeek is an external processor. Its documented disk context cache and privacy terms prevent this route from being represented as local-only or zero-retention.

## Decision

### Provider and dependency

- The endpoint is fixed in backend code at `https://api.deepseek.com`; users cannot configure an arbitrary remote base URL.
- Allowed models are `deepseek-v4-flash` and `deepseek-v4-pro`. Flash is the default; Pro is available only through backend configuration.
- The integration reuses the pinned `openai==2.45.0` OpenAI-compatible SDK. No unofficial or third-party DeepSeek package is added.
- The request uses JSON object output, `stream=false`, and non-thinking mode through `extra_body={"thinking":{"type":"disabled"}}`.
- The SDK uses zero retries and the analyzer performs one provider call. A failed DeepSeek attempt falls back to rules and does not chain to Ollama.

### Activation gates and rollback flags

The safe application defaults remain:

```text
EMAIL_AGENT_LLM_PROVIDER=disabled
EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative
```

DeepSeek-led consequential fields require both explicit backend settings:

```text
EMAIL_AGENT_LLM_PROVIDER=deepseek
EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led
```

Operational rollback sets `EMAIL_AGENT_LLM_PROVIDER=disabled` and restarts the backend. Authority rollback sets `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative`, retaining the provider integration while disabling model-led consequential fields.

### Data and schema boundaries

- The public analysis request and response schema remains unchanged, and SQLite gains no new columns.
- DeepSeek returns an internal `deepseek_analysis_v1` envelope with request-local sources and `field_evidence`. Provider-only fields never enter the public response or SQLite.
- The backend may send the bounded current visible thread and ephemeral sanitized attachment text. Attachment bytes/base64, URLs, cookies, authorization values, tokens, local paths, active content, and unbounded source text are excluded.
- Expanded model context remains request-local and is excluded from API responses, SQLite, logs, debug output, documentation, and repository fixtures.

### Model authority and safety

A valid model result may lead summary, priority, category, Decision Brief, timeline interpretation, added risks, suggested actions, and the English reply draft. The backend remains authoritative for:

- JSON/schema/enums and language boundaries.
- `analysis_engine` and `reply_draft.needs_human_review=true`.
- Attachment membership, filename/type/status/limitations, and parsed-source eligibility.
- Timeline and open-item membership/order/source/owner/due skeletons.
- Mandatory local prompt-injection, security, and commitment risks.
- Critical-fact grounding, source membership, no mailbox actions, and no unconditional commercial/legal commitments.

An isolated unsafe or unsupported field uses deterministic field fallback. A malformed envelope, language/source/global safety failure, empty/truncated response, timeout, provider error, or violation that cannot be isolated uses the complete rule fallback.

### Deadlines and persistence

- Frontends wait 35 seconds for the POST after independent browser resource collection, which has its own 20-second maximum.
- After the validated request body is read, the backend starts a cooperative 32-second monotonic target, with an 8-second hard parser/OCR process deadline, a provider maximum of 25 seconds, a provider minimum of 5 seconds, and a fixed 2-second validation/response reserve.
- SQLite uses one 0.5-second cumulative stage for lock/INSERT/commit with a 0.25-second response floor. Busy timeouts are recomputed from the same stage deadline.
- Persistence must commit before success. Failure returns `PERSISTENCE_FAILED`. A rollback failure closes and quarantines the connection so a pending transaction cannot be reused.

### Disclosure and evaluation

The browser extension and local debug page retain a persistent pre-click disclosure that a configured remote provider receives the current visible thread and bounded attachment extraction. This disclosure does not expand collection or mailbox permissions.

The deterministic release artifact contains exactly 50 synthetic cases with unique IDs, unique synthetic provenance, complete recorded rule/model public results, structured `source_id`/text evidence, explicit expected risks/facts/actions/forbidden commitments, and review labels. `scripts/evaluate_deepseek_analysis.py` runs offline without a key or network. It applies the production `validate_analysis_result` validator to both recorded public results, derives schema pass instead of accepting a schema label, and reuses the production critical-signature normalizer so every amount, date/deadline, business identifier, quantity/measurement, outcome, and commitment signature in the selected public result must also exist in the synthetic evidence. Commitment/action safety additionally reuses the production `has_unsafe_operation` and `has_unconditional_commitment` predicates over the selected result, rather than relying only on fixture substrings. It derives the remaining labels and rejects any human label that disagrees with those checks. Exactly ten fallback selections correspond to provider timeout, malformed JSON, disabled provider, unsafe commitment, or automatic-action safety failure; normal scenarios select the model result. The script reports only case count, schema pass rate, mandatory-risk retention, unsupported-critical-fact case count, commitment/action violation count, fallback rate, and ordered nonnegative latency samples when recorded.

## Consequences

- The model can materially improve displayed analysis while hard backend invariants remain enforceable.
- Remote processing and provider-side caching/storage risk must be disclosed and accepted before use.
- Rule-only analysis remains available immediately through configuration rollback.
- Synchronous limits are bounded but are not a strict Analyze-click-to-result guarantee because browser collection and some local I/O are separate synchronous stages.
- Automated verification never requires a live key. Any live synthetic comparison or real-mail validation needs separate authorization.

## Official sources rechecked 2026-07-12

- [Models, endpoint, and deprecation](https://api-docs.deepseek.com/quick_start/pricing/)
- [Chat Completions models, JSON output, and parameters](https://api-docs.deepseek.com/api/create-chat-completion)
- [Thinking-mode toggle and OpenAI SDK extra_body](https://api-docs.deepseek.com/guides/thinking_mode)
- [Default best-effort disk cache and usual clearing window](https://api-docs.deepseek.com/guides/kv_cache/)
- [Current privacy policy for inputs and PRC processing/storage](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html)
