---
last_update: 2026-07-20
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0007: Multimodal current-email analysis

## Status

Accepted by the operator on 2026-07-16. Implementation and release verification are in progress.

## Context

The current extension frequently requires manual text selection because the real Tencent Exmail message is rendered in a same-origin `mainFrame` that is rejected by the resource path. Local OCR cannot explain business photos without text, and the existing DeepSeek route cannot consume images. The 15-second POST and 13-second backend budgets are also too short for bounded visual inference plus a safe fallback.

The operator selected option C after reviewing provider capability and price: one high-quality multimodal main model for the whole clicked current-message scope, DeepSeek as a text-only fallback, and deterministic rules last. The operator explicitly authorized selected current-message images and files to be sent to the configured remote visual provider and authorized multiple API calls during the final test phase. This does not authorize mailbox scanning.

## Decision

### Acquisition boundary

- The extension remains click-only and uses one top-level content script.
- It may access one unique visible same-origin Tencent `mainFrame` only after validating the frame, current message, and read-message evidence.
- It collects the current body, reliably reconstructed visible history, visible attachments, and visible inline business images belonging to that message.

Attachment acquisition amendment, 2026-07-18:

- Automatic attachment bytes may come from a verified legacy current-message control only after the user clicks Analyze. The fetch is same-origin, credentialed, redirect-failing, bounded, and held in browser memory only.
- The optional picker selection is inert until Analyze; file bytes are read only inside that Analyze lifecycle and are never copied to browser storage or the system Downloads directory.
- Automatic and manual inputs share 5 files, 10 MiB per file, and 25 MiB total. The payload remains the existing path-free `attachment_files` projection.
- The backend owns request-local temporary files. Every request exit invokes deletion from request `finally`. The 24-hour mtime cleanup is crash recovery only; it is not normal retention and is not scheduled.
- Only `attachment_insights[].status == "parsed"` proves content parsing. Metadata, a discovered control, or an array count does not.
- It excludes signatures, portraits, logos, icons, tracking pixels, hidden media, external media, repeated signature media, and ambiguous ownership.
- It revalidates the document, message, and resource binding after asynchronous reads. Any navigation or DOM identity change discards collected bytes.

### Provider route

- `EMAIL_AGENT_LLM_PROVIDER=disabled` remains the application default.
- Explicit `EMAIL_AGENT_LLM_PROVIDER=openai` selects the multimodal route.
- The OpenAI model allowlist initially contains only `gpt-5.6-sol` and uses the backend SDK pinned at `openai==2.45.0`.
- The client uses the fixed official endpoint, Responses API, `store=false`, `max_retries=0`, `stream=false`, no tools, low output verbosity, and at most 2,400 output tokens. OpenAI omits `text.format`; the JSON-only prompt is enforced by strict local validation.
- Images use metadata-stripped bounded data URLs with `detail=high`. PDFs use rewritten bounded in-memory file data. DOCX/XLSX contribute locally extracted deidentified text; bounded embedded images are separately sanitized and supplied as images.
- The Files API, private URLs, original filenames, paths, cookies, authorization data, and tokens are forbidden.
- Gemini is not added to production in this task. It may be evaluated later as a challenger through a separate decision.

### Fallback route

- `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled` remains the default.
- When explicitly set to `deepseek`, the OpenAI route may make one additional text-only DeepSeek call only after an OpenAI failure and only when at least 12 seconds remain in the shared backend budget.
- Each provider call has zero SDK retries. A request makes at most one OpenAI call and at most one DeepSeek call.
- DeepSeek never receives image or file bytes. If the second call is disabled, unsafe, invalid, late, or unavailable, the deterministic rule result returns.
- The displayed engine label identifies the provider that produced the accepted result. A rule fallback includes a fixed content-free reason code.

### Privacy and media boundary

