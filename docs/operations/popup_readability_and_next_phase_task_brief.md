---
last_update: 2026-07-03
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Popup Readability and Next Phase Task Brief

## Task

Improve the Tencent Exmail extension popup readability for long analysis output and record the recommended next-phase development route.

## Type

fix | docs | test

## Goal

Make long RFQ-style analysis results readable in the popup by rendering risks, actions, and attachments as structured blocks instead of compressed comma-separated text. Keep the copy-draft control visible beside the draft area. Record the next-phase route in the product roadmap so future work follows a stable sequence.

## Non-Goals

- No automatic send, delete, archive, move, forward, or reply.
- No mailbox account integration.
- No background mailbox scanning.
- No frontend OpenAI, Ollama, Qwen, or local model calls.
- No API key, token, cookie, or credential handling in the frontend.
- No storage of real email bodies in browser storage or docs.

## Background

Manual Tencent Exmail testing showed that long RFQ numbers, URLs, attachment names, risk evidence, and action descriptions are hard to read when displayed as one-line comma-separated text in the extension popup. A follow-up manual test also showed that long analysis content can hide the copy-draft button, and URL text inside risks/actions needs to be clickable.

## Scope

- `frontend/browser_extension/popup.html`
- `frontend/browser_extension/popup.css`
- `frontend/browser_extension/popup.js`
- `frontend/browser_extension/shared/render_analysis.js`
- `tests/test_browser_extension_renderer_behavior.py`
- `tests/test_browser_extension_static.py`
- `docs/product/roadmap.md`
- `docs/operations/project_status_log.md`

## Approach

1. Add failing renderer and static tests for structured long-output rendering.
2. Render risks, suggested actions, and attachments as list-style blocks.
3. Render risk/action object fields as separate labeled lines, including evidence, recommendation, description, owner hint, and due hint when present.
4. Linkify URLs in risk/action list content with safe anchor attributes.
5. Update popup CSS for fixed readable dimensions, scrollable result content, visible copy control, and long-token wrapping.
6. Record the next-phase route in the roadmap.
7. Regenerate the project status log and run full verification.

## Data and API Changes

- Database changes: none.
- API changes: none.
- AI JSON schema changes: none.
- Prompt changes: none.

## Security and Privacy Checks

- Current-email analysis remains user-clicked only.
- Email body remains untrusted input and is not executed.
- Frontend still calls only the local backend API.
- No secrets or real email bodies are added to docs, tests, logs, or browser storage.
- Reply draft remains copy-only and user-reviewed.

## Acceptance Criteria

1. Risks, actions, and attachments render as separate list items.
2. Long URLs, RFQ numbers, and mixed Chinese/English text wrap within the popup.
3. The draft area and result area remain readable without hiding the copy button.
4. The copy-draft button stays in the draft section and remains reachable after long analysis output.
5. Risks and actions render object details as labeled lines instead of compressed paragraphs.
6. URLs in risk/action content are clickable and use `target="_blank"` with `rel="noopener noreferrer"`.
7. The roadmap includes the recommended next-phase route.
8. Full tests and maintenance scan pass.

## Test Plan

- `python -m unittest tests.test_browser_extension_renderer_behavior tests.test_browser_extension_static`
- `python -m unittest discover -s tests`
- `python -B scripts/maintenance_scan.py`
- `node --check frontend\browser_extension\shared\render_analysis.js`
- `node --check frontend\browser_extension\popup.js`

## Rollback

Revert the popup renderer, popup markup/CSS, roadmap update, and tests from this task.
