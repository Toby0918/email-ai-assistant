---
last_update: 2026-07-09
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Phase Two Attachment and Thread Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user-clicked analysis of the currently opened Tencent Exmail message combine parsed image/PDF/XLSX/DOCX evidence and full visible conversation progress into a validated Chinese decision brief and an English draft reply.

**Architecture:** The extension reads only the open message after the Analyze click and transfers bounded attachment bytes to the local Python backend. Backend modules validate and retain source files temporarily, extract safe text facts, reconstruct the thread, call the configured local model, validate and repair JSON, then render a persistent side panel. SQLite retains only the final structured analysis result, never attachment bytes or private URLs.

**Tech Stack:** Python 3.12.13, standard-library `unittest`, SQLite 3.50.4, beautifulsoup4 4.15.0, openpyxl 3.1.5, pypdf, python-docx, Pillow, pytesseract, Chrome/Edge Manifest V3 JavaScript, local Ollama.

## Global Constraints

- Only a user click may start analysis, attachment extraction, transfer, parsing, OCR, or model inference.
- Only resources visibly associated with the current opened message may be collected.
- `cndlf.com` represents internal business users; other domains are external by default.
- Attachment source files stay in a backend temporary directory for 24 hours, then are deleted; no source bytes, private URLs, cookies, tokens, raw full attachment text, or actual customer samples enter SQLite, logs, docs, or tests.
- `EMAIL_AGENT_OLLAMA_MODEL` defaults to `qwen3.6:latest`; `gemma4` is an environment-selected alternative; unavailable or invalid models fall back to deterministic rules.
- The frontend never calls OpenAI, Ollama, Qwen, Gemma, SQLite, or `.env` directly and never performs send, delete, archive, move, forward, or reply actions.
- AI output remains validated JSON, and every reply draft remains English with `needs_human_review: true`.
- No parser runs executable, macro, archive, or embedded active content.

---

### Task 1: Establish approved dependencies, runtime configuration, and phase-two boundaries

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Modify: `backend/email_agent/config.py`
- Modify: `backend/email_agent/llm_client.py`
- Modify: `AGENTS.md`
- Modify: `docs/product/feature_scope.md`
- Modify: `docs/product/roadmap.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/constraints/architecture_constraints.md`
- Modify: `docs/constraints/linter_constraints.md`
- Modify: `tests/test_config.py`
- Modify: `tests/test_llm_client.py`
- Modify: `tests/test_architecture_constraints.py`
- Modify: `tests/test_static_linter_constraints.py`

**Interfaces:**
- Produces: immutable `AppConfig` fields `attachment_temp_dir`, `attachment_retention_hours`, `attachment_max_files`, `attachment_max_file_bytes`, `attachment_max_total_bytes`, `internal_email_domains`.
- Produces: non-sensitive engine labels `Local Qwen`, `Local Gemma`, and `Rule fallback`.

- [ ] **Step 1: Write failing configuration and model-label tests**

```python
def test_load_config_has_phase_two_defaults(self) -> None:
    config = load_config(dotenv_path=None)
    self.assertEqual(config.ollama_model, "qwen3.6:latest")
    self.assertEqual(config.attachment_retention_hours, 24)
    self.assertIn("cndlf.com", config.internal_email_domains)

def test_configured_engine_label_identifies_gemma(self) -> None:
    config = AppConfig(..., llm_provider="ollama", ollama_model="gemma4:latest", ...)
    self.assertEqual(configured_analysis_engine_label(config), "Local Gemma")
```

- [ ] **Step 2: Run the targeted tests and confirm they fail because the fields are absent**

Run: `python -m unittest tests.test_config tests.test_llm_client`

Expected: failure referencing missing phase-two configuration or missing Gemma label behavior.

- [ ] **Step 3: Add the minimum approved dependencies and configuration**

```text
pypdf==5.7.0
python-docx==1.1.2
Pillow==11.2.1
pytesseract==0.3.13
```

```python
attachment_temp_dir=os.getenv("EMAIL_AGENT_ATTACHMENT_TEMP_DIR", "outputs/attachment_temp"),
attachment_retention_hours=_int_env("EMAIL_AGENT_ATTACHMENT_RETENTION_HOURS", 24),
internal_email_domains=_csv_env("EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS", ("cndlf.com",)),
```

