---
last_update: 2026-07-18
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Multimodal Current Email Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILLS: Use `superpowers:test-driven-development`, `superpowers:subagent-driven-development`, and `superpowers:verification-before-completion`. Execute tasks in order. Preserve each RED result before production changes, commit each task independently, and run a fresh task review before proceeding.

**Goal:** Make one clicked Tencent Exmail message automatically yield a complete, readable, source-grounded analysis that can understand business photos and supported files, with OpenAI multimodal analysis first, DeepSeek text fallback second, and rules last.

**Architecture:** A verified same-origin document context acquires only the currently visible message, thread, attachments, and business inline images. Backend media preparation validates and sanitizes those bytes, locally deidentifies all text, and builds one provider-neutral request using opaque evidence IDs. OpenAI Responses receives text plus bounded media; a separately enabled DeepSeek route receives text only after an early OpenAI failure and sufficient remaining budget. Both providers return the existing private envelope and cross the same strict parser, evidence, grounding, exact-fact, safety, language, and public-schema gates. Public HTTP and SQLite remain compatible.

**Tech stack:** Python 3.12.13, existing `openai==2.45.0`, Pillow 12.3.0, pypdf 6.14.2, python-docx 1.2.0, openpyxl 3.1.5, standard-library `zipfile`/`io`/`base64`, Chrome/Edge extension JavaScript, `unittest`, and Node syntax checks. No dependency is added or upgraded.

## Global constraints

- Work only in `.worktrees/multimodal-plan-c`; do not touch the user's dirty root-checkout deployment notes.
- Keep every provider disabled by default. No frontend key, provider call, secret, or configurable remote base URL.
- Keep acquisition click-only and current-message-only. Never scan the mailbox or read another message/folder/account.
- Use only synthetic `example.test` fixtures during automated implementation and review.
- Do not call a live provider or real mailbox until all offline gates pass and the separately authorized smoke phase begins.
- Keep public HTTP/SQLite fields compatible. Internal media, binary, Base64, source IDs, paths, URLs, prompts, raw outputs, and exception text never persist or log.
- Use one OpenAI call and, only on eligible failure, one DeepSeek call. Each SDK has `max_retries=0`.
- Use exact budgets: frontend 60, backend 55, parser 8, OpenAI 35, DeepSeek 10, fallback remainder 12, response/persistence reserve 5 seconds.
- Preserve local authority for exact identifiers, dates, amounts, quantities, and tracking values.
- Keep drafts human-review-only and forbid automatic mailbox actions or unconditional commitments.

---

### Task 1: Lock governance, configuration, and mechanical boundaries

**Files:**
- Modify: `AGENTS.md`
- Modify: `.env.example`
- Modify: `backend/email_agent/config.py`
- Modify: `backend/email_agent/analysis_budget.py`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `docs/product/feature_scope.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/security/privacy_rules.md`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/constraints/architecture_constraints.md`
- Modify: `docs/constraints/linter_constraints.md`
- Modify: `docs/templates/agent_task_brief_template.md`
- Modify: `tests/test_config.py`
- Modify: `tests/test_analysis_budget.py`
- Modify: `tests/test_browser_extension_task6_contracts.py`
- Modify: `tests/test_frontend_local_debug.py`
- Modify: `tests/test_architecture_constraints.py`
- Modify: `tests/test_static_linter_constraints.py`

**Interfaces:**
- `AppConfig` gains `openai_model`, `openai_timeout_seconds`, and `text_fallback_provider` with safe defaults.
- Allowed OpenAI model is exactly `gpt-5.6-sol`; allowed fallback values are `disabled` and `deepseek`.
- `AnalysisBudget` exposes the exact 55/35/10/12/5 constants without changing the separate private-evaluation 13-second dataset runner.

- [x] Write failing config, budget, frontend-timeout, architecture, and documentation-canary tests first.
- [x] Run the focused modules and preserve RED showing missing fields and stale 15/13-second constants.
- [x] Implement configuration normalization, fixed allowlists, safe defaults, exact timeouts, and no configurable OpenAI endpoint.
- [x] Update governance text with the exact persistent disclosure from task-brief section 15; frontend markup changes remain Task 7.
- [x] Run the focused tests GREEN and commit `feat: define multimodal provider boundaries`.

### Task 2: Automatically extract the visible Tencent message and full thread

**Files:**
- Create: `frontend/browser_extension/content/exmail_visible_context.js`
- Modify: `frontend/browser_extension/manifest.json`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/content/current_message_collector.js`
- Modify: `tests/test_browser_extension_manifest.py`
- Modify: `tests/test_browser_extension_behavior.py`
- Modify: `tests/test_browser_extension_tencent_legacy_context.py`
- Modify: `tests/test_browser_extension_task6_adapter.py`
- Modify: `tests/test_browser_extension_current_message_collector.py`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_browser_extension_task6_contracts.py`

**Interfaces:**
- `resolveVerifiedDocumentContext(window)` returns only a top document or one unique visible, same-origin, accessible Tencent `mainFrame` with read-message evidence.
- `extractVisibleMessageContext` returns a current message and oldest-to-newest `thread_segments`. Unreliable segmentation returns the current body with an empty history.
- A context token binds document identity, frame identity, subject/header evidence, and current-body identity for post-read revalidation.

- [x] Add a synthetic legacy `mainFrame` fixture that reproduces `Email body is empty` without manual selection and run RED.
- [x] Add hidden, cross-origin, duplicate-frame, missing-header, stale-navigation, and ambiguous-body negative fixtures.
- [x] Implement verified context resolution and current body/history extraction without `all_frames` or new host permissions.
- [x] Revalidate context after collection; discard bytes and thread data on any identity change.
- [x] Run extension-focused tests and `node --check` GREEN; commit `fix: read visible Tencent message context`.

### Task 3: Classify business images and collect only approved resources

**Files:**
- Create: `frontend/browser_extension/content/exmail_visible_resource_classifier.js`
- Modify: `frontend/browser_extension/manifest.json`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/content/current_message_collector.js`
- Create: `tests/test_browser_extension_visible_resource_classifier.py`
- Modify: `tests/test_browser_extension_current_message_collector.py`
- Modify: `tests/test_browser_extension_task6_adapter.py`
- Modify: `tests/test_browser_extension_static.py`

