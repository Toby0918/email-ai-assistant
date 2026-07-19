---
last_update: 2026-07-18
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Current Message Attachment Acquisition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse supported current-message attachments through strict automatic Tencent in-memory fetch and an explicit user-selected local-file fallback, with truthful status and immediate backend request cleanup.

**Architecture:** Automatic acquisition adds one verified legacy positive signal without weakening origin, path, ownership, redirect, or limits. A separate pure frontend module reads explicitly selected local files only on Analyze and merges them into the unchanged payload. Backend request-local storage and `finally` deletion remain the only disk lifecycle.

**Tech Stack:** Chrome/Edge Manifest V3 JavaScript, existing local HTTP API, Python 3.12.13 `unittest` with Node VM harnesses. No dependency or browser-permission additions.

## Global Constraints

- Work only in `.worktrees/multimodal-plan-c`; do not alter the root checkout or unstaged review packages.
- Keep acquisition explicit-click, current-message-only, and provider-disabled during automated work.
- Keep exact origin `https://exmail.qq.com`, paths `/cgi-bin/download` and `/cgi-bin/viewfile`, non-empty query, credentials, no redirects, context revalidation, and existing limits.
- Never derive a filename from the URL query and never expose a private URL, query, cookie, token, local path, Base64, `File`, or exception detail.
- Do not add `downloads`, filesystem, cookie, storage, scripting, or broader host permissions.
- Treat only `attachment_insights[].status == "parsed"` as proof of content analysis.

---

### Task 1: Accept the verified legacy Tencent download control

**Files:**
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/content/current_message_collector.js`
- Modify: `tests/test_browser_extension_task6_adapter.py`
- Modify: `tests/test_browser_extension_current_message_collector.py`
- Modify: `tests/test_browser_extension_tencent_legacy_context.py`

**Interfaces:**
- Existing `attachment_files` and `resource_limitations` shapes remain unchanged.
- Legacy positive evidence is exact `/cgi-bin/download` plus non-empty `target` and supported visible metadata when `download` is absent.

- [ ] **Step 1: Add the failing recreated DOM tests**

Create a sanitized fixture containing visible sibling `.readmailinfo`, `#mailContentContainer.qmbox`, and:

```html
<a href="/cgi-bin/download?opaque=synthetic" target="_blank">synthetic.pdf</a>
```

Assert exactly one fetch with `credentials: "include"` and `redirect: "error"`, one PDF `attachment_file`, and no limitation. Add negative subtests for missing `target`, `/cgi-bin/viewfile` without `download`, anchor inside qmbox, external origin, empty query, unsupported visible type, negative profile/signature hint, redirect, and changed context.

- [ ] **Step 2: Run RED**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_browser_extension_task6_adapter tests.test_browser_extension_current_message_collector tests.test_browser_extension_tencent_legacy_context -v
```

Expected: the positive legacy fixture produces zero fetches because `download` is absent; all negative controls remain green.

- [ ] **Step 3: Implement the minimal legacy positive signal**

In the adapter, pass `baseHref` into positive-evidence validation and add:

```javascript
function isLegacyTencentDownloadControl(element, baseHref) {
  try {
    const resolved = new URL(String(element.getAttribute("href") || ""), baseHref);
    return normalizeText(element.getAttribute("target")).length > 0 &&
      resolved.origin === EXMAIL_ORIGIN &&
      resolved.protocol === "https:" &&
      !resolved.username && !resolved.password &&
      resolved.pathname === "/cgi-bin/download" &&
      resolved.search.length > 1 &&
      hasSupportedVisibleAttachmentHint(element);
  } catch (error) {
    return false;
  }
}
```

In the collector, pass `resolvedUrl` into its positive-evidence function and require the same exact origin/path/query/target rule plus `metadata.type` from visible attributes/text. Keep the existing negative hint check. Do not authorize `viewfile` without `download` and do not inspect `onclick` or query values.

- [ ] **Step 4: Run GREEN and syntax checks**

```powershell
& $py -B -m unittest tests.test_browser_extension_task6_adapter tests.test_browser_extension_current_message_collector tests.test_browser_extension_tencent_legacy_context -v
node --check frontend/browser_extension/content/exmail_adapter.js
node --check frontend/browser_extension/content/current_message_collector.js
```

Expected: positive fixture fetches once; all negative fixtures pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/browser_extension/content/exmail_adapter.js frontend/browser_extension/content/current_message_collector.js tests/test_browser_extension_task6_adapter.py tests/test_browser_extension_current_message_collector.py tests/test_browser_extension_tencent_legacy_context.py
git commit -m "fix: recognize legacy Tencent attachments"
```