- All outbound text is locally deidentified and residual-scanned.
- Selected image pixels and sanitized PDF content cannot be represented as fully deidentified. They are sent only under this explicit opt-in provider route and persistent disclosure.
- Images are decoded, orientation-normalized, metadata-stripped, animation-flattened, pixel-bounded, and downscaled before encoding.
- PDFs are magic-checked, encryption-rejected, page-bounded, and rewritten without metadata, JavaScript, embedded files, forms, open actions, additional actions, or annotations before provider input.
- Office embedded images are extracted under entry and aggregate limits, then pass the same image sanitizer.
- Provider media uses opaque request-local names and source IDs. No path, URL, filename, binary, Base64, source ID, prompt, or raw response enters logs, public HTTP, SQLite, docs, tests, or Git.
- Request temporary files are deleted immediately after analysis rather than retained for 24 hours. No physical secure-erasure claim is made. The 24-hour mtime sweep is only a later crash-recovery safeguard for orphaned request files.

### Contract and model authority

- The existing compatibility-named `deepseek_analysis_v1` private envelope remains the single model-result contract for both remote providers in this release. It is not public or persisted.
- The JSON-only system prompt is enforced by the duplicate-key-safe local parser and the private-envelope, schema, evidence, privacy, grounding, and safety validators. The dynamic evidence-pointer map has not yet passed a strict Structured Outputs compatibility gate, so this release does not switch to `json_schema`.
- Live compatibility amendment, 2026-07-17: `text.format.type=json_object` was rejected by the live GPT-5.6 Sol Responses route, while the same bounded request without `text.format` was accepted. The provider-format override is therefore omitted without weakening any local validation gate.
- Visual live amendment, 2026-07-17: the internal `UNTRUSTED_MEDIA` marker correctly failed the residual privacy scan and therefore never leaves the backend. OpenAI instead receives one fixed deidentified natural-language source description; DeepSeek continues to omit visual-only sources. The OpenAI-only prompt requires one source-bound attachment augmentation with evidence for every leaf when a listed observation is visible. A recreated no-text business-photo smoke passed this route with no rule fallback.
- Task 9 amendment, 2026-07-20: prior synthetic and current-clicked smokes remain valid evidence for acquisition, routing, status, and cleanup only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Offline release gates now enforce current/history evidence alignment, explicit attachment semantic coverage, deterministic reconciliation safeguards, and the private human gold-standard contract in `docs/superpowers/plans/2026-07-20-task9-semantic-accuracy-repair.md`. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.
- Text and each media item are paired with an opaque source marker. Visual media reuses existing attachment evidence IDs.
- Visual sources may ground qualitative business observations such as packaging damage, label position, component presence, layout, or visible quality condition. They cannot ground a person identity, protected attribute, exact identifier, date, amount, quantity, tracking value, or consequential commitment.
- Exact business facts remain local-rule-owned and are merged only from verified deterministic extraction.
- All outputs retain schema, language, source, grounding, privacy, action, commitment, and human-review validation.

### Budgets

- Browser and local-debug POST timeout: 60 seconds.
- Backend shared analysis target: 55 seconds.
- Local parser maximum: 8 seconds.
- OpenAI provider cap: 35 seconds.
- DeepSeek provider cap: 10 seconds.
- Minimum remainder before a DeepSeek fallback: 12 seconds.
- Persistence and response reserve: 5 seconds.
- Browser resource collection remains separately bounded at 20 seconds after the click.

From this decision forward, these normal-runtime budgets supersede the earlier
15-second frontend / 13-second backend contract recorded by the completed
DeepSeek implementation brief. The private-evaluation dataset runner keeps its
separate 13-second budget and is not changed by this decision.

## Consequences

- Business photos without OCR text can contribute useful, source-bound analysis.
- A failed main provider can still produce a stronger text result when the explicit fallback and budget permit it.
- Worst-case clicked analysis can take materially longer than the prior 15 seconds and can contact two remote providers. The UI and disclosure must make this clear.
- Media may contain identifying information even after metadata stripping. Users must not click Analyze when remote media processing is not permitted; the disabled rule route remains the rollback.
- The public API and SQLite remain compatible, but internal routing, evidence, media sanitation, and test coverage expand.

## Rollback

Set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the service. To keep OpenAI but prevent a second remote call, set `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled`. No database rollback is required.

## Official references

- [GPT-5.6 Sol model](https://developers.openai.com/api/docs/models/gpt-5.6-sol)
- [Images and vision](https://developers.openai.com/api/docs/guides/images-vision)
- [File inputs](https://developers.openai.com/api/docs/guides/file-inputs)
- [Data controls](https://developers.openai.com/api/docs/guides/your-data)
