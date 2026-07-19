---
last_update: 2026-07-18
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# Current Message Attachment Acquisition Design

## Goal

Make a user-clicked analysis actually parse supported attachments from the currently opened Tencent Exmail message. Use strict automatic in-memory acquisition first and an explicit local-file picker fallback second, while preserving current-message scope, no browser persistence, no automatic system download, and request-finally backend deletion.

## Content-free live evidence

The authorized structural probe found one visible attachment control in the verified message frame. It is a same-origin HTTPS anchor to exact `/cgi-bin/download` with a non-empty query and a `target`; it is outside `#mailContentContainer.qmbox` and in the same trusted parent region as `.readmailinfo`. It has no `download` attribute. No filename, query, message text, identity, or byte content was inspected or output.

Both `exmail_adapter.hasPositiveAttachmentControlEvidence` and `current_message_collector.hasPositiveAttachmentControlEvidence` currently require a non-empty `download` attribute. This is the confirmed reason the real control is discarded before fetch.

### 2026-07-18 automatic-acquisition diagnostic amendment

The separately authorized content-free diagnostic found a second legacy host
shape. The verified message body has one additional intermediate wrapper, so
the attachment region is the body root's grandparent rather than its direct
parent. The exact Tencent download endpoint is rendered with a non-zero layout
but is below the current viewport, and its anchor exposes no supported filename
or MIME evidence. The implementation therefore stops before fetch at three
independent gates: resource-container depth, viewport intersection, and
pre-fetch type evidence.

The operator approved a bounded repair for this exact shape. Automatic
acquisition may use a verified resource container that is either the existing
direct-parent shape or one legacy intermediate-wrapper shape, provided the
chosen container is still a direct child of the verified document body, the
known message body root is unique, and the current context is revalidated
before and after fetch. The collector must never promote `document.body`, an
arbitrary ancestor, quoted history, or the authored message body into the
attachment-control scope.

For verified attachment anchors only, rendered visibility means a non-zero,
finite layout with no hidden or stylesheet-hidden ancestor. Viewport
intersection is not required. The extension does not scroll, click, or
navigate. Inline body images retain the existing viewport-intersection rule.

An exact legacy `/cgi-bin/download` anchor with a non-empty query and target
may defer type resolution until after its one bounded same-origin fetch when
its own supported type metadata is absent. Conflicting or unsupported anchor
metadata still rejects before fetch. After the bounded stream is read, an
allowlisted response Content-Type and content signature must agree. PDF and
supported raster images can be identified from exact signatures with an
absent or generic binary Content-Type. DOCX/XLSX additionally require exact
Office response MIME or a strict response Content-Disposition suffix plus a
ZIP signature. Raw response filenames are not exposed: a type-derived generic
filename is used when the DOM supplied no safe filename. Unknown, HTML,
type-conflicting, truncated, or signature-mismatched responses yield a fixed
limitation and no attachment payload.

## Option A: strict automatic in-memory fetch

Keep every existing gate:

- explicit Analyze click;
- one verified visible same-origin Tencent message context;
- control inside the verified message container but outside the current body root and known quoted history;
- visible layout and no signature/profile/contact hint;
- HTTPS, no userinfo, exact `https://exmail.qq.com`, exact approved path, and non-empty query;
- supported type from visible metadata/text, never from URL query;
- or, only for the verified untyped legacy download control, supported type
  from compatible response headers and file signature after bounded fetch;
- context and resource identity revalidation before and after fetch;
- `credentials: "include"`, `redirect: "error"`, bounded streaming, abort deadline;
- 20 candidates, 5 files, 10 MiB each, 25 MiB total, and 20 seconds.

Add one legacy positive-evidence alternative when `download` is absent:

```text
tag is A
AND target is non-empty
AND resolved origin is exact Tencent origin
AND resolved pathname is exact /cgi-bin/download
AND query is non-empty
AND visible metadata/text yields a supported type
AND negative signature/profile/contact checks remain clear
```

`/cgi-bin/viewfile` without `download` does not qualify. The extension never clicks the anchor and never derives a filename from its query. Bytes stay in memory, become the existing bounded Base64 request field, and are not written by the browser.

## Option C: explicit local-file picker fallback

Add a default-collapsed picker labeled as a fallback for current-message attachments. The operator must explicitly select files they assert belong to the currently opened email. The product cannot cryptographically prove that local origin, and the UI states this limitation.

Selection alone does not read bytes. `File` references are read only after Analyze, after current-message extraction and fingerprint capture. Supported image/PDF/XLSX/DOCX files share the same 5-file, 10 MiB, and 25 MiB aggregate policy with automatic resources. Manual items are deduplicated against automatic items by safe filename, normalized type, and size, without paths, `webkitRelativePath`, URLs, tokens, timestamps, or `File` objects entering the payload.

The message fingerprint is revalidated after manual reads and before the backend call. A stale message results in zero backend calls. On every success, error, stale result, or cancellation path, the input value and local references are cleared. JavaScript immutable copies cannot be guaranteed wiped; documentation makes no secure-memory claim.

No `downloads` permission, `chrome.downloads`, File System Access API, `chrome.storage`, Web Storage, or IndexedDB is added.

## Backend lifecycle

No new storage layer is needed. The existing API writes accepted bytes into uniquely named, contained, create-exclusive request temporary files and removes the current batch in `finally` on success and failure. Prepared mutable media buffers are overwritten on exit. The 24-hour mtime cleanup remains crash-recovery on a later request or service start; it is not a scheduler and is not the normal retention period.

## Result truthfulness

An attachment result exists for limitations as well as successful parsing. Therefore only `attachment_insights[].status == "parsed"` proves content was read. UI and tests must not infer success from array length. A local aggregate may say how many are parsed, metadata-only, unavailable, or failed without adding a public API field.

## Failure behavior

- Automatic acquisition failure keeps safe body analysis and reports a fixed limitation.
- The picker remains optional; failure never forces the operator to expose a local file.
- Unsupported type, excess bytes/count, stale context, read error, redirect, or endpoint mismatch yields a fixed limitation without raw exception details.
- Provider failure still triggers backend cleanup and safe fallback.

## Acceptance

- The recreated legacy control is fetched exactly once without `download`.
- All negative controls remain rejected.
- The picker reads only on Analyze and is always cleared.
- No permissions or persistence expand.
- A vertical synthetic test reaches `status == "parsed"` and request temp storage is empty afterward.
- The bounded two-wrapper legacy shape is accepted without scanning the
  document body or arbitrary ancestors.
- A rendered off-viewport attachment control is eligible without scrolling,
  clicking, or navigation; hidden, zero-layout, and off-viewport inline images
  remain rejected.
- An untyped legacy control is fetched at most once and produces payload bytes
  only after compatible response-header and signature validation.
