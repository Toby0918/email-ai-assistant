---
last_update: 2026-09-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Independent Windows desktop rebuild

## Goal and authority
The operator requests a runnable program in a NEW project because the existing migration cannot progress, and selects a self-contained Windows desktop program. The default new directory is email_ai_assistant_rebuild. This is a fresh application build, not Issue #39 execution, repository migration, resume or recovery. The old project remains unchanged.

## Scope
Reuse reviewed product source from master 407f49b1 and its pure transitive dependencies. Add an independent native desktop launcher, session-only provider configuration, click-driven manual input and attachments, original loopback extension compatibility, a fresh local analysis database, reproducible build script, and portable Windows executable distribution. Preserve analysis schemas and model guards. Do not import the migration, mailbox-ingest, private-vault, authority-store, worktree or recovery implementations.

## Data and exclusions
Copy only allowlisted Git-tracked product source, frontend resources and synthetic tests. Never copy .git, .env, databases, outputs, worktrees, virtual environments, signing files, credentials, closure evidence or private stores. Package a newly built environment with pinned product dependencies. All providers default disabled; a UI choice and session key explicitly enable a fixed existing provider route. Keys are neither logged nor saved. No real mailbox or provider call is part of verification.

## Interfaces and verification
Verify the public loopback health and Analyze request interfaces, native window input/result/copy behavior, click-only attachment reads, fixed attachment limits, restart/close and fresh result persistence. Run preserved synthetic product regression tests and a bundled-executable self-test using caller-owned temporary state. Do not claim production semantic accuracy or real mailbox acceptance from these tests.

## Delivery
A native Windows application and its bundled dependencies; user runs EmailAssistant.exe without installing Python. Original browser extension remains optional for current Tencent Exmail extraction. Manually pasted current-mail text can be analyzed inside the desktop window. Raw history import, knowledge publishing and migration administration are not included in the desktop shell. Preserve the original source for later development and record provenance of reused files.

## Operator corrections on 2026-09-19
Use the latest stable Python and ALL direct and transitive Python dependencies after compatibility verification. This explicitly supersedes the legacy version ceilings in the source project for this independent rebuild. Official Python release metadata identifies Python 3.14.7. Resolve stable package versions from PyPI and lock the actually tested environment. Keep source, runtime, packages, application, data, logs, temporary files and build caches inside this project folder under D:\Projects. Do not use AppData for application storage or reference the old project's runtime at execution.
