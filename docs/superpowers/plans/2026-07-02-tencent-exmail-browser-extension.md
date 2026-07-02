---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: implementation_plan
---

# Tencent Exmail Browser Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Chrome / Edge Manifest V3 prototype that analyzes the currently opened Tencent Exmail Web email through the existing local Python backend.

**Architecture:** Add a dependency-free extension under `frontend/browser_extension/` with a popup UI, a Tencent Exmail content adapter, and shared browser-side helpers. The extension runs only on `https://exmail.qq.com/*`, sends one user-confirmed current-email payload for the currently opened Tencent Exmail message to `http://127.0.0.1:8765/api/analyze-current-email`, and displays the existing analysis schema without storing secrets or real email bodies. The selected-text fallback is limited to user-selected email content from the currently opened Tencent Exmail message after the explicit Analyze click; it is not arbitrary webpage analysis and not background page scraping.

**Tech Stack:** Chrome / Edge Manifest V3, plain HTML/CSS/JavaScript, Python 3.12 `unittest`, existing Python local backend.

---

## File Structure

- Create `frontend/browser_extension/manifest.json`: Manifest V3 extension metadata, popup entry, host permissions for Tencent Exmail and local backend only.
- Create `frontend/browser_extension/popup.html`: Compact user-facing extension popup with analyze, status, analysis fields, draft textarea, and copy button.
- Create `frontend/browser_extension/popup.css`: Popup styling, fixed compact dimensions, readable states.
- Create `frontend/browser_extension/popup.js`: Popup controller that handles user clicks, requests extraction from the active Exmail tab, calls the local backend, and renders results.
- Create `frontend/browser_extension/content/exmail_adapter.js`: Content script that extracts the current email or message-scoped selected-text fallback only when messaged by the popup.
- Create `frontend/browser_extension/shared/api_client.js`: Local backend request helper.
- Create `frontend/browser_extension/shared/render_analysis.js`: Analysis rendering and clear-state helpers.
- Create `tests/test_browser_extension_manifest.py`: Manifest contract and permission tests.
- Create `tests/test_browser_extension_static.py`: Static safety, popup, API, and adapter contract tests.
- Create `docs/operations/tencent_exmail_browser_extension_task_brief.md`: Required task brief for the frontend route change.
- Modify `docs/decisions/adr_0002_frontend_route.md`: Mark Tencent Exmail browser extension as the chosen second-stage route.
- Modify `docs/product/roadmap.md`: Record phase 2 route selection.
- Modify `docs/product/feature_scope.md`: Add Tencent Exmail browser extension as the selected second-stage prototype while preserving non-goals.
- Modify `docs/operations/project_structure.md`: Add the new extension directory responsibilities.
- Modify `README.md`: Add local backend plus unpacked-extension usage notes.
- Modify `docs/operations/setup_checklist.md`: Add extension loading steps.
- Modify `docs/operations/testing_checklist.md`: Add browser extension verification steps.
- Modify `docs/operations/project_status_log.md`: Regenerated at the end.

## Task 1: Document the Route Decision and Task Brief

**Files:**
- Create: `docs/operations/tencent_exmail_browser_extension_task_brief.md`
- Modify: `docs/decisions/adr_0002_frontend_route.md`
- Modify: `docs/product/roadmap.md`
- Modify: `docs/product/feature_scope.md`
- Test: `tests/test_browser_extension_static.py`

- [ ] **Step 1: Write the failing documentation contract tests**

Create `tests/test_browser_extension_static.py` with these initial tests:

```python
"""Static tests for the Tencent Exmail browser extension prototype."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"


class BrowserExtensionStaticTests(unittest.TestCase):
    def test_tencent_exmail_route_decision_is_documented(self) -> None:
        adr = (ROOT / "docs" / "decisions" / "adr_0002_frontend_route.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "product" / "roadmap.md").read_text(encoding="utf-8")
        scope = (ROOT / "docs" / "product" / "feature_scope.md").read_text(encoding="utf-8")

        self.assertIn("Tencent Exmail", adr)
        self.assertIn("Chrome / Edge browser extension", adr)
        self.assertIn("exmail.qq.com", adr)
        self.assertIn("Tencent Exmail", roadmap)
        self.assertIn("Tencent Exmail", scope)

    def test_tencent_exmail_task_brief_exists(self) -> None:
        brief = ROOT / "docs" / "operations" / "tencent_exmail_browser_extension_task_brief.md"

        self.assertTrue(brief.exists())
        text = brief.read_text(encoding="utf-8")
        self.assertIn("Tencent Exmail", text)
        self.assertIn("https://exmail.qq.com/*", text)
        self.assertIn("No automatic send", text)
        self.assertIn("No mailbox account integration", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: failure because the Tencent Exmail route docs and task brief do not exist yet.

- [ ] **Step 3: Add the task brief**

Create `docs/operations/tencent_exmail_browser_extension_task_brief.md`:

```markdown
---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Tencent Exmail Browser Extension Task Brief

