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
