---
last_update: 2026-07-19
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Project Cleanup And Runtime Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely migrate the active ignored SQLite history to the approved project-external OneDrive directory, remove only the approved generated artifacts, and update tracked cleanup documentation without touching user work or private content.

**Architecture:** Tracked documentation changes are prepared and reviewed in the isolated `codex/project-cleanup` worktree. Destructive local-only operations run against the separately validated main checkout and use fixed allowlists, create-only copies, content-free SQLite checks, and source-last deletion. No reusable deleter, provider call, mailbox action, or new dependency is introduced.

**Tech Stack:** Windows PowerShell, Python 3.12 standard library (`hashlib`, `os`, `pathlib`, `sqlite3`, `uuid`), Git, existing project virtual environment.

## Global Constraints

- Derive the main checkout from `$env:USERPROFILE\OneDrive\文档\DELIFU\email-ai-assistant`; never commit or log the resolved Windows account name. The isolated tracked-change worktree is exactly `.worktrees\project-cleanup` below that root.
- Preserve the user's unstaged `docs/operations/deployment_notes.md` modification and the active `.worktrees/multimodal-plan-c` worktree.
- Do not print or persist `.env` values, database text, table names, hashes, email content, identifiers, keys, tokens, external-vault data, or private-evaluation data.
- No mailbox access, browser navigation, remote provider call, send, delete, move, archive, or scheduled cleanup.
- Keep `.env`, `.venv`, `.idea`, `outputs/local_debug_service.log`, tracked SDD records, and ignored Markdown audit records.
- The local service must remain stopped and `EMAIL_AGENT_LLM_PROVIDER=disabled` throughout verification.
- Database copies are create-only; never overwrite an existing target. Source deletion is always the final migration action.
- Reject SQLite `-wal`, `-shm`, or `-journal` sidecars and any symlink/junction/path escape. Ordinary in-boundary OneDrive cloud attributes are allowed.
- Local-only mutations apply only to the validated main checkout; tracked documentation changes apply only to the isolated cleanup worktree until integration.
- Use `apply_patch` for text-file edits. Use native PowerShell end-to-end for verified filesystem deletion.

---

### Task 1: Commit The Executable Plan And Lock The Preconditions

**Files:**
- Create: `docs/superpowers/plans/2026-07-19-project-cleanup-and-runtime-data-migration.md`
- Preserve: `docs/operations/deployment_notes.md`

**Interfaces:**
- Consumes: approved task brief and cleanup design at commit `bb24071`.
- Produces: a committed execution checklist and a fixed content-free preflight result.

- [ ] **Step 1: Validate the two Git roots and branch state**

Run from PowerShell without changing directories through another shell:

```powershell
$main = Join-Path $env:USERPROFILE 'OneDrive\文档\DELIFU\email-ai-assistant'
$work = Join-Path $main '.worktrees\project-cleanup'
function ConvertTo-NormalPath([string] $Path) {
    return [IO.Path]::TrimEndingDirectorySeparator(
        [IO.Path]::GetFullPath($Path)
    ).Replace('/', '\')
}
$main = ConvertTo-NormalPath $main
$work = ConvertTo-NormalPath $work
$rawGitMain = (git -C $main rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0) { throw 'main_git_query_failed' }
$rawGitWork = (git -C $work rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0) { throw 'worktree_git_query_failed' }
$gitMain = ConvertTo-NormalPath ($rawGitMain.Trim())
$gitWork = ConvertTo-NormalPath ($rawGitWork.Trim())
if ($gitMain -cne $main) { throw 'main_root_invalid' }
if ($gitWork -cne $work) { throw 'worktree_root_invalid' }
$mainBranch = (git -C $main branch --show-current)
if ($LASTEXITCODE -ne 0 -or $mainBranch.Trim() -cne 'master') { throw 'main_branch_invalid' }
$workBranch = (git -C $work branch --show-current)
if ($LASTEXITCODE -ne 0 -or $workBranch.Trim() -cne 'codex/project-cleanup') { throw 'cleanup_branch_invalid' }
```