Update user-facing constraints so the approved scope is current-message-only attachment transfer and backend parsing, not mailbox access or automatic mail actions.

- [ ] **Step 4: Run the targeted tests and architecture/static constraint checks**

Run: `python -m unittest tests.test_config tests.test_llm_client tests.test_architecture_constraints tests.test_static_linter_constraints`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add requirements.txt .env.example backend/email_agent/config.py backend/email_agent/llm_client.py AGENTS.md docs/product/feature_scope.md docs/product/roadmap.md docs/security/email_data_handling.md docs/constraints/tooling_constraints.md docs/constraints/architecture_constraints.md docs/constraints/linter_constraints.md tests/test_config.py tests/test_llm_client.py tests/test_architecture_constraints.py tests/test_static_linter_constraints.py
git commit -m "feat: configure phase two attachment analysis"
```

### Task 2: Add safe attachment input validation and temporary storage

**Files:**
- Create: `backend/email_agent/attachment_storage.py`
- Modify: `backend/email_agent/api.py`
- Modify: `backend/email_agent/server.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_attachment_storage.py`

**Interfaces:**
- Consumes: `AppConfig` limits from Task 1 and request field `attachment_files`.
- Produces: `store_attachment_files(files: list[dict[str, object]], config: AppConfig) -> list[StoredAttachment]`.
- Produces: `cleanup_expired_attachments(config: AppConfig, now: datetime | None = None) -> int`.
- `StoredAttachment` contains `safe_filename`, `type`, `path`, `byte_size`, and `expires_at`; it is backend-internal and never serialized into SQLite or the analysis response.

- [ ] **Step 1: Write failing storage and API tests**

```python
def test_store_attachment_files_rejects_file_over_byte_limit(self) -> None:
    with self.assertRaises(AttachmentInputError):
        store_attachment_files([{"filename": "large.pdf", "content_base64": "..."}], config)

def test_cleanup_expired_attachments_deletes_only_expired_files(self) -> None:
    removed = cleanup_expired_attachments(config, now=datetime(2026, 7, 10, tzinfo=UTC))
    self.assertEqual(removed, 1)

def test_api_rejects_attachment_files_without_user_confirmation(self) -> None:
    response = handle_analyze_current_email({"attachment_files": []})
    self.assertEqual(response["error"]["code"], "USER_ACTION_REQUIRED")
```

- [ ] **Step 2: Run targeted tests and confirm the missing-module failure**

Run: `python -m unittest tests.test_attachment_storage tests.test_api`

Expected: failure because `attachment_storage` and the bounded request behavior do not exist.

- [ ] **Step 3: Implement validation, storage, and local request bounds**

```python
SUPPORTED_ATTACHMENT_TYPES = {"image", "pdf", "xlsx", "docx"}

def store_attachment_files(files: list[dict[str, object]], config: AppConfig) -> list[StoredAttachment]:
    _validate_file_count_and_total_size(files, config)
    return [_store_one_attachment(file_data, config) for file_data in files]
```

`server.py` must reject oversized `Content-Length` before reading JSON and return a stable local error. `api.py` must accept attachment bytes only with `user_confirmed is True`, pass `StoredAttachment` values to the analyzer without logging raw content, and always run cleanup before storing new files.

- [ ] **Step 4: Run targeted tests and full server/API regression tests**

Run: `python -m unittest tests.test_attachment_storage tests.test_api tests.test_server`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add backend/email_agent/attachment_storage.py backend/email_agent/api.py backend/email_agent/server.py tests/test_attachment_storage.py tests/test_api.py
git commit -m "feat: add bounded attachment storage"
```

### Task 3: Parse supported attachment types into bounded, safe insights

**Files:**
- Create: `backend/email_agent/attachment_parser.py`
- Modify: `backend/email_agent/attachment_storage.py`
- Create: `tests/test_attachment_parser.py`
- Create: `tests/fixtures/phase_two/README.md`
- Create: generated, de-identified test fixtures under `tests/fixtures/phase_two/`

