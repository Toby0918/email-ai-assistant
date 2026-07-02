---
last_update: 2026-07-02
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Tencent Exmail Browser Extension Task Brief

## Task

Document and implement the second-stage Chrome / Edge browser extension route for Tencent Exmail.

## Goal

Let a user open one current email in Tencent Exmail, click an explicit analyze button, send only that current-email payload to the local Python backend, and review the returned summary, priority, category, risks, suggested actions, and reply draft.

## Target Surface

- Mail system: Tencent Exmail.
- Browser route: Chrome / Edge browser extension.
- Target URL pattern: `https://exmail.qq.com/*`.
- Backend route: `http://127.0.0.1:8765/api/analyze-current-email`.
- AI-facing surface: local Python analysis service only.

## In Scope

- Document the selected Tencent Exmail second-stage frontend route.
- Keep the extension scoped to the current opened email after a user click.
- Selected-text fallback may only use user-selected email content from the currently opened Tencent Exmail message.
- Preserve the local backend as the only AI-facing surface.
- Keep reply output as a user-reviewed draft.

## Out of Scope

- No automatic send.
- No mailbox account integration.
- No mailbox scanning.
- No browser storage of real email bodies.
- No automatic delete, archive, move, forward, or reply.
- No credential, token, cookie, OAuth, or password reading.
- No frontend OpenAI API calls or frontend API keys.

## Acceptance Criteria

- The route decision names Tencent Exmail and `https://exmail.qq.com/*`.
- Product docs identify the second-stage route as a Chrome / Edge browser extension.
- Safety boundaries explicitly preserve user-clicked current-email analysis only.
- Selected-text fallback remains message-scoped and is not arbitrary webpage analysis.
- The extension posts a current-email payload with `user_confirmed: true` to the local backend route.
- Popup output remains summary, priority, category, risks, suggested actions, and copyable reply draft.
- `python -m unittest discover -s tests` passes.
- `python scripts/maintenance_scan.py` reports no cleanup findings.