Expected: exit `0` with no path or content output from the validation block.

- [ ] **Step 2: Confirm the protected state and stopped service**

```powershell
$py = Join-Path $main '.venv\Scripts\python.exe'
$serviceOutput = @(& $py -B (Join-Path $main 'scripts\manage_local_service.py') status)
$serviceCode = $LASTEXITCODE
if ($serviceCode -ne 3 -or ($serviceOutput -join "`n").Trim() -cne 'stopped') {
    throw 'service_not_stopped'
}
git -C $main status --short
if ($LASTEXITCODE -ne 0) { throw 'main_status_failed' }
git -C $main worktree list --porcelain
if ($LASTEXITCODE -ne 0) { throw 'worktree_list_failed' }
```

Expected: service reports `stopped`; main status contains the existing deployment-notes modification and no unexpected tracked mutation; the multimodal and cleanup worktrees are registered.

- [ ] **Step 3: Run content-free path and configuration preflight**

The check must emit only fixed booleans/counts:

```powershell
$source = Join-Path $main 'outputs\email_agent.sqlite3'
$legacy = Join-Path $main 'scripts\outputs\email_agent.sqlite3'
$externalRoot = Join-Path (Split-Path $main -Parent) 'email-ai-assistant-local-data'
$target = Join-Path $externalRoot 'email_agent.sqlite3'
$envLines = @(Get-Content -LiteralPath (Join-Path $main '.env') -Encoding UTF8 |
    Where-Object { $_ -match '^\s*EMAIL_AGENT_SQLITE_PATH\s*=' })
$sidecars = @("$source-wal", "$source-shm", "$source-journal") |
    Where-Object { Test-Path -LiteralPath $_ }