**Interfaces:**
- Consumes: `list[StoredAttachment]` from Task 2.
- Produces: `parse_attachments(items: list[StoredAttachment]) -> list[dict[str, object]]`.
- Each output object has `filename`, `type`, `status`, `summary`, `key_facts`, and `limitations` only.

- [ ] **Step 1: Write failing parser tests for every supported type and optional OCR**

```python
def test_parse_pdf_returns_bounded_text_facts(self) -> None:
    result = parse_attachments([stored_pdf])
    self.assertEqual(result[0]["status"], "parsed")
    self.assertIn("RFQ", result[0]["summary"])

def test_parse_image_marks_ocr_unavailable_without_failing(self) -> None:
    with patch("backend.email_agent.attachment_parser.pytesseract", None):
        result = parse_attachments([stored_image])
    self.assertEqual(result[0]["status"], "metadata_only")
    self.assertIn("OCR", result[0]["limitations"][0])
```

- [ ] **Step 2: Run parser tests and confirm they fail because the parser is absent**

Run: `python -m unittest tests.test_attachment_parser`

Expected: import failure for `attachment_parser`.

- [ ] **Step 3: Implement type-specific bounded extraction**

```python
def parse_attachments(items: list[StoredAttachment]) -> list[dict[str, object]]:
    return [_parse_one(item) for item in items]

def _parse_one(item: StoredAttachment) -> dict[str, object]:
    if item.type == "pdf":
        return _parse_pdf(item)
    if item.type == "xlsx":
        return _parse_xlsx(item)
    if item.type == "docx":
        return _parse_docx(item)
    if item.type == "image":
        return _parse_image(item)
    return _unavailable_insight(item, "Unsupported attachment type.")
```

Use page/sheet/row/character limits. Strip control characters and replace extracted URLs with display-safe text. `pytesseract` failures must become a limitation, not an exception leaving the analysis route.

- [ ] **Step 4: Run parser tests and verify no source text is emitted to logs or stored output**

Run: `python -m unittest tests.test_attachment_parser tests.test_static_linter_constraints`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add backend/email_agent/attachment_parser.py backend/email_agent/attachment_storage.py tests/test_attachment_parser.py tests/fixtures/phase_two
git commit -m "feat: parse supported email attachments"
```

### Task 4: Reconstruct current-message conversation progress and participant roles

**Files:**
- Create: `backend/email_agent/thread_timeline.py`
- Modify: `backend/email_agent/email_cleaner.py`
- Modify: `tests/test_email_cleaner.py`
- Create: `tests/test_thread_timeline.py`

**Interfaces:**
- Consumes: request field `thread_segments: list[dict[str, str]]` and `AppConfig.internal_email_domains`.
- Produces: `build_conversation_timeline(segments: list[dict[str, str]], internal_domains: tuple[str, ...]) -> dict[str, object]`.
- Timeline has `previous_context`, `current_status`, `status_reason`, `latest_external_request`, `latest_internal_commitment`, `open_items`, and `confidence`.

- [ ] **Step 1: Write failing timeline tests for internal/external classification and unresolved work**

```python
def test_timeline_marks_cndlf_sender_as_internal_and_latest_customer_request_open(self) -> None:
    result = build_conversation_timeline(segments, ("cndlf.com",))
    self.assertEqual(result["current_status"], "unresolved")
    self.assertIn("报价", result["latest_external_request"])
    self.assertEqual(result["open_items"][0]["owner_hint"], "internal_sales")
```

- [ ] **Step 2: Run timeline tests and confirm the missing-module failure**

Run: `python -m unittest tests.test_thread_timeline tests.test_email_cleaner`

Expected: import failure for `thread_timeline`.

- [ ] **Step 3: Implement deterministic thread normalization and status calculation**

```python
def build_conversation_timeline(segments, internal_domains):
    normalized = _deduplicate_and_clean(segments)
    ordered = _order_segments(normalized)
    events = [_extract_event(segment, internal_domains) for segment in ordered]
    return _summarize_progress(events)