## Task

Build the second-phase Chrome / Edge browser extension prototype for Tencent Exmail Web.

## Goal

Let the user open one email in Tencent Exmail, click an explicit extension button, analyze only that current email through the local Python backend, and review the returned summary, priority, category, risks, actions, and reply draft.

## Target Surface

- Browser extension route: Chrome / Edge browser extension.
- Mailbox web app: Tencent Exmail Web.
- Match pattern: `https://exmail.qq.com/*`.
- Local backend: `http://127.0.0.1:8765/api/analyze-current-email`.

## In Scope

- Manifest V3 extension files under `frontend/browser_extension/`.
- Tencent Exmail content adapter.
- Selected-text fallback for user-selected email content from the currently opened Tencent Exmail message when DOM extraction cannot identify fields.
- Popup UI for analyze, result display, and copy draft.
- Static and contract tests using Python `unittest`.
- Documentation updates for setup, testing, and route decision.

## Out of Scope

- No mailbox account integration.
- No OAuth, password, token, cookie export, or Tencent API integration.
- No automatic send.
- No automatic delete, archive, move, mark, forward, or reply.
- No background mailbox scan.
- No frontend OpenAI calls.
- No frontend API keys.
- No browser storage of real email bodies.

## Acceptance Criteria

- The unpacked extension can be loaded in Chrome or Edge.
- The extension is scoped to Tencent Exmail and the local backend.
- Clicking Analyze submits one current-email payload with `user_confirmed: true`.
- Selected-text fallback can analyze user-selected email content from the currently opened Tencent Exmail message.
- The popup displays the backend analysis result and copyable reply draft.
- `python -m unittest discover -s tests` passes.
- `python scripts/maintenance_scan.py` reports no findings.
```

- [ ] **Step 4: Update route docs**

Modify `docs/decisions/adr_0002_frontend_route.md` so its body contains:

```markdown
## 状态

已决定。

## 决策

第二阶段正式前端原型选择 Chrome / Edge 浏览器扩展，优先适配腾讯企业邮箱 Web (`https://exmail.qq.com/*`)。

扩展只在用户点击明确的 Analyze 按钮后读取当前打开的 Tencent Exmail 邮件，或在 DOM 字段提取失败时读取该已打开邮件中的用户选中邮件正文内容，并调用本地 Python 后端。它不接入真实邮箱账号，不读取凭据或 token，不扫描邮箱，不自动发送、删除、归档、移动或回复邮件。
```

Modify `docs/product/roadmap.md` phase 2 to include:

```markdown
- 已选择第二阶段原型路线：Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)。
```

Modify `docs/product/feature_scope.md` under later/second-stage evaluation to include:

```markdown
- 第二阶段已选择：Chrome / Edge browser extension for Tencent Exmail Web (`https://exmail.qq.com/*`)。
```

- [ ] **Step 5: Run the targeted tests and verify they pass**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: `OK`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add tests\test_browser_extension_static.py docs\operations\tencent_exmail_browser_extension_task_brief.md docs\decisions\adr_0002_frontend_route.md docs\product\roadmap.md docs\product\feature_scope.md
git commit -m "docs: select Tencent Exmail extension route"
```

## Task 2: Add Manifest and Extension Skeleton

**Files:**
- Create: `tests/test_browser_extension_manifest.py`
- Create: `frontend/browser_extension/manifest.json`
- Create: `frontend/browser_extension/popup.html`
- Create: `frontend/browser_extension/popup.css`
- Create: `frontend/browser_extension/content/exmail_adapter.js`
- Create: `frontend/browser_extension/shared/api_client.js`
- Create: `frontend/browser_extension/shared/render_analysis.js`
- Modify: `tests/test_browser_extension_static.py`

- [ ] **Step 1: Write failing manifest tests**

Create `tests/test_browser_extension_manifest.py`:

```python
"""Manifest contract tests for the Tencent Exmail browser extension."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"
MANIFEST = EXTENSION / "manifest.json"


class BrowserExtensionManifestTests(unittest.TestCase):
    def load_manifest(self) -> dict[str, object]:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_exists_and_uses_manifest_v3(self) -> None:
        manifest = self.load_manifest()

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["name"], "Email AI Assistant for Tencent Exmail")
        self.assertIn("action", manifest)

    def test_manifest_permissions_are_minimal(self) -> None:
        manifest = self.load_manifest()

        permissions = manifest.get("permissions", [])
        host_permissions = manifest.get("host_permissions", [])

        self.assertEqual(permissions, ["activeTab"])
        self.assertEqual(host_permissions, [
            "https://exmail.qq.com/*",
            "http://127.0.0.1:8765/*",
        ])
        self.assertNotIn("<all_urls>", json.dumps(manifest))
        self.assertNotIn("tabs", permissions)
        self.assertNotIn("storage", permissions)

    def test_manifest_registers_exmail_content_adapter(self) -> None:
        manifest = self.load_manifest()
        content_scripts = manifest.get("content_scripts", [])

        self.assertEqual(len(content_scripts), 1)
        script = content_scripts[0]
        self.assertEqual(script["matches"], ["https://exmail.qq.com/*"])
        self.assertEqual(script["js"], ["content/exmail_adapter.js"])
        self.assertEqual(script["run_at"], "document_idle")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Extend static file-existence tests**

Add these tests to `tests/test_browser_extension_static.py`:

```python
    def test_browser_extension_files_exist(self) -> None:
        expected = [
            "manifest.json",
            "popup.html",
            "popup.css",
            "popup.js",
            "content/exmail_adapter.js",
            "shared/api_client.js",
            "shared/render_analysis.js",
        ]

        for relative in expected:
            with self.subTest(relative=relative):
                self.assertTrue((EXTENSION / relative).exists())
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_manifest tests.test_browser_extension_static
```

Expected: failure because extension files do not exist yet.

- [ ] **Step 4: Create `manifest.json`**

Create `frontend/browser_extension/manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "Email AI Assistant for Tencent Exmail",
  "description": "Analyze the currently opened Tencent Exmail message through the local Email AI Assistant backend.",
  "version": "0.2.0",
  "action": {
    "default_title": "Email AI Assistant",
    "default_popup": "popup.html"
  },
  "permissions": ["activeTab"],
  "host_permissions": [
    "https://exmail.qq.com/*",
    "http://127.0.0.1:8765/*"
  ],
  "content_scripts": [
    {
      "matches": ["https://exmail.qq.com/*"],
      "js": ["content/exmail_adapter.js"],
      "run_at": "document_idle"
    }
  ]
}
```

- [ ] **Step 5: Create popup skeleton**

Create `frontend/browser_extension/popup.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Email AI Assistant</title>
    <link rel="stylesheet" href="popup.css">
  </head>
  <body>
    <main class="popup-shell">
      <header class="popup-header">
        <div>
          <p class="eyebrow">Tencent Exmail</p>
          <h1>Email AI Assistant</h1>
        </div>
        <span id="priority" class="priority-pill">-</span>
      </header>

      <button id="analyze-button" type="button">Analyze current email</button>
      <p id="status" class="status-line">Open an email, then click Analyze.</p>

      <section class="result-section" aria-label="Analysis result">
        <h2 id="summary">No analysis yet</h2>
        <dl>
          <dt>Category</dt>
          <dd id="category">-</dd>
          <dt>Risks</dt>
          <dd id="risks">-</dd>
          <dt>Actions</dt>
          <dd id="actions">-</dd>
        </dl>
      </section>

      <label class="draft-label">
        Draft
        <textarea id="draft" rows="8" readonly></textarea>
      </label>
      <button id="copy-draft-button" type="button">Copy draft</button>
    </main>

    <script src="shared/api_client.js"></script>
    <script src="shared/render_analysis.js"></script>
    <script src="popup.js"></script>
  </body>
</html>
```

Create `frontend/browser_extension/popup.css`:

```css
:root {
  color-scheme: light;
  font-family: Arial, "Microsoft YaHei", sans-serif;
  color: #17202a;
  background: #f4f6f8;
}

* {
  box-sizing: border-box;
}

body {
  width: 420px;
  margin: 0;
}

.popup-shell {
  display: grid;
  gap: 12px;
  padding: 16px;
}

.popup-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #52616f;
  font-size: 12px;
  text-transform: uppercase;
}

h1,
h2 {
  margin: 0;
}

h1 {
  font-size: 20px;
}

h2 {
  font-size: 16px;
  line-height: 1.35;
}

