---
last_update: 2026-07-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Project Cleanup And Runtime Data Migration Task Brief

## Task

Organize the current development checkout, remove only evidence-backed generated
artifacts, and move the active local SQLite analysis history outside the Git
working tree while keeping it in the operator-approved OneDrive location.

## Type and status

- Type: `chore`
- Status: `approved`
- Execution state: `design_only`

## Goal

Reduce local project clutter without deleting product code, audit history,
credentials, active work, or approved analysis history. The repository leakage
scan must no longer inspect the active runtime database as an in-repository
`public_sqlite` file.

## Non-goals

- No mailbox access, navigation, scan, send, delete, move, or archive operation.
- No OpenAI, DeepSeek, Ollama, or other provider call.
- No change to API, schema, prompt, provider route, browser extension, or runtime
  behavior beyond the operator-local SQLite path.
- No dependency installation or removal.
- No deletion of tracked business code, tests, ADRs, implementation plans, task
  audit records, `.env`, `.venv`, `.idea`, or an active Git worktree.
- No inspection or output of SQLite row content, email content, credentials,
  tokens, provider keys, external vaults, or private evaluation data.
- No modification of the operator's existing
  `docs/operations/deployment_notes.md` work.

## Evidence

- The main checkout contains seven ignored `__pycache__` directories with 294
  files totaling 4,211,847 bytes.
- `.superpowers/sdd` contains 70 ignored, unreferenced `review-*.diff` files
  totaling 9,161,324 bytes; tracked task records and referenced ignored records
  must remain.
- `outputs/cleanup_report.md` is an ignored temporary report and
  `outputs/local_debug_service.err.log` is an ignored zero-byte file.
- `outputs/email_agent.sqlite3` is the configured active database and is ignored
  by Git. `scripts/outputs/email_agent.sqlite3` is an older ignored duplicate
  candidate.
- The content-free repository leakage scan reports
  `LEAK_PRIVATE_IDENTIFIER` in aggregate `public_sqlite` scope. No database text
  was opened, copied, or reported during inventory.
- No tracked file has sufficient evidence for direct deletion.
- `docs/operations/file_inventory.md` is an obsolete initial-cleanup record that
  conflicts with the implemented repository state but remains useful history.

## Approved design

The operator selected and approved Option A:

1. Preserve the active analysis history under the project-external OneDrive path
   `C:\Users\<operator>\OneDrive\文档\DELIFU\email-ai-assistant-local-data\email_agent.sqlite3`.
   The implementation uses the operator-approved resolved local path; the
   committed document intentionally omits the local Windows account name.
2. Validate source and destination with content-free size, digest-equality, and
   SQLite integrity results before removing the source.
3. Change only `EMAIL_AGENT_SQLITE_PATH` in the ignored local `.env`; do not
   expose or rewrite other values.
4. Delete the old `scripts/outputs/email_agent.sqlite3` only if content-free row
   counts prove it is empty. If it contains rows, migrate it create-only to the
   same external data root under a distinct legacy filename.
5. Delete only the approved generated-artifact whitelist.
6. Mark `docs/operations/file_inventory.md` deprecated and point readers to the
   current project structure and generated status log.

## Expected file scope

### Local-only mutations

All local-only mutations apply to the registered main checkout only, after its
resolved root exactly matches the approved repository path. They must not run
inside the cleanup worktree, the active multimodal worktree, or any other linked
worktree.

- Move or copy-verify-remove: `outputs/email_agent.sqlite3`.
- Delete or migrate: `scripts/outputs/email_agent.sqlite3`.
- Modify only the local setting: `.env` key `EMAIL_AGENT_SQLITE_PATH`.
- Delete the seven inventoried `__pycache__` directories.
- Delete ignored `.superpowers/sdd/review-*.diff` files only after proving each
  candidate is untracked, ignored, under the exact SDD directory, and has zero
  tracked references.
- Delete: `outputs/cleanup_report.md`.
- Delete: `outputs/local_debug_service.err.log`.

### Tracked changes

- Create this task brief.
- Create
  `docs/superpowers/specs/2026-07-19-project-cleanup-and-runtime-data-migration-design.md`.
- Later create the approved implementation plan.
- Modify `docs/operations/file_inventory.md` only to mark it deprecated and add
  a supersession notice.
- Regenerate `docs/operations/project_status_log.md` after implementation.

## Interfaces and data

- Database schema: unchanged.
- Public API and SQLite projection: unchanged.
- AI output JSON: unchanged.
- Prompt: unchanged.
- Provider configuration: unchanged and disabled by default.
- Operator-local configuration: only the SQLite filesystem path changes.

## Safety and privacy

- [x] The service must be stopped before migration and deletion.
- [x] The destination must resolve outside the Git worktree and must not already
  exist; no overwrite is allowed.
- [x] Database validation emits only fixed booleans/count classes, never table
  names, values, subjects, addresses, message text, or identifiers.
- [x] The source remains intact until the external copy passes size equality,
  digest equality, read-only SQLite integrity validation, absence of SQLite
  sidecars, and a final unchanged-source check.
- [x] `.env` remains ignored and is never staged, printed, copied, or committed.
- [x] The active worktree, user modification, runtime diagnostic log, `.venv`,
  `.idea`, and audit records remain untouched.
- [x] No recursive delete may target the repository root, `.worktrees`,
  `.superpowers/sdd`, `outputs`, or any computed directory without an exact
  allowlist check.
- [x] No external vault, `.pkeval*`, private knowledge store, or key material is
  inspected or changed.

## Acceptance

1. The active database exists only at the approved external OneDrive path and
   passes content-free integrity checks.
2. The ignored `.env` points to that external database without exposing or
   altering unrelated values.
3. The two in-repository SQLite paths are absent after safe migration/deletion.
4. Only the approved generated files are removed; tracked files, active work,
   `.env`, `.venv`, `.idea`, and active worktrees are preserved.
5. `file_inventory.md` remains as deprecated historical evidence with current
   navigation links.
6. Repository leakage and maintenance scans have no high finding.
7. Full unit, architecture, static, mechanical, documentation, and Git diff
   checks pass after project-status regeneration.

## Rollback

- Before source removal, restore the exact original `.env` assignment and
  remove only a destination whose recorded file identity and digest still match
  the file created by this run. Otherwise preserve both copies and stop.
- An interrupted run may resume only after source/target equality, SQLite
  integrity, sidecar, path, and configuration checks all pass.
- After source removal, the external database is the sole authoritative copy.
  Moving it back requires a separately approved create-only migration and is not
  part of this cleanup's automatic rollback.
- Generated caches and Git-derived review diffs are intentionally not backed up;
  Python or Git can recreate them.
- Revert tracked documentation commits independently of local data migration.

## Human confirmation

The operator selected Option A and approved the complete cleanup design on
2026-07-19.

## Execution record

Implementation has not started. It remains gated by written-spec review and an
approved implementation plan.
