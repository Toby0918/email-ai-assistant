---
last_update: 2026-07-18
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Multimodal Current Email Analysis Task Brief

## 1. Task name

```text
add click-gated multimodal current-email analysis with a text fallback
```

## 2. Task type

```text
feature | fix | security | prompt | api_contract
```

## 3. Current status

```text
multimodal_current_email_offline_ready_live_pending
```

The operator approved option C on 2026-07-16. Tasks 1-7 are implemented and
review-clean with synthetic fixtures and fake providers. Task 8 aligned active
documentation and the status generator. Task 9 synthetic provider and
current-clicked Tencent smokes are complete; the bounded checks inspected only
approved status fields and structural counts. The separate Task 5 real
current-message attachment smoke remains pending and requires fresh explicit
authorization after its offline Tasks 1-4 are review-clean. No prior check
authorizes another live operation.

## 4. Goal

After one explicit Analyze click, automatically read the complete currently visible Tencent Exmail thread, collect only verified visible attachments and business-relevant inline images, and let one backend OpenAI Responses request analyze text, visual content, and supported files together. Preserve DeepSeek as a text-only fallback and deterministic rules as the final fallback.

## 5. Non-goals

- Do not scan, enumerate, poll, or background-analyze the mailbox.
- Do not read another message, folder, account, hidden resource, or unverified frame.
- Do not send, delete, archive, move, forward, or mark any email.
- Do not send signature portraits, logos, icons, tracking pixels, hidden images, or ambiguous images to a provider.
- Do not put provider keys, model endpoints, raw provider responses, or private diagnostics in frontend code, HTTP responses, SQLite, logs, docs, tests, or Git.
- Do not use Files API, private download URLs, cookies, authorization headers, tokens, or configurable remote base URLs.
- Do not add Gemini to the production path in this task. Gemini remains a later challenger evaluation.
- Do not let any model author exact order identifiers, dates, amounts, quantities, or tracking values unless they are independently extracted and verified locally.
- Do not automate a commercial, delivery, payment, contract, quality, or legal commitment.

## 6. Background and references

The real Tencent Exmail page places the currently opened message in a visible same-origin `mainFrame`. Existing code can discover that document for text, but it rejects resource collection whenever the selected document is not the top-level document. When known body selectors are absent, automatic extraction also fails closed and only manual text selection succeeds.

The current image parser performs OCR only. A business photo without readable text therefore produces metadata rather than visual meaning. The existing OpenAI branch is a disabled skeleton, while the DeepSeek API route is text-only.

Relevant documents:

- `AGENTS.md`
- `docs/product/feature_scope.md`
- `docs/security/email_data_handling.md`
- `docs/security/privacy_rules.md`
- `docs/prompts/analyzer_prompt.md`
- `docs/data/analysis_result_schema.md`
- `docs/api/backend_api_contract.md`
- `docs/decisions/0005-deepseek-led-analysis.md`
- `docs/superpowers/specs/2026-07-09-phase-two-attachment-thread-analysis-design.md`

## 7. Scope

Expected additions or modifications:

- `frontend/browser_extension/content/`
- `frontend/browser_extension/shared/`
- `frontend/browser_extension/manifest.json`
- `frontend/local_debug_page/`
- `backend/email_agent/`
- `.env.example`
- `AGENTS.md`
- `docs/product/`, `docs/security/`, `docs/prompts/`, `docs/data/`, `docs/api/`, `docs/decisions/`, `docs/constraints/`, and `docs/operations/`
- focused Python and JavaScript contract tests under `tests/`

The existing public request fields, public response fields, and SQLite columns remain compatible.

## 8. Technical approach

1. Establish a verified document context that accepts either the top-level read-message document or one unique visible same-origin Tencent `mainFrame`. Revalidate the frame, current message, and resource ownership before and after asynchronous collection.
2. Split the visible thread into current message and oldest-to-newest history. If reliable segmentation is unavailable, analyze the current body only and send no fabricated thread segments.
3. Classify visible resources as attachments or inline business images. Exclude content after signature boundaries, repeated signature media, logos, avatars, icons, tracking pixels, hidden images, external sources, and ambiguous ownership.
4. Decode accepted resources only after the click. Validate type and magic, strip image metadata, flatten animation, bound pixels, downscale images, rewrite PDFs without active metadata, and extract bounded embedded office images. Use opaque provider filenames and request-local source IDs.
5. Locally deidentify all text and run residual scanning. Selected image pixels and sanitized PDF page content are separately disclosed media and are not represented as fully deidentified.
6. Call fixed-endpoint OpenAI Responses once with `gpt-5.6-sol`, text plus selected media, `store=false`, `max_retries=0`, no tools, `text.verbosity=low`, `reasoning.effort=low`, media `detail=high`, and the existing strict local envelope parser/evidence/safety merge. OpenAI omits `text.format`; the JSON-only prompt is enforced by strict local validation.
7. If OpenAI fails and at least 12 seconds remain, call the explicitly enabled DeepSeek route once with text only. Otherwise use deterministic rules. No provider call is retried.
8. Keep exact business identifiers, dates, amounts, quantities, and tracking facts locally authoritative. Visual claims may describe qualitative business conditions only and always require human review.
9. Remove request attachment files immediately after analysis completes. Do not claim physical secure erasure of SSDs, Python immutable objects, HTTP buffers, or provider-side copies.