```

Use timestamp order only when it parses; otherwise retain DOM order and lower confidence. Do not infer a matter is resolved from a generic acknowledgement. The latest unresolved external request takes precedence for `open_items` and later reply drafting.

- [ ] **Step 4: Run timeline tests and existing cleaning tests**

Run: `python -m unittest tests.test_thread_timeline tests.test_email_cleaner`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add backend/email_agent/thread_timeline.py backend/email_agent/email_cleaner.py tests/test_thread_timeline.py tests/test_email_cleaner.py
git commit -m "feat: build current email conversation timeline"
```

### Task 5: Extend schema, rule fallback, repair, and model prompt with timeline and attachment insights

**Files:**
- Modify: `backend/email_agent/analysis_schema.py`
- Modify: `backend/email_agent/analyzer.py`
- Modify: `backend/email_agent/analysis_repair.py`
- Modify: `backend/email_agent/rule_analyzer.py`
- Modify: `backend/email_agent/rule_decision.py`
- Modify: `docs/data/analysis_result_schema.md`
- Modify: `docs/prompts/analyzer_prompt.md`
- Modify: `docs/api/backend_api_contract.md`
- Modify: `tests/test_analysis_schema.py`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_rule_analyzer.py`

**Interfaces:**
- Consumes: parser output from Task 3 and timeline output from Task 4.
- Produces: validated `analysis["attachment_insights"]` and `analysis["conversation_timeline"]`.

- [ ] **Step 1: Write failing schema and rule fallback tests**

```python
def test_schema_requires_conversation_timeline_and_attachment_insights(self) -> None:
    analysis = valid_analysis()
    analysis.pop("conversation_timeline")
    with self.assertRaises(AnalysisValidationError):
        validate_analysis_result(analysis)

def test_rule_analysis_explains_latest_unresolved_customer_request(self) -> None:
    result = build_rule_based_analysis(email_with_thread_and_attachment)
    self.assertEqual(result["conversation_timeline"]["current_status"], "unresolved")
    self.assertIn("客户", result["decision_brief"]["requested_outcome"])
```

- [ ] **Step 2: Run targeted tests and confirm required-field failures**

Run: `python -m unittest tests.test_analysis_schema tests.test_rule_analyzer tests.test_analyzer`

Expected: failure for missing timeline and attachment-insight validation.

- [ ] **Step 3: Implement schema validation, deterministic fallback, and bounded prompt context**

```python
REQUIRED_RESULT_FIELDS |= {"conversation_timeline", "attachment_insights"}

def analyze_current_email(email, llm_generate=generate_analysis, analysis_engine_label=None):
    insights = parse_attachments(email.get("stored_attachments", []))
    timeline = build_conversation_timeline(email.get("thread_segments", []), load_config().internal_email_domains)
    fallback = build_rule_based_analysis(email, attachment_insights=insights, conversation_timeline=timeline)
    return _generate_or_repair(email, insights, timeline, fallback, llm_generate, analysis_engine_label)
```

Prompt context must label every email/thread/file field as untrusted, include parser limitations, request Chinese analysis fields and an English reviewed draft, and prohibit unsupported commercial or legal commitments. The repair layer fills missing model fields from the deterministic timeline and insights; it must not invent parsed attachment facts.

- [ ] **Step 4: Run targeted regression tests**

Run: `python -m unittest tests.test_analysis_schema tests.test_analyzer tests.test_rule_analyzer`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add backend/email_agent/analysis_schema.py backend/email_agent/analyzer.py backend/email_agent/analysis_repair.py backend/email_agent/rule_analyzer.py backend/email_agent/rule_decision.py docs/data/analysis_result_schema.md docs/prompts/analyzer_prompt.md docs/api/backend_api_contract.md tests/test_analysis_schema.py tests/test_analyzer.py tests/test_rule_analyzer.py
git commit -m "feat: analyze attachment and thread context"
```

### Task 6: Extract current-message resources and visible thread segments in the extension

**Files:**
- Modify: `frontend/browser_extension/manifest.json`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/browser_extension/popup.js`
- Modify: `tests/test_browser_extension_behavior.py`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_browser_extension_manifest.py`

**Interfaces:**
- Consumes: explicit popup Analyze click.
- Produces: `payload.thread_segments` and bounded `payload.attachment_files` for only the open message.
- `attachment_files` entries are `{filename, type, size, content_base64}` and have no cookie, token, or private URL fields.