### Task 2: Add the explicit local-file fallback

**Files:**
- Create: `frontend/browser_extension/shared/manual_attachment_files.js`
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/browser_extension/popup.js`
- Modify: `frontend/browser_extension/popup.css`
- Create: `tests/test_browser_extension_manual_attachment_files.py`
- Modify: `tests/test_browser_extension_task6_popup.py`
- Modify: `tests/test_browser_extension_task_focused_ui.py`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_browser_extension_task6_contracts.py`

**Interfaces:**
- Produces `EmailAssistantManualAttachmentFiles.readSelectedFiles(fileList)`.
- Produces `mergeAttachmentFiles(manualFiles, automaticFiles, limitations)`.
- Produces only the existing `{filename, type, size, content_base64}` items and fixed resource limitations.

- [ ] **Step 1: Write failing pure-module and popup tests**

Test supported image/PDF/XLSX/DOCX conversion, safe basename, fixed read error, 5-file cap, 10 MiB per file, 25 MiB aggregate, manual-first deduplication, and absence of path/URL/timestamp/private fields. Test that popup load and input `change` perform zero file reads; one Analyze performs one read; stale revalidation makes zero backend calls; every exit clears `input.value` and re-enables controls.

- [ ] **Step 2: Run RED**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_browser_extension_manual_attachment_files tests.test_browser_extension_task6_popup tests.test_browser_extension_task_focused_ui tests.test_browser_extension_static tests.test_browser_extension_task6_contracts -v
```

Expected: missing module/markup and no manual merge behavior.

- [ ] **Step 3: Implement the bounded pure module**

Expose a frozen namespace and use exact limits:

```javascript
const MAX_RESOURCE_COUNT = 5;
const MAX_RESOURCE_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_RESOURCE_BYTES = 25 * 1024 * 1024;

async function readSelectedFiles(fileList) {
  const files = Array.from(fileList || []).slice(0, MAX_RESOURCE_COUNT + 1);
  const attachmentFiles = [];
  const limitations = [];
  let totalBytes = 0;
  for (const file of files) {
    const metadata = safeSelectedFileMetadata(file);
    if (!metadata || metadata.size > MAX_RESOURCE_BYTES || totalBytes + metadata.size > MAX_TOTAL_RESOURCE_BYTES) {
      limitations.push(fixedLimitation("frontend_limit"));
      continue;
    }
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      if (bytes.byteLength !== metadata.size) {
        limitations.push(fixedLimitation("resource_read_failed"));
        continue;
      }
      attachmentFiles.push({ ...metadata, content_base64: boundedBase64(bytes) });
      totalBytes += bytes.byteLength;
      bytes.fill(0);
    } catch (error) {
      limitations.push(fixedLimitation("resource_read_failed"));
    }
  }
  return { attachment_files: attachmentFiles, resource_limitations: limitations };
}
```

Use a closed extension/MIME map and strip every path component from `file.name`. Never serialize `webkitRelativePath`, `lastModified`, the `File` object, or exception text.

- [ ] **Step 4: Wire the picker into the Analyze lifecycle**

Add a default-collapsed `<details>` with exact `accept` values and `multiple`. Load `shared/manual_attachment_files.js` before `popup.js`. In `analyzeCurrentMessage`, extract and fingerprint the current message first, read selected files only inside that click handler, merge them under aggregate limits, revalidate the fingerprint before the API call, and render merged metadata. In `finally`, clear `input.value`, drop local arrays, and re-enable the input/button.

- [ ] **Step 5: Run GREEN and syntax checks**

Run the Task 2 command, then:

```powershell
node --check frontend/browser_extension/shared/manual_attachment_files.js
node --check frontend/browser_extension/popup.js
```

Expected: focused tests and syntax checks pass with unchanged request fields.

- [ ] **Step 6: Commit**

```powershell
git add frontend/browser_extension/shared/manual_attachment_files.js frontend/browser_extension/popup.html frontend/browser_extension/popup.js frontend/browser_extension/popup.css tests/test_browser_extension_manual_attachment_files.py tests/test_browser_extension_task6_popup.py tests/test_browser_extension_task_focused_ui.py tests/test_browser_extension_static.py tests/test_browser_extension_task6_contracts.py
git commit -m "feat: add manual attachment fallback"
```

### Task 3: Prove parsed status and cleanup truthfully

**Files:**
- Modify: `frontend/browser_extension/shared/render_analysis.js`
- Modify: `tests/test_browser_extension_renderer_behavior.py`
- Modify: `tests/test_resource_limitation_vertical_contract.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_attachment_storage.py`

**Interfaces:**
- No new public field. UI derives counts only from existing attachment statuses.
- Backend request-local cleanup remains unchanged.

- [ ] **Step 1: Write failing truthfulness tests**

Add a renderer test proving one `unavailable` insight displays as not read, while one `parsed` insight displays as parsed. Update the vertical synthetic control to omit `download`, complete automatic acquisition, parse a generated supported file, assert `status == "parsed"`, and assert the request temporary directory is empty after success and provider failure.

- [ ] **Step 2: Run RED**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_browser_extension_renderer_behavior tests.test_resource_limitation_vertical_contract tests.test_api tests.test_attachment_storage -v
```