button {
  border: 0;
  border-radius: 6px;
  padding: 10px 14px;
  background: #146c94;
  color: #ffffff;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}

.status-line {
  margin: 0;
  color: #52616f;
  min-height: 20px;
}

.priority-pill {
  border-radius: 999px;
  background: #e3f2fd;
  color: #0b5c7e;
  padding: 6px 10px;
  font-size: 13px;
  font-weight: 700;
}

dl {
  display: grid;
  grid-template-columns: 78px 1fr;
  gap: 8px 12px;
  margin: 12px 0 0;
}

dt {
  color: #52616f;
  font-weight: 700;
}

dd {
  margin: 0;
}

.draft-label {
  display: grid;
  gap: 6px;
  font-weight: 700;
}

textarea {
  width: 100%;
  border: 1px solid #bcccdc;
  border-radius: 6px;
  padding: 10px;
  font: inherit;
  resize: vertical;
}

#copy-draft-button {
  background: #335c67;
}
```

- [ ] **Step 6: Create empty module placeholders**

Create `frontend/browser_extension/popup.js`:

```javascript
/* global EmailAssistantApi, EmailAssistantRender, chrome */
```

Create `frontend/browser_extension/content/exmail_adapter.js`:

```javascript
/* global chrome */
```

Create `frontend/browser_extension/shared/api_client.js`:

```javascript
window.EmailAssistantApi = {};
```

Create `frontend/browser_extension/shared/render_analysis.js`:

```javascript
window.EmailAssistantRender = {};
```

- [ ] **Step 7: Run targeted tests and verify they pass**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_manifest tests.test_browser_extension_static
```

Expected: `OK`.

- [ ] **Step 8: Commit**

Run:

```powershell
git add tests\test_browser_extension_manifest.py tests\test_browser_extension_static.py frontend\browser_extension
git commit -m "feat: add Tencent Exmail extension skeleton"
```

## Task 3: Implement Shared API Client and Result Renderer

**Files:**
- Modify: `tests/test_browser_extension_static.py`
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/browser_extension/shared/render_analysis.js`

- [ ] **Step 1: Write failing shared-helper tests**

Add these tests to `tests/test_browser_extension_static.py`:

```python
    def test_api_client_calls_only_local_backend(self) -> None:
        script = (EXTENSION / "shared" / "api_client.js").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8765/api/analyze-current-email", script)
        self.assertIn("fetch(", script)
        self.assertIn('"Content-Type": "application/json"', script)
        self.assertNotIn("api.openai.com", script)
        self.assertNotIn("OPENAI_API_KEY", script)
        self.assertNotIn("process.env", script)

    def test_renderer_displays_existing_analysis_schema(self) -> None:
        script = (EXTENSION / "shared" / "render_analysis.js").read_text(encoding="utf-8")

        self.assertIn("renderAnalysis", script)
        self.assertIn("clearAnalysis", script)
        self.assertIn("analysis.priority", script)
        self.assertIn("analysis.summary", script)
        self.assertIn("analysis.category", script)
        self.assertIn("analysis.risk_flags", script)
        self.assertIn("analysis.suggested_actions", script)
        self.assertIn("analysis.reply_draft.body", script)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: failure because helper implementations are placeholders.

- [ ] **Step 3: Implement `api_client.js`**

Replace `frontend/browser_extension/shared/api_client.js` with:

```javascript
(function () {
  const ANALYZE_URL = "http://127.0.0.1:8765/api/analyze-current-email";

  async function analyzeCurrentEmail(payload) {
    const response = await fetch(ANALYZE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_confirmed: true,
        subject: payload.subject || "",
        from: payload.from || "",
        to: Array.isArray(payload.to) ? payload.to : [],
        sent_at: payload.sent_at || "",
        body_text: payload.body_text || "",
      }),
    });

    return response.json();
  }

  window.EmailAssistantApi = {
    analyzeCurrentEmail,
  };
})();
```

- [ ] **Step 4: Implement `render_analysis.js`**

Replace `frontend/browser_extension/shared/render_analysis.js` with:

```javascript
(function () {
  function renderAnalysis(fields, analysis) {
    fields.priority.textContent = analysis.priority || "-";
    fields.summary.textContent = analysis.summary || "No summary returned";
    fields.category.textContent = analysis.category || "-";
    fields.risks.textContent = formatRisks(analysis.risk_flags);
    fields.actions.textContent = formatActions(analysis.suggested_actions);
    fields.draft.value = analysis.reply_draft?.body || "";
  }

  function clearAnalysis(fields) {
    fields.priority.textContent = "-";
    fields.summary.textContent = "No analysis yet";
    fields.category.textContent = "-";
    fields.risks.textContent = "-";
    fields.actions.textContent = "-";
    fields.draft.value = "";
  }

  function formatRisks(riskFlags) {
    if (!Array.isArray(riskFlags) || riskFlags.length === 0) {
      return "none";
    }
    return riskFlags.map((item) => item.type).filter(Boolean).join(", ") || "none";
  }

  function formatActions(actions) {
    if (!Array.isArray(actions) || actions.length === 0) {
      return "-";
    }
    return actions.map((item) => item.description).filter(Boolean).join(" ");
  }

  window.EmailAssistantRender = {
    clearAnalysis,
    renderAnalysis,
  };
})();
```

