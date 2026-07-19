### Task 7: Complete side-panel disclosure, status, and readable diagnostics

**Status:** approved / in progress

**Files:**
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/browser_extension/popup.js`
- Modify: `frontend/browser_extension/shared/render_analysis.js`
- Modify: `frontend/browser_extension/shared/analysis_components.css`
- Modify: `frontend/local_debug_page/index.html`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_browser_extension_task_focused_ui.py`
- Modify: `tests/test_frontend_local_debug.py`

**Goal:**
- Show the exact approved persistent remote-processing disclosure before every
  Analyze click in both frontend surfaces.
- Keep the 320-pixel first screen task-focused while clearly reporting the
  accepted engine and one fixed, content-free fallback reason.
- Explain during loading that selected images/files are being analyzed and the
  operation can take up to 60 seconds.

**Non-goals:**
- No public response, SQLite, prompt, provider-routing, mailbox, attachment
  collection, or timeout-contract changes.
- No live provider, browser mailbox, real email, real media, credential, or
  `.env` access.
- No automatic send, navigation, mailbox scan, or background analysis.

**Interfaces and safety boundaries:**
- The persistent disclosure is byte-for-byte identical in the extension and
  local debug page and matches task-brief section 15.
- First-screen content remains conclusion, current request, next step, key
  facts, and must-check items.
- Technical details show only the public engine label and a fixed reason from
  an allowlist. Raw provider errors, prompts, source IDs, paths, response
  payloads, attachment bytes, keys, and private diagnostics are never rendered.
- History, attachments, risk basis, and technical details remain collapsed by
  default. The external reply draft remains visibly human-review-only.
- Provider labels are `OpenAI GPT-5.6 Sol`, `DeepSeek text fallback`, and
  `Rule fallback`; rule/provider fallback states must not look like successful
  OpenAI output.

**Acceptance:**
- Add RED tests for the exact disclosure in both surfaces, the 60-second
  loading copy, engine labels, fixed fallback reasons, raw-detail rejection,
  collapsed secondary sections, and 320-pixel task-card ordering.
- Implement the smallest markup/rendering/CSS changes without changing public
  analysis fields.
- Run focused frontend tests, browser-extension static tests, `node --check`
  for every changed JavaScript file, mechanical/static guards, and
  `git diff --check`.
- Commit the implementation only after fresh independent review is clean.

**Rollback:** revert the Task 7 UI/test commit. Backend routes, schemas, and
stored analyses require no migration.

**Human confirmation:** none required before offline implementation. Live
provider and real mailbox testing remain prohibited until Task 8 passes and the
operator resumes the separately authorized smoke phase.
