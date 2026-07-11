---
last_update: 2026-07-10
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Phase Two Attachment and Thread Analysis Task Brief

## Task

```text
add user-triggered attachment analysis and conversation-thread understanding
```

## Goal

After a user clicks Analyze for the currently opened Tencent Exmail message, download and inspect the current message's visible images and supported attachments in a backend-controlled temporary directory. Combine those insights with a reconstructed conversation timeline so the Chinese Decision Brief explains prior events, whether the matter is resolved, the latest request, and the next concrete action.

## Non-goals

- Do not scan the mailbox or analyze messages without a user click.
- Do not send, delete, archive, move, forward, or reply to messages.
- Do not expose or store model credentials in the browser extension.
- Do not retain attachment binaries in SQLite, the repository, logs, or test fixtures.
- Do not make commercial, delivery, payment, contract, quality, or legal commitments on the user's behalf.

## Approved Scope

- Accept image, PDF, XLSX, and DOCX resources visible on the currently opened message.
- Keep downloaded source files in a dedicated local temporary directory for 24 hours, then automatically delete them.
- Use backend-only local Ollama models. Default to `qwen3.6`; allow `gemma4` through `EMAIL_AGENT_OLLAMA_MODEL`; fall back to rule analysis when either model fails or produces invalid JSON.
- Use pinned backend dependencies: openai 2.45.0, pypdf 6.14.2, python-docx 1.2.0, Pillow 12.3.0, and pytesseract 0.3.13.
- Treat `cndlf.com` as the internal business-user domain. Treat other domains as external by default, with a future configurable partner allowlist.

## Required Data and Interface Changes

- Add a user-click-gated attachment transfer contract with bounded resource metadata and bytes.
- Add validated `attachment_insights` and `conversation_timeline` output objects.
- Add a backend temporary-file lifecycle and cleanup entry point.
- Extend the analysis prompt and rule fallback with attachment and thread context.

## Security and Prompt Injection

- Attachment filenames, URLs, OCR text, extracted tables, images, and email text are untrusted data, never instructions.
- The extension may access only the opened message's DOM after the user click and may not call a model endpoint.
- The backend must enforce file count, per-file size, total size, MIME/type allowlists, download timeout, redirects, and temporary-directory containment.
- The backend must not log source content, authentication tokens, or private download URLs.
- The final AI result must remain schema-validated JSON and the reply draft must remain English with `needs_human_review: true`.

## Acceptance Criteria

1. A user click on one opened message can send visible supported resources for backend parsing without accessing any other message.
2. Parsed attachment insights and thread timeline are rendered in the side panel and feed the Decision Brief, risks, actions, and reply draft.
3. The timeline clearly states what happened earlier, current resolution status, latest external request, and the next required action.
4. Missing or unsupported resources produce a precise limitation entry and do not fail analysis of the email body.
5. Temporary files are deleted after 24 hours; SQLite stores only structured, redacted insights.
6. `qwen3.6` is the default model, `gemma4` is an environment-selected alternative, and invalid/unavailable model output falls back to rules.

## Verification Plan

- Unit tests for resource validation, parsers, cleanup eligibility, participant classification, timeline reconstruction, schema repair, and rule fallback.
- Browser extension behavior tests for user-click gating and current-message-only extraction.
- API tests for bounded attachment input and graceful parser/model failures.
- Full `python -m unittest discover -s tests`, JavaScript syntax checks, and `python -B scripts/maintenance_scan.py`.