- [ ] **Step 5: Run targeted tests and verify they pass**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: `OK`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add tests\test_browser_extension_static.py frontend\browser_extension\shared\api_client.js frontend\browser_extension\shared\render_analysis.js
git commit -m "feat: add extension backend client and renderer"
```

## Task 4: Implement Tencent Exmail Content Adapter

**Files:**
- Modify: `tests/test_browser_extension_static.py`
- Modify: `frontend/browser_extension/content/exmail_adapter.js`

- [ ] **Step 1: Write failing adapter contract tests**

Add these tests to `tests/test_browser_extension_static.py`:

```python
    def test_exmail_adapter_extracts_only_on_popup_message(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("chrome.runtime.onMessage.addListener", script)
        self.assertIn("EXTRACT_CURRENT_EMAIL", script)
        self.assertIn("extractCurrentEmail", script)
        self.assertNotIn("setInterval", script)
        self.assertNotIn("MutationObserver", script)

    def test_exmail_adapter_has_selected_text_fallback(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("getSelection", script)
        self.assertIn("selected_text", script)
        self.assertIn("body_text", script)
        self.assertIn("hasMessageContext", script)
        self.assertIn("user-selected email content", script)
        self.assertIn("not arbitrary webpage analysis", script)
        self.assertIn("Open one email or select visible email body content first", script)

    def test_exmail_adapter_does_not_perform_mailbox_actions(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")
        forbidden = [
            "sendMail",
            "deleteMessage",
            "archiveMessage",
            "trashMessage",
            "messages.trash",
            "forward",
        ]

        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, script)

    def test_exmail_adapter_does_not_log_email_body(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertNotIn("console.log", script)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: failure because the adapter is still a placeholder.

- [ ] **Step 3: Implement `exmail_adapter.js`**

Replace `frontend/browser_extension/content/exmail_adapter.js` with:

```javascript
/* global chrome */
(function () {
  const MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL";

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || message.type !== MESSAGE_TYPE) {
      return false;
    }

    sendResponse(extractCurrentEmail());
    return false;
  });

  function extractCurrentEmail() {
    const documents = collectAccessibleDocuments(window);
    for (const doc of documents) {
      const payload = extractFromDocument(doc);
      if (payload.body_text) {
        return { ok: true, source: "dom", payload };
      }
    }

    const selected = getSelectedEmailContent(documents);
    if (selected) {
      return {
        ok: true,
        source: "selected_text",
        payload: {
          subject: document.title || "Tencent Exmail selected email content",
          from: "",
          to: [],
          sent_at: "",
          body_text: selected,
        },
      };
    }

    return {
      ok: false,
      error: "Open one email or select visible email body content first. The fallback is user-selected email content only, not arbitrary webpage analysis.",
    };
  }

  function collectAccessibleDocuments(rootWindow) {
    const documents = [];
    visitWindow(rootWindow, documents);
    return documents;
  }

  function visitWindow(targetWindow, documents) {
    try {
      if (targetWindow.document) {
        documents.push(targetWindow.document);
      }
      for (let index = 0; index < targetWindow.frames.length; index += 1) {
        visitWindow(targetWindow.frames[index], documents);
      }
    } catch (error) {
      return;
    }
  }

  function extractFromDocument(doc) {
    if (!hasMessageContext(doc)) {
      return { subject: "", from: "", to: [], sent_at: "", body_text: "" };
    }

    const subject = findSubject(doc);
    const body = findBody(doc);

    if (!body) {
      return { subject: "", from: "", to: [], sent_at: "", body_text: "" };
    }

    return {
      subject: subject || doc.title || "Tencent Exmail message",
      from: findLabeledText(doc, ["发件人", "From"]),
      to: splitRecipients(findLabeledText(doc, ["收件人", "To"])),
      sent_at: findLabeledText(doc, ["时间", "发送时间", "Date", "Sent"]),
      body_text: body,
    };
  }

  function findSubject(doc) {
    const titleCandidate = firstText(doc, [
      "#subject",
      ".subject",
      ".mail_subject",
      "[role='heading']",
      "h1",
      "h2",
    ]);
    return titleCandidate || "";
  }

  function findBody(doc) {
    const bodyCandidate = firstText(doc, [
      "#mailContentContainer",
      "#mailContent",
      ".mail_content",
      ".mail-detail-content",
      ".content",
      "[role='main']",
    ]);

    if (bodyCandidate && bodyCandidate.length >= 5) {
      return bodyCandidate;
    }

    return "";
  }

  function hasMessageContext(doc) {
    const markerText = normalizeText(doc.body?.innerText || "");
    if (!markerText) {
      return false;
    }

    return Boolean(
      firstText(doc, ["#subject", ".subject", ".mail_subject", "#mailContent", "#mailContentContainer"]) ||
      markerText.includes("发件人") ||
      markerText.includes("收件人") ||
      markerText.includes("From:") ||
      markerText.includes("To:")
    );
  }

  function firstText(doc, selectors) {
    for (const selector of selectors) {
      const element = doc.querySelector(selector);
      const text = normalizeText(element?.innerText || element?.textContent || "");
      if (text) {
        return text;
      }
    }
    return "";
  }

  function findLabeledText(doc, labels) {
    const text = normalizeText(doc.body?.innerText || "");
    if (!text) {
      return "";
    }

    const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
    for (const label of labels) {
      const line = lines.find((item) => item.startsWith(`${label}:`) || item.startsWith(`${label}：`));
      if (line) {
        return line.slice(label.length + 1).trim();
      }
    }
    return "";
  }

  function splitRecipients(value) {
    if (!value) {
      return [];
    }
    return value.split(/[;,；，]/).map((item) => item.trim()).filter(Boolean);
  }

  function getSelectedEmailContent(documents) {
    for (const doc of documents) {
      if (!hasMessageContext(doc)) {
        continue;
      }
      const view = doc.defaultView;
      const text = normalizeText(view?.getSelection?.().toString() || "");
      if (text) {
        return text;
      }
    }
    return "";
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }
})();
```

- [ ] **Step 4: Run targeted tests and verify they pass**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: `OK`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add tests\test_browser_extension_static.py frontend\browser_extension\content\exmail_adapter.js
git commit -m "feat: extract Tencent Exmail current email"
```

## Task 5: Implement Popup Controller

**Files:**
- Modify: `tests/test_browser_extension_static.py`
- Modify: `frontend/browser_extension/popup.js`

- [ ] **Step 1: Write failing popup behavior tests**

Add these tests to `tests/test_browser_extension_static.py`:

```python
    def test_popup_requests_current_email_after_user_click(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector("#analyze-button").addEventListener("click"', script)
        self.assertIn("chrome.tabs.query", script)
        self.assertIn("chrome.tabs.sendMessage", script)
        self.assertIn("EXTRACT_CURRENT_EMAIL", script)
        self.assertIn("EmailAssistantApi.analyzeCurrentEmail", script)
        self.assertIn("EmailAssistantRender.renderAnalysis", script)

    def test_popup_handles_copy_draft(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector("#copy-draft-button").addEventListener("click"', script)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn("No draft to copy", script)
        self.assertIn("Copy failed", script)

    def test_popup_has_user_facing_error_states(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn("Open a Tencent Exmail tab first", script)
        self.assertIn("Open a Tencent Exmail message or select email body text from that opened message first", script)
        self.assertIn("Local analysis service unavailable", script)
        self.assertIn("Analysis failed", script)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: failure because `popup.js` is still a placeholder.

- [ ] **Step 3: Implement `popup.js`**

Replace `frontend/browser_extension/popup.js` with:

```javascript
/* global EmailAssistantApi, EmailAssistantRender, chrome */
const fields = {
  status: document.querySelector("#status"),
  priority: document.querySelector("#priority"),
  summary: document.querySelector("#summary"),
  category: document.querySelector("#category"),
  risks: document.querySelector("#risks"),
  actions: document.querySelector("#actions"),
  draft: document.querySelector("#draft"),
  analyzeButton: document.querySelector("#analyze-button"),
  copyButton: document.querySelector("#copy-draft-button"),
};

document.querySelector("#analyze-button").addEventListener("click", async () => {
  EmailAssistantRender.clearAnalysis(fields);
  setBusy(true, "Reading current email");

  let extraction;
  try {
    extraction = await requestCurrentEmail();
  } catch (error) {
    setBusy(false, "Open a Tencent Exmail tab first");
    return;
  }

  if (!extraction?.ok) {
    setBusy(false, extraction?.error || "Open a Tencent Exmail message or select email body text from that opened message first");
    return;
  }

  setBusy(true, "Analyzing");
  let data;
  try {
    data = await EmailAssistantApi.analyzeCurrentEmail(extraction.payload);
  } catch (error) {
    setBusy(false, "Local analysis service unavailable");
    return;
  }

  if (!data.ok) {
    setBusy(false, data.error?.message || "Analysis failed");
    return;
  }

  EmailAssistantRender.renderAnalysis(fields, data.analysis);
  setBusy(false, `Saved #${data.saved_id || "-"}`);
});

document.querySelector("#copy-draft-button").addEventListener("click", async () => {
  const draft = fields.draft.value.trim();
  if (!draft) {
    fields.status.textContent = "No draft to copy";
    return;
  }

  try {
    await navigator.clipboard.writeText(fields.draft.value);
    fields.status.textContent = "Draft copied";
  } catch (error) {
    fields.status.textContent = "Copy failed";
  }
});

async function requestCurrentEmail() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.startsWith("https://exmail.qq.com/")) {
    return { ok: false, error: "Open a Tencent Exmail tab first." };
  }

  return chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_CURRENT_EMAIL" });
}

function setBusy(isBusy, message) {
  fields.analyzeButton.disabled = isBusy;
  fields.status.textContent = message;
}
```

- [ ] **Step 4: Run targeted tests and verify they pass**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: `OK`.

- [ ] **Step 5: Commit**

Run:

```powershell
git add tests\test_browser_extension_static.py frontend\browser_extension\popup.js
git commit -m "feat: connect extension popup to local analysis"
```

## Task 6: Strengthen Frontend Safety Constraints

**Files:**
- Modify: `tests/test_browser_extension_static.py`
- Optional Modify: extension files only if tests reveal violations.

- [ ] **Step 1: Add frontend safety tests**

Add these tests to `tests/test_browser_extension_static.py`:

```python
    def test_browser_extension_has_no_secret_or_openai_markers(self) -> None:
        forbidden = [
            "OPENAI_API_KEY",
            "api.openai.com",
            "/v1/responses",
            "/v1/chat/completions",
            "new OpenAI",
            "process.env",
            ".env",
            "sk-",
        ]

        for path in EXTENSION.rglob("*"):
            if path.is_dir() or path.suffix not in {".js", ".html", ".json", ".css"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker, text)

    def test_browser_extension_has_no_high_risk_mailbox_actions(self) -> None:
        forbidden = [
            "sendMail",
            "gmail.users.messages.send",
            "archiveMessage",
            "deleteMessage",
            "trashMessage",
            "messages.trash",
        ]

        for path in EXTENSION.rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path, marker=marker):
                    self.assertNotIn(marker, text)
```

- [ ] **Step 2: Run tests and verify the safety contract**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static tests.test_static_linter_constraints
```

Expected: `OK`. If a marker fails because of documentation text inside a test string, keep the forbidden list in tests but avoid adding the marker to production frontend files.

- [ ] **Step 3: Commit**

Run:

```powershell
git add tests\test_browser_extension_static.py
git commit -m "test: enforce browser extension safety boundaries"
```

## Task 7: Update User Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/operations/setup_checklist.md`
- Modify: `docs/operations/testing_checklist.md`
- Modify: `docs/operations/project_structure.md`
- Modify: `tests/test_browser_extension_static.py`

- [ ] **Step 1: Add failing documentation tests**

Add these tests to `tests/test_browser_extension_static.py`:

```python
    def test_readme_documents_browser_extension_usage(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("frontend/browser_extension", readme)
        self.assertIn("exmail.qq.com", readme)
        self.assertIn("Load unpacked", readme)
        self.assertIn("start_local_service.cmd", readme)

    def test_operations_docs_document_extension_setup_and_testing(self) -> None:
        setup = (ROOT / "docs" / "operations" / "setup_checklist.md").read_text(encoding="utf-8")
        testing = (ROOT / "docs" / "operations" / "testing_checklist.md").read_text(encoding="utf-8")
        structure = (ROOT / "docs" / "operations" / "project_structure.md").read_text(encoding="utf-8")

        self.assertIn("frontend/browser_extension", setup)
        self.assertIn("Load unpacked", setup)
        self.assertIn("Tencent Exmail", testing)
        self.assertIn("message-scoped selected-text fallback", testing)
        self.assertIn("frontend/browser_extension", structure)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: failure because user docs do not mention the browser extension yet.

- [ ] **Step 3: Update `README.md`**

Add a short section:

```markdown
## Tencent Exmail browser extension prototype

Second-stage prototype files live in `frontend/browser_extension`.

Local use:

1. Start the backend with `start_local_service.cmd` or `python scripts/manage_local_service.py start`.
2. Open Chrome or Edge extension management.
3. Choose `Load unpacked`.
4. Select the `frontend/browser_extension` folder.
5. Open Tencent Exmail Web at `https://exmail.qq.com/`.
6. Open one email, then click the extension's `Analyze current email` button.

The extension calls only the local backend. It does not store API keys, connect to a mailbox account, scan the mailbox, or automatically send/delete/archive email.
```

- [ ] **Step 4: Update operations docs**

In `docs/operations/setup_checklist.md`, add:

```markdown
## Tencent Exmail extension setup

- Start the local backend before using the extension.
- Load `frontend/browser_extension` as an unpacked extension in Chrome or Edge.
- Use the extension only on `https://exmail.qq.com/*`.
- Keep the extension pointed at `http://127.0.0.1:8765`.
```

In `docs/operations/testing_checklist.md`, add:

```markdown
## Tencent Exmail extension checks

- Open one Tencent Exmail message and click `Analyze current email`.
- Verify one current-email payload is sent after the click.
- Verify message-scoped selected-text fallback works only for user-selected email content in the currently opened Tencent Exmail message.
- Verify local backend unavailable state is readable.
- Verify the extension does not send, delete, archive, move, or reply to mail.
```

In `docs/operations/project_structure.md`, add `frontend/browser_extension/` to the current structure and responsibilities:

```text
frontend/
  browser_extension/
    manifest.json
    popup.html
    popup.css
    popup.js
    content/
      exmail_adapter.js
    shared/
      api_client.js
      render_analysis.js
```

- [ ] **Step 5: Run targeted tests and verify they pass**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_static
```

Expected: `OK`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add README.md docs\operations\setup_checklist.md docs\operations\testing_checklist.md docs\operations\project_structure.md tests\test_browser_extension_static.py
git commit -m "docs: add Tencent Exmail extension usage"
```

## Task 8: Final Verification and Project Status

**Files:**
- Modify: `docs/operations/project_status_log.md`

- [ ] **Step 1: Regenerate project status**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\generate_project_status.py --output docs\operations\project_status_log.md
```

Expected: command exits 0 and `docs/operations/project_status_log.md` includes `frontend/browser_extension/` files in the key status inventory if the generator tracks them.

- [ ] **Step 2: Run all tests**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests
```

Expected: all tests pass.

- [ ] **Step 3: Run maintenance scan**

Run:

```powershell
C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\maintenance_scan.py
```

Expected:

```text
No cleanup findings detected.
```

- [ ] **Step 4: Run git diff checks**

Run:

```powershell
git diff --check
git status --short --branch
```

Expected: `git diff --check` exits 0. `git status` shows only intended modified files before commit.

- [ ] **Step 5: Commit final status update**

Run:

```powershell
git add docs\operations\project_status_log.md
git commit -m "docs: update project status for extension prototype"
```

- [ ] **Step 6: Manual verification note**

After automated verification, manually load the unpacked extension:

```text
Chrome/Edge -> Extensions -> Developer mode -> Load unpacked -> frontend/browser_extension
```

Then verify:

- The extension appears in the toolbar.
- The extension popup opens.
- On `https://exmail.qq.com/*`, clicking Analyze either extracts the opened email or shows message-scoped selected-text fallback guidance.
- With local backend stopped, the popup shows "Local analysis service unavailable".
- With local backend running, a message-scoped selected-text sample can be analyzed through the local backend.

Record any manual limitation in the final response if DOM extraction needs real opened-message selector refinement.

## Self-Review Notes

- Spec coverage: Tasks cover route documentation, Manifest V3 skeleton, Exmail host permissions, content adapter, message-scoped selected-text fallback, local backend call, result rendering, copy draft, safety boundaries, docs, and verification.
- Scope: This is one coherent prototype. It does not add OAuth, mailbox APIs, automated send/delete/archive actions, or OpenAI frontend calls.
- Type and naming consistency: The popup sends `EXTRACT_CURRENT_EMAIL`; the content adapter listens for `EXTRACT_CURRENT_EMAIL`; the backend payload uses `subject`, `from`, `to`, `sent_at`, `body_text`, and `user_confirmed`.
- Dependency check: No new Python or JavaScript package dependencies are introduced.
