---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: design_spec
---

# Tencent Exmail Browser Extension Prototype Design

## Goal

Build the second-phase browser-extension prototype for Tencent Exmail Web at `https://exmail.qq.com/*`.
The extension should let the user open one email, click an explicit analysis button, send only that current email payload to the local Python backend, and display the existing structured analysis result and reply draft.

## User Context

The target mailbox shown by the user is Tencent Enterprise Email in a Chromium-based browser.
The visible URL is `https://exmail.qq.com/cgi-bin/frame_html...`, and the page uses a classic webmail layout with folders on the left, a message list, and message-reading pages behind Tencent Exmail frames.

This confirms that the second-phase route should be a Chrome / Edge browser extension specialized for Tencent Exmail, not Outlook Add-in or Google Workspace Add-on.

## Scope

The prototype includes:

- A Manifest V3 browser extension under `frontend/browser_extension/`.
- Host permissions limited to Tencent Exmail and the local backend.
- A popup or compact panel with an "Analyze current email" action.
- A Tencent Exmail content adapter that extracts the currently open email from the active tab after the user clicks the action.
- A selection fallback that analyzes the selected page text when DOM extraction is not available.
- A call to `http://127.0.0.1:8765/api/analyze-current-email` using the existing backend API contract.
- Result rendering for summary, priority, category, risk flags, suggested actions, and reply draft.
- Copy-to-clipboard support for the reply draft.

## Non-Goals

The prototype does not:

- Connect to a mailbox account through OAuth, password, cookie export, or Tencent APIs.
- Read mailbox credentials, tokens, or hidden account data.
- Scan the inbox, unread messages, folders, or all messages.
- Analyze emails without an explicit user click.
- Send, delete, archive, move, mark, forward, or reply to email automatically.
- Store OpenAI API keys, call OpenAI directly, or read `.env` from the frontend.
- Save real email bodies to the browser storage.
- Commit real customer, supplier, employee, or mailbox data to docs, tests, logs, or fixtures.

## Approaches Considered

### Approach A: Tencent Exmail adapter plus selected-text fallback

This is the chosen approach.
The extension is intentionally narrow: it runs only on Tencent Exmail, tries to extract the open email with a dedicated adapter, and falls back to selected text when the Exmail DOM is not stable enough.

Benefits:

- Fits the user's actual mailbox.
- Keeps the first prototype useful even if Tencent changes DOM details.
- Avoids account integration and keeps the existing safety boundary intact.
- Reuses the current local backend and result schema.

Trade-offs:

- The DOM adapter may need adjustment after observing the real opened-message page.
- The selected-text fallback may produce less complete metadata than DOM extraction.

### Approach B: Selection-only generic extension

This would analyze only selected text on any web page.
It is safer and faster, but it does not meet the product goal of recognizing the current email fields from the mailbox UI.

### Approach C: Outlook or Gmail extension route

This does not fit the user's current environment.
It should remain out of scope unless the target mailbox changes.

## Architecture

The extension should be split into small files with clear responsibilities:

```text
frontend/browser_extension/
  manifest.json
  popup.html
  popup.js
  popup.css
  content/
    exmail_adapter.js
  shared/
    api_client.js
    render_analysis.js
```

`manifest.json` declares Manifest V3 metadata, the popup entry, and minimum host permissions:

```text
https://exmail.qq.com/*
http://127.0.0.1:8765/*
```

The popup owns user interaction:

- Show backend status.
- Ask the active Exmail tab for the current email payload only after a user click.
- Submit the payload with `user_confirmed: true`.
- Render the backend response.
- Copy the reply draft on explicit click.

The content adapter owns page extraction:

- Detect whether the current tab is Tencent Exmail.
- Traverse same-origin Tencent Exmail frames when accessible.
- Extract subject, sender, recipients, sent time, and body from the currently opened email view.
- If no opened email is detected, return a structured extraction error.
- If selected text exists, return a fallback payload with the selected text as body and visible page title as subject.