$sourceExists = Test-Path -LiteralPath $source -PathType Leaf
$targetExists = Test-Path -LiteralPath $target -PathType Leaf
$envValueClass = if ($envLines.Count -ne 1) {
    'invalid'
} elseif ($envLines[0] -eq 'EMAIL_AGENT_SQLITE_PATH=outputs/email_agent.sqlite3') {
    'source'
} elseif ($envLines[0] -match '^EMAIL_AGENT_SQLITE_PATH=.+/email-ai-assistant-local-data/email_agent\.sqlite3$') {
    'target'
} else {
    'conflict'
}
$migrationState = if ($sourceExists -and -not $targetExists -and $envValueClass -eq 'source') {
    'fresh'
} elseif ($sourceExists -and $targetExists -and $envValueClass -in @('source', 'target')) {
    'resume'
} elseif (-not $sourceExists -and $targetExists -and $envValueClass -eq 'target') {
    'complete'
} elseif ($sourceExists -and -not $targetExists -and $envValueClass -eq 'target') {
    'repair_env'
} else {
    'conflict'
}
[pscustomobject]@{
    SourceRegular = (Test-Path -LiteralPath $source -PathType Leaf)
    LegacyRegular = (Test-Path -LiteralPath $legacy -PathType Leaf)
    EnvAssignmentCount = $envLines.Count
    SidecarCount = $sidecars.Count
    MigrationState = $migrationState
}
```

Expected for this first execution: `SourceRegular=True`, `LegacyRegular=True`, `EnvAssignmentCount=1`, `SidecarCount=0`, and `MigrationState=fresh`. A later interrupted run may enter only `resume`, `complete`, or `repair_env`; the migration process must fully verify that state before mutation. Stop on `conflict`.

- [ ] **Step 4: Verify ignored/untracked status without reading file contents**

```powershell
git -C $main check-ignore -q -- outputs/email_agent.sqlite3
if ($LASTEXITCODE -ne 0) { throw 'active_database_not_ignored' }
git -C $main ls-files --error-unmatch -- outputs/email_agent.sqlite3 2>$null
if ($LASTEXITCODE -eq 0) { throw 'active_database_tracked' }
git -C $main check-ignore -q -- scripts/outputs/email_agent.sqlite3
if ($LASTEXITCODE -ne 0) { throw 'legacy_database_not_ignored' }
git -C $main ls-files --error-unmatch -- scripts/outputs/email_agent.sqlite3 2>$null
if ($LASTEXITCODE -eq 0) { throw 'legacy_database_tracked' }
```

Expected: exit `0`; neither database is tracked.

- [ ] **Step 5: Self-review and commit the plan**

```powershell
git -C $work diff --check
if ($LASTEXITCODE -ne 0) { throw 'plan_diff_check_failed' }
git -C $work add -- docs/superpowers/plans/2026-07-19-project-cleanup-and-runtime-data-migration.md
if ($LASTEXITCODE -ne 0) { throw 'plan_stage_failed' }
git -C $work diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'plan_staged_diff_check_failed' }
git -C $work diff --cached --name-only
if ($LASTEXITCODE -ne 0) { throw 'plan_staged_names_failed' }
git -C $work commit -m "docs: plan safe project cleanup"
if ($LASTEXITCODE -ne 0) { throw 'plan_commit_failed' }
```

Expected: exactly the plan file is staged and committed.

### Task 2: Migrate The Active SQLite Database

**Files:**
- Local temporary create, then remove: `outputs/project_cleanup_migration.py`
- Local temporary create, then remove: `outputs/test_project_cleanup_migration.py`
- Local create: `C:\Users\<operator>\OneDrive\文档\DELIFU\email-ai-assistant-local-data\email_agent.sqlite3`
- Local modify: `.env` (`EMAIL_AGENT_SQLITE_PATH` only)
- Local remove after verification: `outputs/email_agent.sqlite3`

**Interfaces:**
- Consumes: Task 1 preflight, stopped service, ignored source database.
- Produces: a verified external authoritative database and a local configuration path pointing to it.

- [ ] **Step 1: Create the ignored one-time migration helper and synthetic tests**

Use `apply_patch` in the main checkout to create the two exact ignored files listed above. The helper is not a product feature and must be deleted after Task 3. It exposes these focused interfaces:

```python
def classify_state(*, source_exists: bool, target_exists: bool, env_class: str) -> str:
    """Return fresh, resume, complete, repair_env, or conflict."""

def assert_safe_path(path: Path, *, exact: Path, boundary: Path) -> None:
    """Require exact normalized path, resolved containment, and no symlink/junction in existing ancestors."""

def stable_digest(path: Path) -> tuple[tuple[int, int, int, int], bytes]:
    """Return (st_dev, st_ino, st_size, st_mtime_ns) plus SHA-256; fail on stat drift."""

def sqlite_quick_check(path: Path) -> bool:
    """Open with mode=ro and accept only the single result ('ok',)."""

def service_is_stopped(*, python_exe: Path, manager: Path) -> bool:
    """Capture output and return true only for exit code 3 and exact text stopped."""

def migrate_active(*, source: Path, target: Path, env_file: Path,
                   expected_env_line: str, main_root: Path,
                   external_root: Path, python_exe: Path) -> str:
    """Perform fresh/resume/complete migration in one process and return a fixed code."""
```

`migrate_active` must keep the staging path, staging identity, created-target identity, and digests in the same process. For a fresh state it uses UUID staging opened with `xb`, stable streaming copy, digest equality, read-only integrity, and Windows create-only rename. For resume it requires source/target equality and target integrity. For complete it requires target integrity and the exact target `.env` assignment. It checks the fixed stopped-service result and sidecar absence immediately before copying and again immediately before source unlink. On a handled failure before source unlink, it removes only an exact staging file or a target whose identity still matches the target created by that same process. It emits no exception detail, paths, hashes, schema, or rows.

The synthetic test file uses temporary directories and synthetic SQLite only. It must cover:

```python
class ProjectCleanupMigrationTests(unittest.TestCase):
    def test_classify_state_covers_fresh_resume_complete_repair_and_conflict(self): ...
    def test_fresh_migration_copies_valid_database_and_removes_source_last(self): ...
    def test_resume_requires_equal_source_and_target(self): ...
    def test_complete_state_is_idempotent_and_integrity_checked(self): ...
    def test_sidecar_rejects_before_copy(self): ...
    def test_digest_mismatch_preserves_source(self): ...
    def test_service_not_stopped_preserves_source(self): ...
    def test_symlink_or_junction_escape_is_rejected(self): ...
    def test_failure_output_uses_only_fixed_code(self): ...