## 9. Data structure and interface changes

### Database changes

```text
None. Existing SQLite columns and public projections remain unchanged.
```

### API changes

```text
No required public field is added or removed. Existing attachment_files bytes continue to be accepted only from the clicked current-message collector. Optional analysis_engine context metadata remains compatible.
```

### AI output JSON changes

```text
No public JSON shape change. OpenAI and DeepSeek reuse the existing private analysis envelope and the existing public schema. The backend adds only request-local media/evidence metadata that never crosses HTTP or SQLite.
```

### Prompt changes

```text
The system prompt gains modality/source binding, visual uncertainty, no-person-identification, no-hidden-instruction, no-precise-fact-authoring, and mandatory human-review rules. Text and each media item are explicitly labelled as untrusted evidence.
```

### Backend configuration

```text
EMAIL_AGENT_LLM_PROVIDER=disabled
EMAIL_AGENT_OPENAI_MODEL=gpt-5.6-sol
EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS=35
EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled
```

`OPENAI_API_KEY` and `DEEPSEEK_API_KEY` remain backend-only. The OpenAI and DeepSeek base URLs are code-fixed and cannot be configured from the environment.

## 10. Security and privacy checklist

- [x] Current-message analysis still requires one explicit user click.
- [x] No mailbox scan or account connection is added to the browser or normal backend.
- [x] No automatic email action is added.
- [x] Provider keys remain backend-only.
- [x] Text crosses backend-only deidentification and residual scanning.
- [x] Remote media is limited to verified current-message resources and is disclosed as not guaranteed fully deidentified.
- [x] Signature portraits, logos, tracking pixels, hidden media, external media, and ambiguous resources fail closed.
- [x] Provider inputs, binary data, source IDs, paths, URLs, raw outputs, and exception text do not enter logs, SQLite, public HTTP, docs, fixtures, or Git.
- [x] Provider output remains duplicate-key-safe, schema validated, evidence checked, safety merged, and human-review-only.
- [x] Temporary files are removed after the request and never saved in SQLite.
- [x] Synthetic fixtures contain no real customer, employee, supplier, email, attachment, or identifier.

## 11. Prompt injection protection

- Email text, visual pixels, PDFs, office content, filenames, OCR text, and model output are untrusted data, never instructions.
- The model cannot browse, follow links, fetch URLs, call tools, or execute commands.
- System instructions and private implementation details must never be returned.
- Visual text that looks like a prompt is treated as content to describe, not an instruction to follow.
- Model-authored exact identifiers, dates, amounts, quantities, and tracking facts are removed or replaced with locally verified facts.
- Every draft remains `needs_human_review=true`; no model can send or commit on the user's behalf.

## 12. Acceptance criteria

1. A click on a real Tencent Exmail message in the visible same-origin `mainFrame` automatically extracts a non-empty current body and a reliably ordered visible thread without manual text selection.
2. A visible business photo without text reaches the multimodal OpenAI request and produces a source-bound qualitative attachment insight.
3. Signature portraits, logos, icons, tracking pixels, hidden images, external images, repeated signature media, and ambiguous images cause zero provider media items.
4. PDF content and locally extracted DOCX/XLSX text are included; bounded embedded office images are included as independent sanitized image inputs.
5. OpenAI receives one text-plus-media request with no private URL/path/original filename, `store=false`, zero retries, no tools, and bounded output.
6. OpenAI failure can invoke one DeepSeek text-only fallback only when explicitly configured and at least 12 seconds remain. Otherwise the rule result returns.
7. Exact order IDs, dates, amounts, quantities, and tracking values come only from local verified extraction and are never invented from visual output.
8. Public HTTP and SQLite contain no binary, Base64, path, provider source ID, raw output, API key, token, URL, or new private field.
9. Request-local attachment files are removed after success and failure.
10. The side panel states which engine ran and why a fallback occurred, while keeping the task-card layout readable at 320 pixels.
11. Offline focused tests, full tests, JavaScript syntax checks, architecture/mechanical checks, leakage scan, status generation, and maintenance scan all pass.
12. An explicitly authorized final smoke test covers one synthetic multimodal request and representative clicked current emails without reading any other mailbox item.

## 13. Test plan