Expected: status aggregation and/or no-download vertical parse assertion fails.

- [ ] **Step 3: Implement local status aggregation only**

Add a renderer helper that counts the fixed enum values `parsed`, `metadata_only`, `unavailable`, and `failed`. Render only counts and fixed labels. Do not expose provider diagnostics, filenames, paths, URLs, source IDs, or content in the aggregate.

- [ ] **Step 4: Run GREEN**

Run the Task 3 command and `node --check frontend/browser_extension/shared/render_analysis.js`. Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/browser_extension/shared/render_analysis.js tests/test_browser_extension_renderer_behavior.py tests/test_resource_limitation_vertical_contract.py tests/test_api.py tests/test_attachment_storage.py
git commit -m "test: verify attachment parsing lifecycle"
```

### Task 4: Synchronize governance and run release gates

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/decisions/0007-multimodal-current-email-analysis.md`
- Modify: `docs/security/email_data_handling.md`
- Modify: `docs/api/frontend_backend_flow.md`
- Modify: `docs/api/backend_api_contract.md`
- Modify: `docs/operations/testing_checklist.md`
- Modify: `docs/operations/current_email_grounding_and_attachment_repair_task_brief.md`
- Modify: `docs/operations/project_status_log.md`
- Modify: `scripts/generate_project_status.py`
- Modify: relevant architecture/static/documentation/status tests

- [ ] **Step 1: Lock the acquisition boundary in tests and docs**

Document automatic in-memory fetch, explicit picker semantics, no downloads/storage permissions, request-finally deletion, crash-recovery meaning, and parsed-status truthfulness. Add static tests forbidding `chrome.downloads`, File System Access, Web Storage, IndexedDB, `chrome.storage`, local path fields, and new manifest permissions.