```

- [ ] **Step 2: Run the one-time helper tests before touching real data**

```powershell
& $py -B (Join-Path $main 'outputs\test_project_cleanup_migration.py')
```

Expected: all synthetic tests pass and no real database, `.env`, or external target is opened.

- [ ] **Step 3: Recheck stopped service and patch only the SQLite assignment**

Repeat the exact exit-code-`3` stopped-service check from Task 1. For `fresh` or `resume` with the source assignment, verify that assignment exactly and use `apply_patch` on the absolute main-checkout `.env` path, substituting the runtime-resolved `$target` with forward slashes. For `resume`, `complete`, or `repair_env` with the already exact target assignment, do not rewrite `.env`; the helper must validate it. The committed plan deliberately does not record the local account name:

```diff
-EMAIL_AGENT_SQLITE_PATH=outputs/email_agent.sqlite3
+EMAIL_AGENT_SQLITE_PATH=C:/Users/<operator>/OneDrive/文档/DELIFU/email-ai-assistant-local-data/email_agent.sqlite3
```

Any assignment outside those state-specific source/target values is `conflict`; do not create or delete a database.

- [ ] **Step 4: Run the active migration in one bounded process**

Invoke the helper from the main checkout with exact source, target, `.env`, main-root, external-root, and project Python arguments. The CLI prints only one fixed JSON object. Success is:

```json
{"ok": true, "code": "active_migration_complete"}
```

Accepted idempotent recovery success is `active_migration_already_complete`. Failure codes are restricted to `argument_invalid`, `path_invalid`, `redirect_rejected`, `env_invalid`, `service_not_stopped`, `sidecar_present`, `state_conflict`, `source_changed`, `digest_mismatch`, `integrity_failed`, or `copy_failed`.

If the process fails and the source still exists, reverse only an `.env` patch made by this execution. If the process is interrupted, rerun the state classifier: `source+target+env-target` enters verified resume; `source-only+env-target` enters `repair_env` and performs the same fully verified create-only copy as fresh; `target-only+env-target` enters verified complete; every other combination stops.

- [ ] **Step 5: Verify the active postcondition**

```powershell
$serviceOutput = @(& $py -B (Join-Path $main 'scripts\manage_local_service.py') status)
$serviceCode = $LASTEXITCODE
if ($serviceCode -ne 3 -or ($serviceOutput -join "`n").Trim() -cne 'stopped') {
    throw 'service_not_stopped'
}
[pscustomobject]@{
    SourceAbsent = -not (Test-Path -LiteralPath $source)
    TargetPresent = (Test-Path -LiteralPath $target -PathType Leaf)
    SidecarCount = @("$target-wal", "$target-shm", "$target-journal") |
        Where-Object { Test-Path -LiteralPath $_ } |
        Measure-Object |
        Select-Object -ExpandProperty Count
}
```

Expected: `SourceAbsent=True`, `TargetPresent=True`, `SidecarCount=0`.

### Task 3: Resolve The Legacy Database And Delete Only Whitelisted Artifacts

**Files:**
- Local temporary modify, then remove: `outputs/project_cleanup_migration.py`
- Local temporary modify, then remove: `outputs/test_project_cleanup_migration.py`
- Local remove or migrate: `scripts/outputs/email_agent.sqlite3`
- Local optional create: `email-ai-assistant-local-data/legacy-scripts-email-agent.sqlite3`
- Local remove: seven exact `__pycache__` directories, approved `review-*.diff`, `outputs/cleanup_report.md`, and zero-byte `outputs/local_debug_service.err.log`

**Interfaces:**
- Consumes: validated main root and Task 2 authoritative database.
- Produces: no SQLite below the repository root and an evidence-backed generated-artifact cleanup.

- [ ] **Step 1: Extend and test the one-time helper for the legacy database**

Repeat the exact exit-code-`3` stopped-service check before changing the helper and again immediately before opening or deleting the real legacy database.

Use `apply_patch` on the two ignored helper files to add:

```python
def inspect_legacy(path: Path) -> str:
    """Return legacy_empty or legacy_nonempty without exposing schema or values."""

