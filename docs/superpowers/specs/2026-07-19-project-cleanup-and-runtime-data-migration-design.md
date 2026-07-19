---
last_update: 2026-07-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Project Cleanup And Runtime Data Migration Design

## Goal

Create a smaller, clearer development checkout while preserving the operator's
active analysis history and every current product, security, test, and audit
boundary. Cleanup is an explicit one-time maintenance operation, not a new
background cleanup capability.

## Approved decision

The operator chose Option A. The active runtime SQLite database moves from the
Git worktree to this project-external, operator-approved OneDrive location:

```text
C:\Users\<operator>\OneDrive\文档\DELIFU\email-ai-assistant-local-data\email_agent.sqlite3
```

The one-time implementation resolves and validates the operator-approved local
path. The committed design deliberately uses `<operator>` instead of recording
the local Windows account name.

The application continues to use the existing `EMAIL_AGENT_SQLITE_PATH`
configuration seam. No code default, database schema, API, or committed
configuration changes. The ignored local `.env` receives only the new path.

## Design principles

1. **Evidence before deletion.** A path is deleted only when it is on the fixed
   whitelist and its tracked/ignored/reference state still matches inventory.
2. **Data before tidiness.** The active database remains at its original path
   until an external create-only copy passes all integrity gates.
3. **No broad recursive cleanup.** The operation never targets a root such as
   `.worktrees`, `.superpowers/sdd`, `outputs`, `.venv`, or the repository itself.
4. **Tracked history stays tracked.** Product code, tests, ADRs, plans, task
   reports, and existing user work are not deletion candidates.
5. **Content-free observability.** Migration and verification report fixed
   status, counts, and equality booleans only.
6. **One mutation root.** Ignored-file cleanup and database migration run only
   against the registered main checkout after exact root validation. The
   isolated cleanup worktree and every other linked worktree remain read-only.

## Current evidence

The inventory observed the following without reading secrets or database text:

| Class | Evidence | Decision |
|---|---|---|
| Python bytecode | 7 ignored directories, 294 files, 4,211,847 bytes | delete |
| Review diffs | 70 ignored, unreferenced `review-*.diff` files, 9,161,324 bytes | delete |
| Cleanup report | ignored temporary report, 85 bytes | delete |
| Error log | ignored zero-byte service error log | delete |
| Active SQLite | ignored, 417,792 bytes, current configured path | migrate |
| Older SQLite | ignored, 12,288 bytes under `scripts/outputs` | empty-check, then delete or migrate |
| Runtime log | ignored operator diagnostic log, 2,610 bytes | keep |
| `.env` | ignored local configuration | keep; update one key only |
| `.venv` | ignored but current verification runtime | keep |
| `.idea` | ignored and recently updated user IDE state | keep |
| Active worktree | `codex/multimodal-plan-c`, contains local work | keep |
| Tracked files | no high-confidence deletion candidate | keep |

The maintenance scan emitted the aggregate fixed finding
`LEAK_PRIVATE_IDENTIFIER` for `public_sqlite` with count 252. Git ignores both
in-repository databases, so they are not upload candidates, but the scanner
intentionally treats every database under the repository root as public scope.
Moving preserved history outside the repository closes that conflict without
weakening the scanner.

## Database migration

### Preconditions

The migration stops before mutation unless all conditions hold:

- `scripts/manage_local_service.py status` reports `stopped`.
- The source is a regular file at the exact approved path and is not a directory.
- Git reports the source as ignored and not tracked.
- No matching `-wal`, `-shm`, or `-journal` sidecar exists. A sidecar causes a
  conservative stop so the operation never copies an incomplete SQLite state.
- The ignored `.env` contains exactly one `EMAIL_AGENT_SQLITE_PATH` assignment.
  Its original line is retained in memory for handled-error restoration before
  any external database file is created.
- The resolved external root is the exact sibling directory named
  `email-ai-assistant-local-data`, remains under the approved OneDrive `DELIFU`
  directory, and is outside every registered repository worktree.