- [ ] **Step 2: Run focused extension and guard matrices**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_browser_extension_current_message_collector tests.test_browser_extension_task6_adapter tests.test_browser_extension_tencent_legacy_context tests.test_browser_extension_manual_attachment_files tests.test_browser_extension_task6_popup tests.test_browser_extension_renderer_behavior tests.test_architecture_constraints tests.test_static_linter_constraints tests.test_multimodal_documentation_contracts tests.test_generate_project_status -v
```

Expected: all pass.

- [ ] **Step 3: Run full release gates**

```powershell
& $py -B -m unittest discover -s tests
Get-ChildItem frontend/browser_extension -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
& $py -B scripts/generate_project_status.py --output docs/operations/project_status_log.md
& $py -B -m unittest discover -s tests
& $py -B scripts/repository_leakage_scan.py
& $py -B scripts/maintenance_scan.py --fail-on-high
git diff --check
```

Expected: full suite passes, every JS file parses, scans exit 0, and no sensitive or real-derived artifact is found.

- [ ] **Step 4: Request fresh code review and commit**

Resolve only bounded in-scope findings, then:

```powershell
git add AGENTS.md docs scripts/generate_project_status.py tests
git commit -m "docs: finalize attachment acquisition safeguards"
```

### Task 5: Separately authorized real smoke

**Preconditions:**
- Tasks 1-4 are review-clean and all offline gates pass.
- The operator explicitly authorizes one current-clicked-message attachment test.
- No navigation, mailbox scanning, send action, or content output is permitted.

- [ ] Reload the verified unpacked extension and refresh only the already opened message.
- [ ] Click Analyze once and inspect only fixed engine/status fields and structural counts.
- [ ] Confirm at least one supported attachment has `status == "parsed"`; do not infer success from count alone.
- [ ] Confirm the backend request temporary directory is empty afterward.
- [ ] If automatic acquisition still fails, use the explicit picker only after the operator selects the current-message file, then repeat the parsed-status check.
- [ ] Stop the bounded service and restore provider-disabled defaults.

### Task 6: Repair the diagnosed legacy automatic-acquisition seam

**Files:**
- Modify: `frontend/browser_extension/content/exmail_adapter.js`
- Modify: `frontend/browser_extension/content/exmail_visible_resource_classifier.js`
- Modify: `frontend/browser_extension/content/current_message_collector.js`
- Modify: focused browser-extension tests and active governance documents

**Approved boundary:**
- The resource container may be the existing direct parent or one additional
  legacy wrapper, but the selected outer container must remain a direct child
  of the verified document body.
- Only verified attachment anchors may be rendered below the current viewport.
  No scroll, click, or navigation occurs. Inline images keep the viewport gate.
- An exact untyped legacy download control may be fetched once. Payload bytes
  are released only after allowlisted response-header and signature validation.
- No URL query or arbitrary ancestor text is used for type inference.

- [x] **Step 1: Add failing synthetic DOM and response-validation tests**

Cover the bounded two-wrapper shape, a non-zero off-viewport attachment anchor,
an untyped exact download endpoint, supported PDF/image/OOXML header-signature
pairs, generic binary PDF/image responses, and fixed failure for conflicts,
HTML, unknown, truncated, hidden, zero-layout, deeper-wrapper, authored-body,
and off-viewport inline-image controls. Assert zero scroll, click, navigation,
provider, persistence, and second fetch.

- [x] **Step 2: Run RED**

Run the adapter, collector, classifier, legacy-context, vertical-contract, and
static/architecture focused suites. The new positive shape must fail before
implementation while existing controls remain green.

- [x] **Step 3: Implement the minimum bounded repair**

Mirror the exact container and ownership checks in adapter and collector. Split
rendered attachment layout from viewport-intersecting inline-image layout. Add
one internal deferred-type fact for exact verified legacy controls. Return a
type-derived generic filename when no safe DOM filename exists. Preserve all
existing count, byte, time, endpoint, redirect, context, identity, and cleanup
gates.

- [x] **Step 4: Run GREEN and release gates**

Run focused tests, all extension JavaScript syntax checks, the complete Python
suite, architecture/static/mechanical tests, leakage scan, project-status
generation, maintenance scan, and `git diff --check`. Do not perform a real
browser, mailbox, provider, or attachment operation in this task.

- [x] **Step 5: Independent review and progress record**

Resolve only Critical or Important in-scope findings, record fixed test counts
and commit range in the SDD ledger, and leave any later real smoke behind a new
explicit authorization gate.

Completion record, 2026-07-18: implementation commit `6d39860` and bounded
review-fix commit `baf5d62` passed the focused synthetic gate and independent
re-review with no remaining Critical, Important, or Minor findings. This is an
offline completion record only; it does not authorize or claim a successful
real Tencent attachment fetch, provider call, navigation, mailbox scan, or send.