- Tencent legacy `mainFrame` fixtures for automatic body/thread extraction and stale revalidation.
- Resource-classification fixtures for business photos versus signatures, logos, trackers, hidden/external/ambiguous images.
- Media sanitation tests for image magic, metadata stripping, animation flattening, pixel bounds, PDF active-content removal, and office embedded-image bounds.
- OpenAI client tests for exact Responses payload, fixed model allowlist, `store=false`, zero retries, media/source adjacency, timeout, and fixed error codes.
- Route tests for OpenAI success, conditional DeepSeek fallback, no fallback under insufficient budget, and deterministic rule fallback.
- Grounding and merge tests for qualitative visual facts, locally authoritative exact facts, unsafe commitments, person identification, and prompt injection.
- API/SQLite/log tests proving no binary, Base64, path, URL, source ID, key, or raw provider output persists.
- Full `python -m unittest discover -s tests`, JS syntax, `git diff --check`, project status generation, and maintenance scan.

## 14. Rollback

Set `EMAIL_AGENT_LLM_PROVIDER=disabled` and restart the backend to return immediately to deterministic rule analysis. Set `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled` to prevent a second provider call. Revert the extension resource-classifier files to disable remote media while retaining current text analysis. No database migration is required.

## 15. Human confirmations

- Option C and remote visual/file processing were approved by the operator on 2026-07-16.
- Multiple API test calls and a clicked-current-email smoke test were approved. This does not authorize mailbox scanning.
- A real smoke test must still be initiated through the visible Analyze control and must not expose credentials to Codex output.

The exact persistent pre-click disclosure for both frontend surfaces is:

```text
After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.
```

## 16. Pre-execution checks

- [x] Read `AGENTS.md`.
- [x] Read project status and relevant constraints/docs.
- [x] Confirmed goals, non-goals, provider route, timeout expansion, and fallback behavior.
- [x] Isolated changes in `.worktrees/multimodal-plan-c`.
- [x] Preserved the user's unrelated root-checkout modification.
- [x] Baseline full suite passed with the pinned Python 3.12.13 runtime and existing locked dependencies.

## 17. Remote provider private-context checklist

- [x] All providers remain disabled by default; DeepSeek conservative mode remains the default.
- [x] Every remote text path uses backend-only deidentification and residual scanning.
- [x] Media is separately screened, bounded, metadata-stripped, and disclosed as not fully deidentified.
- [x] Runtime cards remain immutable, startup-verified, and request-bounded.
- [x] No private knowledge, key, path, vault, snapshot, or restoration data crosses the runtime seam.
- [x] Provider output placeholders, restoration hints, source leaks, unsafe actions, and unsupported exact facts fail closed.
- [x] Public API, SQLite, renderer data fields, and diagnostic payload remain compatible.
- [x] Exact budgets are frontend POST 60 seconds, backend 55 seconds, OpenAI 35 seconds, DeepSeek 10 seconds, fallback minimum remainder 12 seconds, parser maximum 8 seconds, and response reserve 5 seconds.
- [x] Persistent disclosure uses the exact approved sentence in section 15.
- [x] Automated verification is offline; live calls occur only in the separately authorized final smoke phase.

## 18. Administrator evaluation checklist

```text
Not applicable. This task does not modify mailbox ingest, raw vault, stage-evaluation, private dataset build, or interactive judge behavior.
```

## 19. Post-execution record

Tasks 1-7 completed their offline implementation and review gates on 2026-07-16:

- Focused RED ran 96 tests and failed 19 expected missing-field, stale-budget,
  stale-timeout, and documentation-canary assertions before production changes.
- The same focused set passed 96 tests after the minimum implementation.
- The first full suite exposed 10 stale downstream test contracts that still
  encoded the superseded 15/13-second normal-runtime budget and prior disclosure.
  A focused 89-test regression set passed after those contracts were aligned.
- Final full verification passed 1,181 tests with one expected skip.
- Task 2 added verified Tencent visible-frame/current-thread extraction with
  current-only fail-closed behavior (`476a57a` plus review fixes and gate).
- Task 3 added visible business-media classification and rejected signature,
  tracker, hidden, external, and ambiguous resources (`187235c` plus review fix
  and gate).
- Task 4 added bounded image/PDF/Office media sanitation and request-local source
  binding (`34a8270` plus review fix and gate).
- Task 5 added the fixed OpenAI Responses client for `gpt-5.6-sol`, including
  strict metadata/environment controls (`67744bf` plus review fixes and gate).
- Task 6 added OpenAI-to-DeepSeek-to-rules routing, 12-second fallback gating,
  text/hybrid grounding, visual qualitative claim limits, and the body-only
  fixed cross-language bridge (`186713c` plus review fixes and gate).
- Task 7 added the shared task-card UI, exact engine/fallback states, and the
  60-second pending explanation (`cb85dc2` plus security fix and gate).
- The current stage remains `multimodal_current_email_offline_ready_live_pending`
  because the new Task 5 real current-message attachment smoke remains pending
  and requires fresh explicit authorization. Task 9 synthetic provider and
  current-clicked Tencent smokes are complete; they do not validate the new
  attachment acquisition path or authorize another live operation.
- No provider, network, browser, mailbox, real email, key, `.env`, or live API was
  accessed during Tasks 1-8. Task 9 used only the separately authorized bounded
  checks recorded above. The new attachment acquisition smoke is not live-tested.
