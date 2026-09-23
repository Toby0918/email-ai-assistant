---
last_update: 2026-09-23
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Independent desktop verification

## Browser Action Console, 2026-09-23

Extension 0.2.5 adds the guarded evidence layer and lifecycle checks on top of
the decision summary, action queue and read-only draft card. Current browser
verification and deployment instructions are in [browser_verification.md](browser_verification.md).
The earlier desktop counts below remain historical receipts, not current totals.

## Current-email acceptance, 2026-09-19

The source suite passed 186 tests, including seven native-window regressions and
the actual DeepSeek SDK serialization check using a synthetic HTTP transport.
The rebuilt executable self-test passed XLSX window analysis and changed-email
copy rejection alongside the earlier DOCX, cleanup and restart checks. The
renderer JavaScript syntax check also passed. Automated checks accessed no real
provider or mailbox. The operator's first live screenshot showed DeepSeek
participation but exposed local delivery/quote and deadline misclassifications.
The subsequent nine acceptance regressions cover those fixes, conservative model
merging, readable engine status and rejection of customer request/issue narrative
inside reply target clauses. The exact clean-input native XLSX flow and packaged
self-test also check the draft retains quantity and cautious timing without
echoing the customer's request. The operator's clean-input screenshot confirmed
delivery classification and attachment quantity; the subsequent draft screenshot
exposed the request echo now fixed. Operator review/copy of the corrected draft
remains pending. See docs/desktop_mail_acceptance.md for acceptance boundaries and
the general XLSX header-association limitation.

## Initial desktop baseline

The initial desktop baseline's unittest discovery passed 169 tests on Python 3.14.7 with
SQLite 3.53.4 and the installed stable package set recorded in
requirements-resolved.lock. The SDK compatibility test exercises actual SDK
serialization via httpx2 MockTransport without opening a provider connection.

The Windows executable was built successfully using PyInstaller 6.22.3. Its own
self-test returned PASS for the native window, synthetic click analysis, human
review copy gate, bundled static assets, DOCX isolated worker, attachment
temporary-file cleanup, result persistence across service restart and library
imports. Provider call count and live mailbox access count were both zero.

An additional execution used C:\Windows\System32 as the working directory and a
PATH containing only Windows directories, with PYTHONPATH empty. The same
packaged executable returned exit code zero and the same successful self-test.
This proves the tested executable path does not require the old project, a
system Python command, or launching from the source directory. It does not prove
compatibility with every other Windows computer or model response quality.

Build/desktop-self-test.json is the actual last executable report.
Build/desktop-draft-fix-build.log records the latest tests and packaging. The shipped program is
Program/EmailAssistant/EmailAssistant.exe. All configured data, logs, temporary,
build and cache paths are under the new project. OS-managed caches and Windows
runtime internals are outside application control.

The application was built from allowlisted source reads. No old .env, database,
private store or signing key was connected to runtime. Historical extraction and
encrypted archival were separate authorized work, completed before the operator
deleted the retired directories. Pure deidentification and schema helpers remain
because the analysis core imports them; no private-store reader is connected.

Scope limits: no real mailbox/UI extraction acceptance, no remote AI call, no
private history import and no bundled Tesseract OCR executable. The original
browser extension is available for separately operated current-mail
capture. pypdf's legacy decoder-limit compatibility currently emits deprecation
warnings in some inherited tests; the tested 6.19.0 limits remain effective.

Dependency exception: current Pydantic 2.13.5 declares the exact dependency
pydantic-core==2.46.5. Use that compatible version instead of forcing the standalone
2.49.0 release. pip check passes. The other 34 installed packages match their
current stable PyPI releases at the time of this verification.
