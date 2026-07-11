---
last_update: 2026-07-03
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Browser Extension Side Panel Task Brief

## Task

Change the Tencent Exmail browser extension entry from a transient action popup to a persistent Chrome / Edge side panel.

## Type

feature | fix | docs | test

## Goal

When the user clicks the extension icon, the Email AI Assistant should stay visible while the user clicks or scrolls inside Tencent Exmail. This avoids the browser action popup disappearing whenever focus moves back to the mailbox page.

## Non-Goals

- No automatic send, delete, archive, move, forward, or reply.
- No mailbox account integration.
- No background mailbox scanning.
- No automatic analysis without the user clicking `Analyze current email`.
- No frontend OpenAI, Ollama, Qwen, or local model calls.
- No API key, token, cookie, OAuth, or credential handling in the frontend.
- No storage of real email bodies in browser storage or docs.

## Background

Manual Tencent Exmail testing showed that the current action popup disappears after clicking elsewhere in the browser. Chrome / Edge action popups are transient by design. The persistent extension surface for this use case is the browser side panel.

## Scope

- `frontend/browser_extension/manifest.json`
- `frontend/browser_extension/background.js`
- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.css`
- `tests/test_browser_extension_manifest.py`
- `tests/test_browser_extension_static.py`
- `README.md`
- `docs/operations/setup_checklist.md`
- `docs/operations/testing_checklist.md`
- `docs/operations/project_status_log.md`

## Approach

1. Add failing manifest/static tests for side panel configuration.
2. Remove the transient `action.default_popup` entry.
3. Add `side_panel.default_path` pointing to the existing assistant UI.
4. Add a service worker that calls `chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })`.
5. Adjust popup CSS so the same UI fits a persistent side-panel viewport.
6. Update setup/testing docs to describe the persistent side panel behavior.
7. Regenerate the project status log and run verification.

## Data and API Changes

- Database changes: none.
- Backend API changes: none.
- AI JSON schema changes: none.
- Prompt changes: none.
- Browser extension manifest changes: add `sidePanel` permission, `side_panel.default_path`, and a background service worker.

## Security and Privacy Checks

- Current-email analysis remains user-clicked only.
- Email body remains untrusted input and is not executed.
- Frontend still calls only the local backend API.
- The side panel does not read mailbox data until the user clicks `Analyze current email`.
- No secrets or real email bodies are added to docs, tests, logs, or browser storage.
- Reply draft remains copy-only and user-reviewed.

## Acceptance Criteria

1. Clicking the extension icon opens a persistent side panel instead of a transient popup.
2. The side panel keeps the existing `Analyze current email` and `Copy draft` flow.
3. The UI remains usable in a side-panel viewport and still wraps long analysis output.
4. The manifest no longer declares `action.default_popup`.
5. The extension does not add any automatic mailbox actions.
6. Setup and testing docs mention the persistent side panel behavior.
7. Full tests and maintenance scan pass.

## Test Plan

- `python -m unittest tests.test_browser_extension_manifest tests.test_browser_extension_static`
- `python -m unittest discover -s tests`
- `python -B scripts/maintenance_scan.py`
- `node --check frontend\browser_extension\background.js`
- `node --check frontend\browser_extension\popup.js`

## Rollback

Revert the manifest side panel entries, `background.js`, side-panel CSS adjustments, docs, and tests from this task.
