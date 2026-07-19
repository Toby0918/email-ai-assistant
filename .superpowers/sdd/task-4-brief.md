### Task 4: Prepare request-local sanitized media and embedded office images

**Files:**
- Create: `backend/email_agent/multimodal_media.py`
- Create: `backend/email_agent/office_embedded_media.py`
- Modify: `backend/email_agent/attachment_storage.py`
- Modify: `backend/email_agent/analyzer.py`
- Modify: `backend/email_agent/analysis_model_routes.py`
- Modify: `backend/email_agent/api.py`
- Create: `tests/test_multimodal_media.py`
- Create: `tests/test_office_embedded_media.py`
- Modify: `tests/test_attachment_storage.py`
- Modify: `tests/test_attachment_parser.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- `PreparedMediaAsset` is frozen, `repr=False`, uses an opaque `source_id`, generic provider filename, fixed MIME, kind, detail, and a mutable byte buffer.
- Image sanitation decodes, verifies, applies orientation, flattens animation, strips metadata, bounds pixels/dimensions, and re-encodes without original metadata.
- PDF sanitation rejects encryption and excess pages, rewrites selected pages, and removes metadata, scripts, actions, forms, annotations, and embedded files.
- Office extraction accepts only bounded `word/media/` or `xl/media/` entries with safe names, image magic, per-entry and aggregate limits.
- `remove_stored_attachments` runs in API `finally` after success or failure.

- [ ] Write RED tests for MIME/magic mismatch, malformed files, pixel bombs, animation, EXIF removal, PDF active objects, encryption/page limits, zip traversal/bombs, embedded-image limits, opaque names, `repr`, and cleanup on all API exits.
- [ ] Implement the smallest pure media preparation modules using existing dependencies only.
- [ ] Associate each asset with an existing `attachment:N` evidence ID and add a generic untrusted-media text source when OCR/text is absent.
- [ ] Ensure no provider-ready Base64 or asset bytes enter a dataclass repr, exception, response, SQLite, or log.
- [ ] Run media/parser/API suites GREEN; commit `feat: sanitize request media for vision`.