def migrate_legacy(*, source: Path, target: Path, main_root: Path,
                   external_root: Path, python_exe: Path) -> str:
    """Delete an empty source or create-only migrate a nonempty source."""
```

Open the legacy database read-only. Enumerate non-`sqlite_%` table names only in process memory, double-quote identifiers by replacing `"` with `""`, and issue `SELECT 1 FROM "<quoted>" LIMIT 1`. Print only one fixed result:

```json
{"ok": true, "code": "legacy_empty"}
```

or:

```json
{"ok": true, "code": "legacy_nonempty"}
```

Never print table names, counts, values, paths, or exception details.

Add synthetic tests proving that an empty database is removed only after stable identity and stopped-service checks, a nonempty database is migrated with create-only digest/integrity gates, quoted table names do not alter the query, target conflicts preserve the source, sidecars reject, and only fixed codes are emitted. Run the full temporary helper test file again and require all tests to pass before the real legacy file is opened.

- [ ] **Step 2: Delete an empty legacy file or migrate a nonempty one**

For `legacy_empty`, recheck ignored/untracked state, stable file identity, no sidecars, and remove only the exact legacy file. For `legacy_nonempty`, apply the same create-only copy, digest, integrity, stable-source, and source-last deletion gates from Task 2 to the distinct `legacy-scripts-email-agent.sqlite3` target. No `.env` change is made.

Expected fixed result: `legacy_removed_empty` or `legacy_migration_complete`.

- [ ] **Step 3: Delete the exact Python cache allowlist**

In one PowerShell process, store the seven repository-relative paths from the design in a literal array. Define a non-following tree check that examines `FileAttributes` before descending and rejects every symlink, junction, or reparse entry:

```powershell
function Assert-NoReparseTree([string] $Root) {
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push($Root)
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        $attributes = [IO.File]::GetAttributes($current)
        if (($attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'reparse_rejected'
        }
        if (($attributes -band [IO.FileAttributes]::Directory) -ne 0) {
            foreach ($child in [IO.Directory]::EnumerateFileSystemEntries($current)) {
                $childAttributes = [IO.File]::GetAttributes($child)
                if (($childAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    throw 'reparse_rejected'
                }
                if (($childAttributes -band [IO.FileAttributes]::Directory) -ne 0) {
                    $pending.Push($child)
                }
            }
        }
    }
}
```

For each path, normalize both separators and absolute form, require it to remain below the exact normalized main root, require its relative path to equal an allowlist entry, run `Assert-NoReparseTree`, require `git check-ignore` success, and require zero tracked files below it. Only then run:

```powershell
Remove-Item -LiteralPath $resolvedCandidate -Recurse -Force
```

Expected content-free result: `cache_directory_removed_count=7`. A missing or drifted candidate is skipped and reported only by fixed category/count.

- [ ] **Step 4: Delete only validated review diff files**

Enumerate direct children of the exact main `.superpowers\sdd` directory with `-Filter 'review-*.diff'`. Before enumeration, require the SDD directory and every existing ancestor below the normalized main root not to be a symlink, junction, or reparse point. For each candidate reject a reparse attribute, require the fixed basename regex, ignored state, untracked state, and zero `git grep -F` matches for its repository-relative literal path. Delete in the same PowerShell process with `Remove-Item -LiteralPath`.

Expected content-free result: `review_diff_removed_count=70` if inventory has not drifted. Never remove the directory or a Markdown file.