**Interfaces:**
- Classifier output is internal only: `visible_attachment`, `inline_business_image`, or rejected.
- Accepted inline images become existing `attachment_files` with opaque safe names such as `inline-image-1.jpg`; no role, URL, DOM selector, or original filename is sent.
- Approved URLs remain same-origin HTTPS Tencent `/cgi-bin/download` or `/cgi-bin/viewfile` with a non-empty query and no credentials.

- [x] Add the inclusion matrix for a large current-body product/packaging photo and visible attachment control.
- [x] Add exclusion fixtures for the three supplied signature patterns, repeated images, signature-boundary media, logos, avatars, icons, 1x1 trackers, hidden media, quoted-history signatures, external sources, and ambiguous ownership; run RED.
- [x] Implement the pure classifier and integrate it only into the verified context from Task 2.
- [x] Preserve 20 candidates, 5 downloads, 10 MiB per resource, 25 MiB total, and 20-second resource-phase bounds.
- [x] Revalidate before and after fetch and discard redirected or stale resources.
- [x] Run extension suites and syntax checks GREEN; commit `feat: collect visible business media safely`.

### Task 4: Prepare request-local sanitized media and embedded office images

**Files:**
- Create: `backend/email_agent/multimodal_media.py`
- Create: `backend/email_agent/office_embedded_media.py`
- Modify: `backend/email_agent/attachment_storage.py`
- Modify: `backend/email_agent/analyzer.py`
- Modify: `backend/email_agent/analysis_model_routes.py`
- Modify: `backend/email_agent/api.py`
- Create: `tests/test_multimodal_media.py`
- Create: `tests/test_office_embedded_media.py`
- Modify: `tests/test_attachment_storage.py`
- Modify: `tests/test_attachment_parser.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- `PreparedMediaAsset` is frozen, `repr=False`, uses an opaque `source_id`, generic provider filename, fixed MIME, kind, detail, and a mutable byte buffer.
- Image sanitation decodes, verifies, applies orientation, flattens animation, strips metadata, bounds pixels/dimensions, and re-encodes without original metadata.
- PDF sanitation rejects encryption and excess pages, rewrites selected pages, and removes metadata, scripts, actions, forms, annotations, and embedded files.
- Office extraction accepts only bounded `word/media/` or `xl/media/` entries with safe names, image magic, per-entry and aggregate limits.
- `remove_stored_attachments` runs in API `finally` after success or failure.

- [x] Write RED tests for MIME/magic mismatch, malformed files, pixel bombs, animation, EXIF removal, PDF active objects, encryption/page limits, zip traversal/bombs, embedded-image limits, opaque names, `repr`, and cleanup on all API exits.
- [x] Implement the smallest pure media preparation modules using existing dependencies only.
- [x] Associate each asset with an existing `attachment:N` evidence ID and add a generic untrusted-media text source when OCR/text is absent.
- [x] Ensure no provider-ready Base64 or asset bytes enter a dataclass repr, exception, response, SQLite, or log.
- [x] Run media/parser/API suites GREEN; commit `feat: sanitize request media for vision`.

### Task 5: Implement the OpenAI Responses multimodal client

**Files:**
- Create: `backend/email_agent/model_request.py`
- Create: `backend/email_agent/openai_multimodal_client.py`
- Modify: `backend/email_agent/llm_client.py`
- Modify: `backend/email_agent/prompt_context.py`
- Modify: `backend/email_agent/private_context_gate.py`
- Modify: `tests/test_llm_client.py`
- Create: `tests/test_openai_multimodal_client.py`
- Modify: `tests/test_prompt_context.py`
- Modify: `tests/test_private_context_gate.py`

**Interfaces:**
- `ModelAnalysisRequest` contains only locally deidentified text plus request-local sanitized media assets.
- OpenAI input is one user message whose content starts with `input_text`; every media item is immediately preceded by an opaque `UNTRUSTED_BINARY_SOURCE` marker and followed by `input_image` or PDF `input_file`.
- Remote filenames are `attachment_0.pdf` or equivalent opaque names.
- Responses call uses `gpt-5.6-sol`, fixed official endpoint, `store=false`, `stream=false`, `max_retries=0`, no tools, `detail=high`, low output verbosity, bounded reasoning, 2,400 output tokens, and at most 35 seconds. OpenAI omits `text.format`; the JSON-only prompt is enforced by strict local validation.
- The client returns only non-empty `response.output_text` or a fixed `LlmClientError.reason_code`.

- [ ] Write an async-client fake and RED tests for exact request shape, source/media adjacency, fixed model/endpoint, no Files API, no private URL/path/original filename, and all timeout/empty/incomplete/provider error mappings.
- [ ] Add RED tests proving media cannot bypass text privacy failure and that output crosses the existing private-output gate.
- [ ] Implement the request builder and Responses call without adding a dependency.
- [ ] Keep the existing DeepSeek Chat Completions request unchanged and text-only.
- [ ] Run client/prompt/privacy tests GREEN; commit `feat: add OpenAI multimodal analysis client`.

### Task 6: Route OpenAI first, DeepSeek text fallback second, and rules last

**Files:**
- Modify: `backend/email_agent/analysis_route_support.py`
- Modify: `backend/email_agent/analysis_model_routes.py`
- Modify: `backend/email_agent/model_grounding.py`
- Modify: `backend/email_agent/model_result_safety.py`
- Modify: `backend/email_agent/analysis_diagnostics.py`
- Modify: `tests/test_analysis_route_support.py`
- Modify: `tests/test_analysis_model_routes.py`
- Modify: `tests/test_model_grounding.py`
- Modify: `tests/test_model_result_safety.py`
- Modify: `tests/test_analyzer.py`

**Interfaces:**
- OpenAI is model-led and uses existing private envelope parsing/evidence validation/merge.
- `EvidenceSource` gains an internal grounding mode. Visual sources may support qualitative attachment observations but never exact facts or person identification.
- A `ModelRun` records the accepted non-sensitive engine label so the public result reflects OpenAI or DeepSeek text fallback accurately.
- Fallback eligibility requires explicit provider configuration and 12 seconds remaining immediately before the DeepSeek call.

- [ ] Write route RED tests for OpenAI acceptance, OpenAI early failure plus DeepSeek success, OpenAI late failure with zero DeepSeek calls, fallback disabled, both providers failing, and injected synthetic generators.
- [ ] Write grounding RED tests for permitted damage/label/layout observations and rejected identity, protected trait, exact ID/date/amount/quantity/tracking, URL, tool instruction, or commitment claims.
- [ ] Implement provider-neutral model-led preparation, conditional fallback, engine labeling, and sanitized diagnostics.
- [ ] Preserve the full deterministic timeline, mandatory risks, exact local fact merge, attachment membership, and human-review flag.
- [ ] Run routing/grounding/analyzer suites GREEN; commit `feat: route multimodal analysis with text fallback`.

### Task 7: Complete side-panel disclosure, status, and readable diagnostics

**Files:**
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/browser_extension/popup.js`
- Modify: `frontend/browser_extension/shared/analysis_components.js`
- Modify: `frontend/browser_extension/shared/analysis_components.css`
- Modify: `frontend/local_debug_page/index.html`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_browser_extension_task_focused_ui.py`
- Modify: `tests/test_frontend_local_debug.py`

**Interfaces:**
- Persistent pre-click disclosure is identical in both frontend surfaces.
- First screen remains task conclusion, current request, next step, key facts, and must-check items.
- Technical details show `OpenAI GPT-5.6 Sol`, `DeepSeek text fallback`, or `Rule fallback` plus one fixed reason. History, attachments, risk basis, and technical details remain collapsed by default.
- Loading state explains that selected images/files are being analyzed and can take up to 60 seconds.

- [ ] Add RED tests for exact disclosure, provider labels, fixed fallback reasons, 320-pixel first-screen content, collapsed technical details, and no raw provider data.
- [ ] Implement minimal markup/rendering/CSS changes without changing public response fields.
- [ ] Run UI/static/syntax tests GREEN; commit `feat: explain multimodal analysis status`.

### Task 8: Synchronize contracts, run offline release gates, and update status

**Files:**
- Modify: `docs/api/backend_api_contract.md`
- Modify: `docs/api/frontend_backend_flow.md`
- Modify: `docs/prompts/analyzer_prompt.md`
- Modify: `docs/data/analysis_result_schema.md`
- Modify: `docs/security/api_key_rules.md`
- Modify: `docs/operations/testing_checklist.md`
- Modify: `docs/operations/deployment_notes.md` only in the isolated worktree and only after confirming no user overlap
- Modify: `docs/product/roadmap.md`
- Modify: `docs/operations/multimodal_current_email_analysis_task_brief.md`
- Modify: `docs/operations/project_status_log.md`
- Modify: relevant documentation-contract and maintenance tests

**Verification:**

- [ ] Update all active docs and front matter from actual implementation, not planned behavior.
- [ ] Run focused Python suites for extension, media, clients, routes, safety, API, SQLite, and docs.
- [ ] Run `node --check` for every changed JavaScript file.
- [ ] Run the full pinned-runtime command:

  ```powershell
  $env:PYTHONPATH='C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages'
  & 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
  ```

- [ ] Run architecture, linter, mechanical, dependency, secret/binary leakage, documentation metadata, and `git diff --check` gates.
- [ ] Generate `docs/operations/project_status_log.md`, rerun full tests, then run `python -B scripts/maintenance_scan.py`.
- [ ] Request a fresh final code review and resolve only bounded in-scope findings.
- [ ] Commit `docs: finalize multimodal analysis release gates`.

### Task 9: Perform the separately authorized live smoke and integrate to master

**Preconditions:**
- All Task 8 offline gates pass.
- No key is printed, read into tool output, logged, or committed.
- The service is started from backend-controlled environment settings.
- The extension is reloaded from the verified worktree build.

**Smoke sequence:**

- [x] Make one synthetic OpenAI multimodal call with a recreated business-photo fixture. Confirm the accepted engine is OpenAI, output is schema-valid, and no rule fallback occurs. Passed 2026-07-17 with one source-bound attachment augmentation.
- Status amendment, 2026-07-18: Task 9 synthetic provider and current-clicked Tencent smokes are complete for their bounded checks; the remaining Task 9 gates below stay unchecked and are not marked complete. Task 5 real current-message attachment smoke remains pending, is not live-tested, and requires fresh explicit authorization.
- [ ] Make one synthetic forced OpenAI failure with eligible budget and confirm exactly one DeepSeek text fallback call.
- [ ] In the user's already signed-in Tencent Exmail tab, use the visible Analyze control on representative current messages only. Do not navigate, search, enumerate, or scan the mailbox.
- [ ] Confirm automatic current-body/full-thread extraction, business-photo understanding, signature-media exclusion, attachment analysis, readable layout, exact local facts, engine status, and bounded latency.
- [ ] Inspect only content-free diagnostics and leakage checks; never print the email, media, prompt, raw output, or credentials.
- [ ] Stop the test service, disable provider settings unless the operator chooses to keep them, and remove request temporary files.
- [ ] Run final diff/status/leakage checks, merge the reviewed commits into local `master`, verify the preserved user change, and push `master` only after all checks pass.

## Final release criteria

1. Offline test suite and all mechanical/security gates pass.
2. No real content, binary, database, key, token, path, provider raw output, or private source ID is staged or committed.
3. Real smoke touches only the current clicked message and produces no mailbox mutation.
4. At least one no-text business photo is understood, while all tested signature images are excluded.
5. Supported attachment content materially affects the analysis with accurate status and limitations.
6. OpenAI, DeepSeek fallback, and rule fallback are distinguishable and safe.
7. Final integration lands on `master`, not a feature branch, without overwriting the user's unrelated root-checkout change.
