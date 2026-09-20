---
last_update: 2026-09-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Independent Windows desktop rebuild

## Goal and authority
The operator requests a runnable program in a NEW project because the existing migration cannot progress, and selects a self-contained Windows desktop program. The new directory is email_ai_assistant_rebuild. This is a fresh application build, not Issue #39 execution, repository migration, resume or recovery. The initial build left the old project unchanged; after separately verified historical extraction, the operator manually deleted the retired directories. See README.md for the completed retirement status.

## Scope
Reuse reviewed product source from master 407f49b1 and its pure transitive dependencies. Add an independent native desktop launcher, session-only provider configuration, click-driven manual input and attachments, original loopback extension compatibility, a fresh local analysis database, reproducible build script, and portable Windows executable distribution. Preserve analysis schemas and model guards. Do not import the migration, mailbox-ingest, private-vault, authority-store, worktree or recovery implementations.

## Data and exclusions
The application includes only allowlisted product source, frontend resources and synthetic tests. Its runtime never imports old configuration, databases, signing files, credentials or private stores. Repository history and encrypted historical material were separately retained in Git and the excluded LegacyArchive under the operator's later archival authorization. Package a newly built environment with pinned product dependencies. All providers default disabled; a UI choice and session key explicitly enable a fixed provider route. Keys are neither logged nor saved. Automated verification makes no real mailbox or provider calls; separately approved manual DeepSeek acceptance is described in docs/desktop_mail_acceptance.md.

## Interfaces and verification
Verify the public loopback health and Analyze request interfaces, native window input/result/copy behavior, click-only attachment reads, fixed attachment limits, restart/close and fresh result persistence. Run preserved synthetic product regression tests and a bundled-executable self-test using caller-owned temporary state. Do not claim production semantic accuracy or real mailbox acceptance from these tests.

## Delivery
A native Windows application and its bundled dependencies; user runs EmailAssistant.exe without installing Python. Original browser extension remains optional for current Tencent Exmail extraction. Manually pasted current-mail text can be analyzed inside the desktop window. Raw history import, knowledge publishing and migration administration are not included in the desktop shell. Preserve the original source for later development and record provenance of reused files.

## Operator corrections on 2026-09-19
Use the latest stable Python and ALL direct and transitive Python dependencies after compatibility verification. This explicitly supersedes the legacy version ceilings in the source project for this independent rebuild. Official Python release metadata identifies Python 3.14.7. Resolve stable package versions from PyPI and lock the actually tested environment. Keep source, runtime, packages, application, data, logs, temporary files and build caches inside this project folder under D:\Projects. Do not use AppData for application storage or reference the old project's runtime at execution.