- [ ] **Step 5: Delete the two small approved artifacts**

For each exact path, normalize it below the main root, reject reparse attributes on the file or existing ancestors, and require ignored and untracked state. Additionally require `outputs/local_debug_service.err.log` length to remain zero. Delete each with `Remove-Item -LiteralPath`.

Expected: `small_artifact_removed_count=2`. Keep `outputs/local_debug_service.log`.

- [ ] **Step 6: Remove the two one-time helper files**

After both database postconditions are verified, require both helper paths to remain exact regular ignored/untracked files below `outputs`, reject reparse attributes, then delete them with `Remove-Item -LiteralPath`. Confirm neither helper exists and neither was staged or committed.

### Task 4: Update Tracked Historical Documentation

**Files:**
- Modify: `docs/operations/file_inventory.md`
- Modify: `docs/operations/project_cleanup_task_brief.md`
- Modify: `docs/operations/project_status_log.md`

**Interfaces:**
- Consumes: fixed aggregate results from Tasks 2 and 3.
- Produces: current navigation, an execution record without private data, and regenerated project metadata.

- [ ] **Step 1: Mark the obsolete inventory as historical**

Use `apply_patch` on the absolute cleanup-worktree path to change front matter `status: active` to `status: deprecated`, retain `last_update: 2026-07-19`, and insert a notice immediately below the title pointing to:

```text
docs/operations/project_structure.md
docs/operations/project_status_log.md
```

Do not rewrite the historical body.

- [ ] **Step 2: Record completion in the cleanup task brief**

Use `apply_patch` on the absolute cleanup-worktree path to change `Execution state: design_only` to `Execution state: completed` and replace the final execution paragraph with aggregate-only outcomes: active database migrated, legacy database resolved, approved generated counts removed, and no private content inspected or emitted. Do not record hashes, database values, local username, or `.env` contents.

- [ ] **Step 3: Regenerate project status and normalize only target-branch metadata if needed**

```powershell
& $py -B (Join-Path $work 'scripts\generate_project_status.py') `
    --output (Join-Path $work 'docs\operations\project_status_log.md')