- [ ] **Step 1: Write failing extension behavior tests**

```javascript
opened_message_extracts_thread_segments: () => {
  const result = dispatch(threadDocument());
  if (result.payload.thread_segments.length < 2) {
    throw new Error("expected visible current-message thread segments");
  }
},
explicit_click_collects_supported_attachment_bytes_only: async () => {
  const payload = await collectCurrentMessageResources(openedMessage);
  if (payload.attachment_files[0].content_base64.length === 0) {
    throw new Error("expected attachment bytes after explicit collection");
  }
}
```

- [ ] **Step 2: Run extension behavior tests and confirm missing collection behavior**

Run: `python -m unittest tests.test_browser_extension_behavior tests.test_browser_extension_static tests.test_browser_extension_manifest`

Expected: failure because thread segments and user-click-only byte transfer are absent.

- [ ] **Step 3: Implement DOM-only current-message collection**

```javascript
async function collectCurrentMessageResources(extraction) {
  const resources = findCurrentMessageResourceElements(extraction.document);
  return Promise.all(resources.slice(0, MAX_ATTACHMENTS).map(readSupportedResource));
}

async function readSupportedResource(resource) {
  const response = await fetch(resource.downloadUrl, { credentials: "include" });
  const bytes = await response.arrayBuffer();
  return { filename: resource.filename, type: resource.type, size: bytes.byteLength, content_base64: arrayBufferToBase64(bytes) };
}
```

Call `collectCurrentMessageResources` only inside the Analyze click path. Enforce the same visible resource count and byte limits before upload. If a resource cannot be fetched from the current page session, include only safe metadata and a limitation. Do not add automated fetches on page load, URL scanning, or access to another tab/frame.

- [ ] **Step 4: Run JavaScript syntax checks and extension tests**

Run: `node --check frontend/browser_extension/content/exmail_adapter.js`

Run: `node --check frontend/browser_extension/shared/api_client.js`

Run: `python -m unittest tests.test_browser_extension_behavior tests.test_browser_extension_static tests.test_browser_extension_manifest`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add frontend/browser_extension/manifest.json frontend/browser_extension/content/exmail_adapter.js frontend/browser_extension/shared/api_client.js frontend/browser_extension/popup.js tests/test_browser_extension_behavior.py tests/test_browser_extension_static.py tests/test_browser_extension_manifest.py
git commit -m "feat: collect current email attachments and thread"
```

### Task 7: Render conversation progress and attachment insights in the persistent side panel

**Files:**
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/browser_extension/popup.css`
- Modify: `frontend/browser_extension/popup.js`
- Modify: `frontend/browser_extension/shared/render_analysis.js`
- Modify: `frontend/local_debug_page/index.html`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `tests/test_browser_extension_renderer_behavior.py`
- Modify: `tests/test_frontend_local_debug.py`

**Interfaces:**
- Consumes: validated `analysis.conversation_timeline` and `analysis.attachment_insights` from Task 5.
- Produces: readable side-panel sections that keep Copy Draft visible and render each insight/action as separate DOM nodes.

- [ ] **Step 1: Write failing renderer tests**

```javascript
const timeline = {
  previous_context: "客户先提交 RFQ，我司已确认收到。",
  current_status: "unresolved",
  latest_external_request: "客户要求在明天前提供报价。",
  open_items: [{ item: "核对成本", owner_hint: "internal_sales", due_hint: "明天", source: "thread" }]
};
EmailAssistantRender.renderConversationTimeline(fields.timeline, timeline);
if (fields.timeline.children.length < 3) throw new Error("expected timeline entries");
```

- [ ] **Step 2: Run renderer tests and confirm missing render functions**

Run: `python -m unittest tests.test_browser_extension_renderer_behavior tests.test_frontend_local_debug`

Expected: failure because the timeline and attachment-insight sections do not exist.

- [ ] **Step 3: Implement structured, scroll-safe rendering**

```javascript
function renderConversationTimeline(field, timeline) {
  renderLabeledEntries(field, [
    ["前情", timeline.previous_context],
    ["当前状态", formatStatus(timeline.current_status, timeline.status_reason)],
    ["最新诉求", timeline.latest_external_request],
    ["下一步", timeline.open_items]
  ]);
}
```

