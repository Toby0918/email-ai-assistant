# Task 4 Implementation Report

Status: ROOT REVIEW FIXES DONE - RE-REVIEW PENDING
Date: 2026-07-16
Worktree: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.worktrees\multimodal-plan-c`
Branch: `codex/multimodal-plan-c`

## Summary

Task 4 now prepares request-local, provider-neutral media without changing the
public API or SQLite schema and without making a provider call.

- `PreparedMediaAsset` is frozen, slot-backed, `repr=False`, contract-checked,
  uses only opaque source IDs and provider filenames, and owns a mutable
  `bytearray` with explicit best-effort overwrite and release.
- Images require matching filename MIME, magic, and Pillow format; source
  dimensions, pixels, and frames are bounded; EXIF orientation is applied;
  animation is flattened; and a fresh metadata-free PNG is re-audited.
- PDFs require valid PDF magic, reject encryption and more than five pages,
  copy pages into a fresh writer without active page surfaces, remove
  annotations and metadata, and re-audit the resulting object graph for
  scripts, actions, forms, annotations, embedded files, and active types.
- DOCX/XLSX extraction validates every ZIP entry before reading media. It
  rejects traversal, malformed/duplicate/control names, encryption, symlinks,
  unsupported compression, oversized or high-ratio entries, missing canonical
  OOXML roots, and media count/byte overflow. Only direct `word/media/` or
  `xl/media/` image entries are decoded and sanitized.
- Every accepted asset keeps its existing parent `attachment:N` evidence ID.
  A fixed `UNTRUSTED_MEDIA` evidence marker is added only when that source has
  no local text/OCR candidate.
- The analyzer carries only the provider-neutral tuple during routing and
  wipes all prepared buffers in `finally`. The API holds an immutable cleanup
  snapshot and removes current-request temporary files in `finally` on normal,
  known-error, and unexpected-error exits. A post-storage budget expiry also
  removes the batch before it can be dropped from the analyzer payload.

## Fixed limits

- Source image: 25,000,000 pixels, 16,384 pixels on either side, 32 frames.
- Sanitized image: 2,048 pixels on either side and 10 MiB per output asset.
- PDF: 5 pages, 10 MiB input, 10 MiB sanitized output.
- Office package: 256 entries, 10 MiB per entry, 25 MiB aggregate uncompressed,
  100:1 maximum declared compression ratio, and 240 UTF-8 bytes per entry name.
- Office embedded media: 8 images, 5 MiB per source entry, 10 MiB aggregate.
- Request media: 12 assets and 20 MiB aggregate sanitized bytes.

## Files in scope

Implementation:

- `backend/email_agent/multimodal_media.py`
- `backend/email_agent/image_media_safety.py`
- `backend/email_agent/pdf_media_safety.py`
- `backend/email_agent/office_embedded_media.py`
- `backend/email_agent/attachment_media_context.py`
- `backend/email_agent/attachment_storage.py`
- `backend/email_agent/attachment_safety.py`
- `backend/email_agent/attachment_parser.py`
- `backend/email_agent/analyzer.py`
- `backend/email_agent/analysis_model_routes.py`
- `backend/email_agent/api.py`

Tests:

- `tests/test_multimodal_media.py`
- `tests/test_office_embedded_media.py`
- `tests/test_attachment_storage.py`
- `tests/test_attachment_parser.py`
- `tests/test_analyzer.py`
- `tests/test_api.py`

Task records:

- `.superpowers/sdd/progress.md`
- `.superpowers/sdd/task-4-report.md`
- `docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md`

## TDD evidence

All Python runs used the pinned Python 3.12.13 runtime with the project and
Python 3.12 site packages on `PYTHONPATH`.

- Baseline before Task 4: 1,238 tests passed with one expected skip.
- Initial media/storage/API RED: 18 tests produced 3 failures and 6 errors for
  the missing modules, missing cleanup lifecycle, and deliberately exposed
  unsafe media behavior. The first focused GREEN passed 38 tests.
- Parser/analyzer carrier RED: 14 tests produced 1 failure and 4 errors for the
  missing OOXML roots, evidence binding, route carrier, and wipe lifecycle. The
  next integrated focused run passed 109 tests.
- Image/PDF/Office hardening passed 30 tests after correcting the sanitized PNG
  re-audit to verify a fresh Pillow handle and building a valid synthetic PDF
  active-object fixture.
- The final five approved lifecycle and bound cases all failed before their
  production changes: bounded Office prefix retention, unexpected-failure
  buffer wiping, case-insensitive ZIP duplicates, raw Office input size, and
  post-storage budget cleanup. The same five cases then passed.
- Frozen Task 4 focused matrix:

```text
Ran 186 tests in 4.377s
OK
```

### Mechanical-rule closure

The first full run had no business or security regression, but correctly
failed seven mechanical checks: four functions exceeded 50 lines and two
modules exceeded 300 lines (one function/file caused both categories). The
pure refactor split image sanitation, PDF sanitation, and media-evidence
binding into focused modules and extracted small helpers without changing the
frozen tests or public imports.

```text
Ran 7 tests in 0.241s
OK
```

The frozen focused matrix passed again after that refactor, followed by the
fresh correct-environment full suite:

```text
Ran 1285 tests in 91.116s
OK (skipped=1)
```

`git diff --check` also exited 0; it printed only the checkout's expected
LF-to-CRLF conversion warnings.

### Root fresh-review closure

Root fresh review of commit `34a82702d8eddf001190dfd5b71ac01812d139ae`
found four Important gaps. The six exact regression methods produced eleven
assertion failures before production changes:

- page/catalog active PDF graphs left detached JavaScript, Filespec, and
  EmbeddedFile objects in the serialized xref even after the page root looked
  clean;
- a later unexpected Office image-sanitizer exception left an earlier mutable
  prepared buffer populated;
- the text parser had no fixed raw compressed-package cap while media used a
  separate value;
- local-header-only encryption flags disagreed with the central directory but
  reached both the media reader and DOCX/XLSX loaders.

The same six methods passed after the bounded fixes:

```text
Ran 6 tests in 0.101s
OK
```

PDF sanitation now strips and audits the bounded reader-reachable graph before
`PdfWriter.add_page`, excludes the complete forbidden-key union during clone,
and audits the trailer plus every serialized xref identity under one node and
depth budget. Active indirect type/action values are resolved safely; object
streams and xref streams are rejected from the fresh-writer output contract.

Office text and media paths now share one fixed 10 MiB compressed-package
policy and enforce it before `ZipFile` construction or byte copying. Every ZIP
entry's full local header is read at its declared `header_offset`; the complete
general-purpose flag word must equal the central value and remain unencrypted
before roots, media, or third-party loaders are read. Unexpected ordinary
exceptions wipe all accumulated media buffers before being re-raised.

Final review-fix verification:

```text
Ran 192 tests in 4.975s
OK

Ran 7 tests in 0.264s
OK

Ran 1291 tests in 90.909s
OK (skipped=1)
```

## Security and scope boundaries

- No original filename, source path, private URL, cookie, token, raw binary,
  provider-ready Base64, or prepared buffer is added to a repr, fixed media
  exception, HTTP response, SQLite field, or log.
- No Task 5 request builder, OpenAI Responses call, provider payload, prompt
  change, provider switch, live browser, mailbox, real email, API key, `.env`,
  or external API was accessed.
- Existing DeepSeek, OpenAI placeholder, Ollama, prompt, API response, and
  SQLite contracts remain unchanged.
- Project-status generation and maintenance/release scans remain deferred to
  the plan's later integration/release-gate task.
- The pre-existing untracked review-package and Task 4 brief files are not part
  of this implementation and must not be staged.

## Review state

The root-review fix scope and expanded test matrix are frozen for fresh
re-review. Task 5 remains unstarted until that gate closes.