```

Expected: document metadata counts include the new brief, design, and plan; `file_inventory.md` is counted as deprecated. Do not hand-edit generated content except an explicitly reviewed branch-name normalization required for integration.

- [ ] **Step 4: Run focused documentation and constraint tests**

```powershell
$env:EMAIL_AGENT_LLM_PROVIDER='disabled'
Push-Location -LiteralPath $work
try {
    & $py -B -m unittest tests.test_generate_project_status tests.test_static_linter_constraints tests.test_architecture_constraints tests.test_mechanical_rule_constraints
    if ($LASTEXITCODE -ne 0) { throw 'focused_tests_failed' }
    & $py -B scripts\maintenance_scan.py --fail-on-high
    if ($LASTEXITCODE -ne 0) { throw 'worktree_maintenance_failed' }
    & $py -B scripts\repository_leakage_scan.py
    if ($LASTEXITCODE -ne 0) { throw 'worktree_leakage_scan_failed' }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'worktree_diff_check_failed' }
} finally {
    Pop-Location
}
Push-Location -LiteralPath $main
try {
    & $py -B scripts\maintenance_scan.py --fail-on-high
    if ($LASTEXITCODE -ne 0) { throw 'main_maintenance_failed' }
    & $py -B scripts\repository_leakage_scan.py
    if ($LASTEXITCODE -ne 0) { throw 'main_leakage_scan_failed' }
} finally {
    Pop-Location
}
```

Expected: tests pass, both scans have zero high findings in both the main checkout and cleanup worktree, and diff check is clean.

- [ ] **Step 5: Commit the tracked documentation update**

Stage only the three listed documentation files and commit:

```powershell
git -C $work add -- docs/operations/file_inventory.md docs/operations/project_cleanup_task_brief.md docs/operations/project_status_log.md
if ($LASTEXITCODE -ne 0) { throw 'documentation_stage_failed' }
git -C $work diff --cached --check
if ($LASTEXITCODE -ne 0) { throw 'documentation_staged_diff_failed' }
git -C $work diff --cached --name-only
if ($LASTEXITCODE -ne 0) { throw 'documentation_staged_names_failed' }
git -C $work commit -m "chore: finalize safe project cleanup"
if ($LASTEXITCODE -ne 0) { throw 'documentation_commit_failed' }
```

Expected: no `.env`, SQLite, log, cache, output, worktree, or deployment-notes path is staged.

### Task 5: Full Verification And Branch Completion

**Files:**
- Verify only: entire repository and local postconditions

**Interfaces:**
- Consumes: completed local mutations and tracked commits.
- Produces: fresh completion evidence and a reviewed integration choice.

- [ ] **Step 1: Verify protected paths and Git scope**

Confirm `.env`, `.venv`, `.idea`, `outputs/local_debug_service.log`, the multimodal worktree, tracked/ignored Markdown SDD records, and the user's deployment-notes modification remain. Confirm the two known in-repository SQLite paths and both temporary helper paths are absent, repository leakage scan finds no other SQLite leakage, and no ignored local artifact is staged. Use `Test-Path` booleans and `git -C <root> status --short`; do not print protected file contents.

- [ ] **Step 2: Run the complete Python suite**

```powershell
$env:EMAIL_AGENT_LLM_PROVIDER='disabled'
Push-Location -LiteralPath $work
try {
    & $py -B -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) { throw 'full_test_suite_failed' }
} finally {
    Pop-Location
}
```

Expected: all tests pass with only the repository's documented skip.

- [ ] **Step 3: Run executable constraints and JavaScript syntax checks**

```powershell
Push-Location -LiteralPath $work
try {
    & $py -B -m unittest `
        tests.test_architecture_constraints `
        tests.test_static_linter_constraints `
        tests.test_mechanical_rule_constraints `
        tests.test_mailbox_transport_constraints `
        tests.test_generate_project_status `
        tests.test_multimodal_documentation_contracts `
        tests.test_deepseek_documentation_contracts
    if ($LASTEXITCODE -ne 0) { throw 'constraint_suite_failed' }
    & $py -B scripts\maintenance_scan.py --fail-on-high
    if ($LASTEXITCODE -ne 0) { throw 'worktree_maintenance_failed' }
    & $py -B scripts\repository_leakage_scan.py
    if ($LASTEXITCODE -ne 0) { throw 'worktree_leakage_scan_failed' }
    $trackedJavaScript = @(git ls-files '*.js')
    foreach ($relativePath in $trackedJavaScript) {
        node --check (Join-Path $work $relativePath)
        if ($LASTEXITCODE -ne 0) { throw 'javascript_syntax_failed' }
    }
    git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'worktree_diff_check_failed' }
} finally {
    Pop-Location
}
Push-Location -LiteralPath $main
try {
    & $py -B scripts\maintenance_scan.py --fail-on-high
    if ($LASTEXITCODE -ne 0) { throw 'main_maintenance_failed' }
    & $py -B scripts\repository_leakage_scan.py
    if ($LASTEXITCODE -ne 0) { throw 'main_leakage_scan_failed' }
} finally {
    Pop-Location
}
```

Expected: exit `0` throughout, zero high findings, and every tracked JavaScript file passes `node --check`.

- [ ] **Step 4: Perform independent whole-branch review**

Generate a review package from the branch merge base through `HEAD`. The reviewer checks deletion scope, database preservation evidence, `.env` exclusion, user-work preservation, documentation accuracy, and absence of authorization expansion. Resolve every Critical or Important finding and rerun its covering checks.

- [ ] **Step 5: Use the finishing-development-branch workflow**

Re-run the fresh full verification required by `superpowers:verification-before-completion`, then invoke `superpowers:finishing-a-development-branch`. Present the verified integration options without deleting the worktree or merging until the user selects the final option.
