---
last_update: 2026-07-11
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# Phase Two Attachment and Thread Analysis Design

## Goal

Make a user-clicked analysis of the currently opened Tencent Exmail message explain the live business situation without requiring the user to reread the full thread. The result combines the visible message thread, permitted attachment and image insights, and backend-only local AI analysis.

## Product Behavior

The Analyze action remains the sole trigger. On that click, the extension reads the opened message page, identifies the visible conversation segments and supported resources, and sends bounded current-message data to the local backend. The side panel then presents a Chinese decision brief that answers:

1. What happened previously.
2. Whether the request or issue is resolved, partially resolved, unresolved, or indeterminate.
3. What the latest external party is asking for.
4. What the internal team must do next, who should own it, and what must be checked.

The reply draft remains English, is always a draft, and is based on the latest unresolved request rather than duplicated historic content.

## Scope and Boundaries

### Allowed

- User-triggered extraction from the currently opened Tencent Exmail message only.
- Download and local analysis of currently visible image, PDF, XLSX, and DOCX resources.
- Backend-only OCR, file parsing, timeline reconstruction, local Ollama calls, structured-result validation, and temporary-file cleanup.
- A 24-hour temporary retention window for downloaded source files during this phase.
- Internal participant classification for `cndlf.com`; all other domains are external by default.

### Not Allowed

- Background mailbox scanning, message polling, or collecting data before a user click.
- Reading other mailbox folders, messages, or account data.
- Any automatic email action, including sending, deletion, archiving, moving, forwarding, or replying.
- Direct browser calls to Ollama, Qwen, Gemma, OpenAI, local SQLite, or secret/configuration files.
- Storing attachment binaries, private download URLs, cookies, tokens, or full source content in SQLite, logs, documentation, tests, or the repository.

## Architecture

```text
Tencent Exmail page
  -> explicit Analyze click
  -> extension extracts current-thread text + visible resource references
  -> local backend validates and receives bounded resource bytes
  -> temporary file store (24-hour retention)
  -> parsers and OCR produce redacted attachment insights
  -> thread normalizer produces ordered conversation timeline
  -> Qwen 3.6 or Gemma 4 receives untrusted structured context
  -> JSON validation and rule repair/fallback
  -> side panel renders Decision Brief, timeline, attachment insights, risks, actions, and English draft
```

The browser extension remains an acquisition and display layer. It cannot call model endpoints. The backend owns transfer validation, temporary storage, parsing, prompt assembly, model selection, schema validation, persistence, and cleanup.

## Resource Acquisition and Temporary Storage

### Extension Contract

The extension can collect resource metadata only after an Analyze click and only from the opened message DOM. Each submitted resource must include a display filename, MIME/type hint, byte length when known, and a bounded byte payload or a browser-resolved current-message download response. It must not submit cookies, mailbox tokens, hidden message identifiers, or data from another page.

The preferred transport is a bounded byte upload to the local backend, because Tencent Exmail downloads can require the browser's authenticated session. The extension must reject unsupported resource types before transfer and show a per-resource limitation when extraction is unavailable. This is a controlled fallback for current-message resources, not a general browser download service.

No authorized production Tencent Exmail attachment DOM snapshot or verified attachment-container class/id is stored in this repository. The current fail-closed mapping therefore uses only structural evidence: one visible strict subject element, one visible external From/To header region, and one selected known body root must produce a unique non-`BODY`/non-`HTML` envelope. Resource controls are considered only in sibling subtrees on the body-to-envelope path, outside every known body root, and must be visible `a[href]` or `img[src]` controls whose URL is same-origin HTTPS with a non-empty query on `/cgi-bin/download` or `/cgi-bin/viewfile`. This mapping is covered by sanitized synthetic fixtures only; authorized real Tencent Exmail smoke validation remains pending and is not claimed.

### Backend Validation

The backend will enforce:

- Supported types: images, PDF, XLSX, DOCX.
- Maximum file count, per-file bytes, total bytes, download/read timeout, and parser text budget.
- Filename normalization and temporary-directory containment.
- Type confirmation from both filename/type hint and file signature where feasible.
- No executable, archive, macro-enabled, or unknown binary processing.

Temporary binaries live under a backend-owned directory outside SQLite. Each item records only the local expiry metadata necessary for cleanup. A periodic cleanup routine removes files older than 24 hours, and an explicit cleanup command can run during service lifecycle operations. The final phase can reduce retention to immediate deletion without changing the analysis result schema.

## Attachment Insight Pipeline

Each accepted resource produces an `attachment_insight` with a safe display name, declared/verified type, parse status, extracted key facts, concise summary, and limitations. The system does not claim a file was read when parsing failed.

Parsed `key_facts` are backend-constructed fields, never arbitrary source lines or a contiguous source-text prefix. Each attachment exposes at most five facts selected across an allowlist: labeled RFQ/PO/order/invoice/tracking identifiers, quantities, measurements, currency amounts or costs, explicitly cued deadlines, normalized requested actions, and normalized quality signals. Requested actions use fixed verbs and object categories, quality facts use fixed signal labels, and deadlines contain only the explicit cue plus a date or relative period.