The shared API client owns local backend calls:

- POST to `/api/analyze-current-email`.
- Handle unavailable local service and non-OK backend responses.
- Never call OpenAI or any remote AI endpoint.

The result renderer owns display formatting:

- Render priority, summary, category, risk flags, suggested actions, and reply draft.
- Avoid logging email body text to the console.

## Data Flow

```text
User opens one email in Tencent Exmail
-> User clicks extension Analyze
-> Popup asks content adapter for current email payload
-> Content adapter extracts current email or selected-text fallback
-> Popup sends payload to local Python backend with user_confirmed=true
-> Backend cleans, analyzes, validates JSON, and saves local SQLite debug record
-> Popup displays structured analysis and reply draft
-> User manually reviews and may copy the draft
```

## Extraction Strategy

The first implementation should prioritize robustness over cleverness:

- Only run extraction in response to a popup message triggered by the user's click.
- Look for the most likely opened-message document in the top page and same-origin frames.
- Prefer semantic field labels and stable visible text over brittle absolute CSS paths.
- Treat subject, sender, recipients, and sent time as optional when the page does not expose them clearly.
- Require non-empty body text before analysis.
- If the body is empty but selected text is present, use selected text as fallback body.
- If neither opened-message body nor selected text exists, show a user-facing "open or select an email first" error.

## Error Handling

Expected user-facing states:

- Local backend unavailable.
- Current tab is not Tencent Exmail.
- No opened email detected.
- Email body is empty.
- Backend rejected the request.
- Analysis failed.
- Copy failed.

Errors should be short and actionable.
They must not include raw stack traces, credentials, cookies, full email bodies, or hidden page data.

## Security Boundaries

The extension must preserve the project safety rules:

- Frontend to backend only; no frontend to OpenAI.
- No API key, mailbox password, OAuth token, cookie export, or `.env` access in frontend files.
- No automated mailbox scanning.
- No automated email send, delete, archive, move, forward, or reply actions.
- No browser storage of real email bodies.
- No console logging of email bodies.
- No real email content in tests or docs.

## Testing Plan

Automated tests should remain Python `unittest` based and avoid new dependencies for this prototype.
They should verify:

- Browser extension files exist under `frontend/browser_extension/`.
- The manifest is Manifest V3 and only grants the intended host permissions.
- Frontend files do not contain OpenAI direct-call markers, `.env` access, API key markers, or high-risk mailbox action markers.
- Popup code calls the local backend endpoint and sends `user_confirmed: true`.
- The content adapter exposes extraction and fallback behavior with synthetic, non-real fixture snippets or static contract checks.
- Documentation and ADR updates exist for the Tencent Exmail route.

Manual verification should cover:

- Loading the unpacked extension in Chrome or Edge.
- Opening Tencent Exmail Web at `exmail.qq.com`.
- Running analysis on one opened email.
- Running analysis with selected text fallback.
- Handling local backend unavailable.

## Acceptance Criteria

The second-phase prototype is complete when:

- A user can load the extension unpacked in Chrome or Edge.
- The extension is limited to Tencent Exmail and the local backend.
- Clicking Analyze on an opened Exmail message submits exactly one current email payload to the backend.
- If DOM extraction fails, selected-text fallback can still analyze manually selected email content.
- The popup displays the existing backend analysis fields and a copyable reply draft.
- Automated tests and maintenance scan pass.
- Updated docs explain that the chosen second-phase frontend route is Tencent Exmail browser extension.

## Open Risks

- Tencent Exmail's frame and DOM structure may differ between inbox list and message view.
- Browser extension access to some frames may be constrained by browser security rules.
- The first DOM adapter may need refinement after inspecting an opened message page rather than only the inbox list.
- Selected-text fallback reduces metadata quality, so analysis may be less precise when fallback is used.

These risks are acceptable for the prototype because the fallback keeps the workflow usable without crossing mailbox-account integration boundaries.