- For a fresh run, the target does not exist. An existing target is accepted
  only by the interrupted-run resume protocol below. The operation never
  overwrites a database.

### Create-only copy and validation

1. Create the external data directory if absent.
2. Copy the active source to a randomly named staging file inside the external
   directory using create-only semantics.
3. Compare source and staging sizes.
4. Compute source and staging SHA-256 values in memory and report only whether
   they match.
5. Open the staging database read-only with the standard-library `sqlite3`
   module and run `PRAGMA quick_check`; report only `ok=true|false`.
6. Record the verified staging file identity, then rename it to the final
   filename only when the final target is still absent.
7. Modify only the exact `EMAIL_AGENT_SQLITE_PATH` entry in ignored `.env`.
8. Load configuration locally and verify only that the resolved configured path
   equals the approved target; do not print configuration or environment values.
9. Immediately before source removal, repeat the source file-identity, size,
   timestamp, and digest checks. Any drift keeps both copies and stops.
10. Remove the original source only after every preceding gate passes.

If any gate fails, the source remains. A pre-final staging file may be removed by
its already-open exact path. If a handled failure occurs after the final rename
but before source removal, restore the exact original `.env` line and remove the
new final target only after its current file identity still equals the recorded
staging identity and its digest still equals the preserved source. Otherwise,
preserve both files and stop rather than guessing.

An interrupted run has one narrow resume path. When both source and final target
exist, a rerun may resume only if the source is still the configured path, both
paths and SQLite sidecar checks pass, their size and digest are equal, and the
target passes read-only integrity validation. If `.env` already points to the
target, resume is allowed only when those same checks pass and the source is
unchanged. Every other existing-target state stops for a new explicit decision;
the operation never overwrites either file.

### Older duplicate database

The `scripts/outputs/email_agent.sqlite3` candidate is never assumed empty from
its size. It is opened read-only and evaluated with fixed aggregate row counts:

- If every user table contains zero rows, delete the ignored untracked file.
- If any user row exists, migrate it with the same create-only copy, digest, and
  integrity gates to
  `email-ai-assistant-local-data/legacy-scripts-email-agent.sqlite3`.
- Never output table names, row values, identifiers, or per-table counts.
- If the distinct legacy target exists, stop and preserve the source.

## Generated-artifact cleanup

Every local mutation in this section targets the registered main checkout. The
implementation first compares its resolved root with the approved repository
path and stops if they differ. It never redirects the allowlist to the isolated
cleanup worktree or the active multimodal worktree.

### Python caches

Delete only these exact ignored directories from the main checkout:

```text
backend/__pycache__
backend/email_agent/__pycache__
backend/mailbox_ingest/__pycache__
backend/private_evaluation/__pycache__
backend/private_knowledge/__pycache__
scripts/__pycache__
tests/__pycache__
```

Before recursive deletion, resolve each absolute path and require its parent and
basename to match the fixed allowlist. Do not follow or enumerate another shell's
computed paths. The active `.venv` and every worktree are excluded.

### Review diffs

For each `.superpowers/sdd/review-*.diff` candidate:

- require a direct child of the exact `.superpowers/sdd` directory;
- require extension `.diff` and basename matching the fixed review-diff pattern;
- require `git ls-files --error-unmatch` to fail;
- require `git check-ignore` to succeed;
- require zero tracked literal references to the repository-relative path;
- delete with PowerShell `Remove-Item -LiteralPath` in the same verified shell.

The directory itself is never removed. All tracked SDD records, all Markdown
records, and the seven ignored Markdown files referenced by tracked documents
remain.

### Small runtime artifacts

Delete only:

```text
outputs/cleanup_report.md
outputs/local_debug_service.err.log
```

Both must still be ignored and untracked. The error log must still have length
zero. Keep `outputs/local_debug_service.log` and the empty configured attachment
temporary directory.

## Tracked documentation treatment

`docs/operations/file_inventory.md` is an initial migration record, not a current
inventory. Deleting it would remove useful traceability and break an existing
navigation reference. The implementation therefore:

- changes front matter from `status: active` to `status: deprecated`;
- updates `last_update` to `2026-07-19`;
- adds a notice that current structure and state live in
  `docs/operations/project_structure.md` and
  `docs/operations/project_status_log.md`;
- leaves the historical keep/delete record intact.

No other tracked file is deleted. `backend/email_agent/exporter.py`, AGENTS
snippets, deprecated plans, and task audit records remain because current
evidence does not justify deletion.

## Preserved state

The implementation must not modify or delete:

- `.env` except for the exact SQLite path assignment;
- `.venv`, `.idea`, `.git`, or `.github`;
- `.worktrees/multimodal-plan-c` or any registered worktree;
- the operator's uncommitted `docs/operations/deployment_notes.md` change;
- `outputs/local_debug_service.log`;
- tracked `.superpowers/sdd` files or ignored Markdown audit records;
- external raw vaults, authority stores, snapshots, evaluation datasets,
  recovery keys, or any `.pkeval*`/`.pk*` material.

## Error handling and rollback

- **Service running:** stop without mutation and ask the operator to stop it.
- **Unexpected path, tracking state, or non-resumable existing target:** stop
  without deletion. Reject a symlink, junction, or other redirection whose
  resolved target escapes the approved main-checkout or external-data boundary.
  Ordinary OneDrive cloud-file attributes alone are not a failure when the
  resolved path remains within the approved boundary.
- **Copy, digest, or integrity failure:** keep the source; remove only the exact
  incomplete staging file.
- **`.env` key absent or duplicated:** stop after preserving both database files;
  do not guess which entry to edit.
- **Configuration verification failure:** restore the original single path line
  and keep the source.
- **Post-migration test failure:** keep the external database as the sole
  authoritative runtime copy, revert tracked documentation independently, and
  report the failing gate. Moving data back into the repository is a separate
  destructive migration requiring fresh approval, create-only copy, stopped
  service, sidecar, digest, integrity, and configuration gates; it is not an
  automatic rollback in this cleanup.
- **Generated-artifact validation drift:** skip only the drifted candidate and
  report its fixed category/count; never widen the pattern.

## Verification

After local mutations and tracked documentation changes:

1. Confirm the service remains stopped.
2. Confirm the external database exists, its content-free integrity check passes,
   and both in-repository database paths are absent.
3. Confirm `.env`, `.venv`, `.idea`, the active worktree, runtime log, tracked SDD
   records, and the operator's deployment-notes change remain present.
4. Run the repository leakage scan and maintenance scan; both must have zero high
   findings.
5. Run the focused configuration/database/service/documentation guards.
6. Run the complete `python -B -m unittest discover -s tests` suite with the
   project provider disabled and the existing project virtual environment.
7. Run architecture, static, mechanical, mailbox-transport, and JavaScript syntax
   checks.
8. Regenerate `docs/operations/project_status_log.md`, then rerun documentation
   guards, maintenance, leakage, and the full suite.
9. Run `git diff --check` and inspect staged paths. `.env`, SQLite, logs, caches,
   outputs, and user-owned changes must not be staged.

No verification step calls a remote provider, opens a mailbox, reads an external
vault, or displays private database content.

## Acceptance criteria

- Analysis history is preserved at the approved external OneDrive path.
- No SQLite file remains under the Git repository root.
- At least the 70 review diffs, seven Python cache directories, temporary cleanup
  report, and empty error log are removed when their gates still match.
- No tracked product file is deleted.
- The obsolete file inventory is retained as deprecated history.
- The maintenance and leakage scans report no high finding.
- Full tests and executable constraints pass.
- The resulting commit contains documentation and testable cleanup-policy changes
  only; ignored local data migration and generated-file deletion are never
  committed.

## Authorization boundary

This design records one approved local project cleanup. It does not authorize a
scheduled deleter, broader cleanup command, mailbox action, provider call,
external-vault operation, or future database migration.