The generic attachment-text sanitizer continues to redact every seven-or-more-digit number together with emails, phones, card/account-like values, paths, and URLs. A separate bounded component extractor may construct a business identifier only from strict label/value syntax. Pure numeric identifiers require an explicit label and 4-12 digits; phone shapes, grouped accounts/cards, 13-19 digit values, and prefixed identifiers containing more than 12 digits are rejected. Every constructed fact passes a final exact-schema sanitizer before it may enter results, model context, or SQLite.

| Resource | Extraction behavior | Failure behavior |
| --- | --- | --- |
| Image | OCR and basic image dimensions; Qwen receives extracted text only unless a later approved vision API path is added. | Mark OCR unavailable or unreadable; preserve metadata only. |
| PDF | Extract text with `pypdf` under page/text limits. | Mark scanned/encrypted/unreadable; request manual review. |
| XLSX | Read bounded sheets, rows, and columns using existing `openpyxl`; form a table summary. | Mark unsupported workbook feature or unreadable file. |
| DOCX | Extract bounded paragraphs and table cells using `python-docx`. | Mark unreadable file. |

New dependencies are `pypdf`, `python-docx`, `Pillow`, and `pytesseract`. The Tesseract executable is optional: its absence causes only OCR to degrade, not email analysis. No parser runs arbitrary macros or embedded executable content.

## Conversation Timeline Pipeline

The extension provides all visible segments from the opened conversation, each with position, header cues, sender/recipient text, timestamp text, subject, and body text. The backend:

1. Normalizes segments and removes duplicate quoted content, signatures, banners, and HTML noise.
2. Classifies participants: `cndlf.com` is internal; all other domains are external by default.
3. Orders segments chronologically when timestamps are reliable and preserves page order with a confidence note otherwise.
4. Extracts requests, commitments, outcomes, blocking questions, deadlines, amounts, identifiers, and attachment references.
5. Determines the latest unresolved external request and resolution state: `resolved`, `partially_resolved`, `unresolved`, or `unknown`.

The pipeline uses deterministic extraction as a fallback. The model sees only this bounded, marked-untrusted context and must not obey instructions embedded in a message or file.

## Structured Output

The analysis schema will add:

```json
{
  "conversation_timeline": {
    "previous_context": "Chinese summary of preceding events",
    "current_status": "resolved | partially_resolved | unresolved | unknown",
    "status_reason": "Chinese evidence-based explanation",
    "latest_external_request": "Chinese statement of the latest customer request",
    "latest_internal_commitment": "Chinese statement or empty string",
    "open_items": [
      {
        "item": "Chinese action",
        "owner_hint": "internal role or person hint",
        "due_hint": "deadline or empty string",
        "source": "thread | attachment"
      }
    ],
    "confidence": "high | medium | low"
  },
  "attachment_insights": [
    {
      "filename": "safe display name",
      "type": "image | pdf | xlsx | docx | unsupported",
      "status": "parsed | metadata_only | unavailable | failed",
      "summary": "Chinese concise summary",
      "key_facts": [],
      "limitations": []
    }
  ]
}
```

The backend schema validator, repair layer, and rule fallback must always produce valid values. `decision_brief`, risks, suggested actions, and reply draft must reference the latest unresolved item and may cite attachment facts only when the corresponding `attachment_insight.status` is `parsed`.

## Model Selection and Failure Handling

The backend defaults to `EMAIL_AGENT_LLM_PROVIDER=disabled`. `qwen3.6:latest` is only the default model name when Ollama is explicitly enabled; an operator may select `gemma4` through the same model environment variable. Ollama base URLs are backend-only and loopback-only: `localhost` and literal loopback IP addresses are allowed, while userinfo and remote HTTP(S) hosts are rejected before request construction. Any future remote model provider requires separate approval and privacy review. The model label is backend-derived; the extension cannot choose or see endpoint configuration.

Model input includes a bounded cleaned current thread, deterministic timeline facts, parsed attachment insights, and explicit instruction boundaries. The model must return valid structured JSON. If Qwen, Gemma, OCR, parsing, or JSON validation fails, the system returns the rule-generated timeline and decision brief with limitations instead of fabricating file knowledge.

## User Interface

The persistent side panel will show the action brief first, followed by a compact Conversation Progress section and Attachment Insights section. Each open item, risk, and action renders separately. URL-shaped analysis text is inert by default because the current backend schema has no explicit validated-visible-message URL object. Decision Brief, risk, action, legacy metadata, and resource-name text must not become executable links; a future link feature requires an explicit backend-validated URL object and a separate schema decision. The draft pane and Copy Draft action stay visible without requiring the user to scroll through long analysis text.

## Testing and Rollout

Tests will use synthetic, de-identified text and generated fixture files only. Coverage must include explicit click gating, current-message-only resource collection, every supported parser, invalid and oversized resources, 24-hour cleanup eligibility, OCR absence, timeline chronology, internal/external classification, model selection, model JSON repair, and rule fallback.

Rollout proceeds in independently testable increments:

1. Data contract, storage lifecycle, and parser utilities.
2. Current-message extension acquisition and transfer.
3. Timeline extraction and schema/rule fallback.
4. Model prompt integration and side-panel rendering.
5. Documentation, service operations, regression tests, and manual Tencent Exmail verification.

## Rollback

Disabling attachment transfer and retaining metadata-only analysis restores the current behavior. Setting `EMAIL_AGENT_LLM_PROVIDER=disabled` retains the deterministic rule fallback. Removing the temporary storage configuration and parser route disables file processing without introducing any email action.