Render parsed attachment summaries and limitations separately. Do not render raw attachment text wholesale, dynamic HTML, or private download URLs. Put the draft label and Copy Draft control in the visible draft header; preserve the current persistent side-panel behavior.

- [ ] **Step 4: Run targeted rendering tests and JavaScript checks**

Run: `node --check frontend/browser_extension/shared/render_analysis.js`

Run: `node --check frontend/browser_extension/popup.js`

Run: `python -m unittest tests.test_browser_extension_renderer_behavior tests.test_frontend_local_debug`

Expected: PASS.

- [ ] **Step 5: Commit the task**

```bash
git add frontend/browser_extension/popup.html frontend/browser_extension/popup.css frontend/browser_extension/popup.js frontend/browser_extension/shared/render_analysis.js frontend/local_debug_page/index.html frontend/local_debug_page/app.js tests/test_browser_extension_renderer_behavior.py tests/test_frontend_local_debug.py
git commit -m "feat: render thread and attachment insights"
```

### Task 8: Add lifecycle operations, update project documentation, and complete release verification

**Files:**
- Modify: `scripts/manage_local_service.py`
- Modify: `start_local_service.cmd`
- Modify: `restart_local_service.cmd`
- Modify: `status_local_service.cmd`
- Modify: `README.md`
- Modify: `docs/operations/setup_checklist.md`
- Modify: `docs/operations/testing_checklist.md`
- Modify: `docs/operations/deployment_notes.md`
- Modify: `docs/operations/project_status_log.md`
- Modify: `docs/operations/phase_two_attachment_thread_task_brief.md`
- Modify: `tests/test_manage_local_service.py`
- Modify: `tests/test_run_local_debug.py`

**Interfaces:**
- Consumes: `cleanup_expired_attachments` from Task 2.
- Produces: service startup/restart behavior that performs bounded expiry cleanup and status diagnostics without exposing attachment contents.

- [ ] **Step 1: Write failing lifecycle and documentation-oriented tests**

```python
def test_restart_service_runs_attachment_expiry_cleanup(self) -> None:
    result = run_cleanup_before_service_start(config)
    self.assertEqual(result.removed_count, 2)

def test_status_output_does_not_include_attachment_file_content(self) -> None:
    output = status_local_service()
    self.assertNotIn("synthetic attachment content", output)
```

- [ ] **Step 2: Run lifecycle tests and confirm missing cleanup wiring**

Run: `python -m unittest tests.test_manage_local_service tests.test_run_local_debug`

Expected: failure because lifecycle cleanup is not called.

- [ ] **Step 3: Wire cleanup into service operations and update operational documentation**

```python
def run_cleanup_before_service_start(config: AppConfig | None = None) -> CleanupResult:
    removed_count = cleanup_expired_attachments(config or load_config())
    return CleanupResult(removed_count=removed_count)
```

Document environment settings, optional Tesseract installation, `qwen3.6` default and `gemma4` switch, 24-hour retention, limitations, reload instructions, and manual Tencent Exmail tests. Regenerate the project status log after implementation.

- [ ] **Step 4: Run full verification**

Run: `python -m unittest discover -s tests`

Run: `python -B scripts/maintenance_scan.py`

Run: `node --check frontend/browser_extension/content/exmail_adapter.js`

Run: `node --check frontend/browser_extension/shared/api_client.js`

Run: `node --check frontend/browser_extension/shared/render_analysis.js`

Run: `node --check frontend/browser_extension/popup.js`

Expected: all commands exit `0`; full test output has no failures; maintenance output reports no cleanup findings.

- [ ] **Step 5: Commit the task**

```bash
git add scripts/manage_local_service.py start_local_service.cmd restart_local_service.cmd status_local_service.cmd README.md docs/operations/setup_checklist.md docs/operations/testing_checklist.md docs/operations/deployment_notes.md docs/operations/project_status_log.md docs/operations/phase_two_attachment_thread_task_brief.md tests/test_manage_local_service.py tests/test_run_local_debug.py
git commit -m "chore: document phase two attachment operations"
```

