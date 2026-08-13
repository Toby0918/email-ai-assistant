---
last_update: 2026-08-13
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Pre-freeze workspace topology reconciliation task brief

## Task identity

- Type: fix
- State: implemented
- Governing remote baseline: `master@160bd10ee18cf6692352bcd65a3ae04277e8b313`
- Governing tree: `4a2d8a7ab6a733c3961d92a2b78bd35f86314fa8`
- Local implementation baseline: `5c1f77c6024f2567ea9412ad4cfeb699cf196f10`
- Local baseline tree: `4a2d8a7ab6a733c3961d92a2b78bd35f86314fa8`
- Branch: `codex/pre-freeze-topology-reconciliation`
- Confirmed test seam: public test fixture
  `tests.cutover_managed_activation_fixtures.build_runtime_scenario(directory=...)`

## Goal

Stop Issue #57 synthetic managed-activation fixtures from creating temporary
directories at a drive root or at the `D:\Projects` top level when the caller
supplies an owned parent. Produce a content-free classification of the current
`D:\`, `D:\Projects`, and registered-worktree topology before the next frozen
Issue #38 master.

## Authorization

The operator authorized implementation, tests, and content-free classification.
This task may create and edit only the allowlisted repository files below. It
must not delete, move, rename, replace, overwrite, unregister, prune, repair, or
clean any observed directory, worktree, Git administrative entry, ref, artifact,
stage, or failure site.

The task must not read legacy LocalData, private data, mailbox, provider, vault,
credential, or file payload content. It must not run a real migration, cutover,
preflight, evidence publication, Solo Maintainer confirmation, protected
verifier, Issue #38 mutation, or Issue #39 action.

## Expected changed files

- `tests/cutover_managed_activation_fixtures.py`
- `tests/test_cutover_managed_activation_fixture_boundaries.py`
- `docs/operations/pre_freeze_workspace_topology_reconciliation_task_brief.md`
- `docs/operations/pre_freeze_workspace_topology_reconciliation.md`
- `docs/operations/project_status_log.md` after implementation

No production package, workflow, GitHub state, migration contract, closure
contract, or execution surface is in scope.

## Interface and data changes

- Database: none.
- Public API or CLI: none.
- AI JSON: none.
- Prompt: none.
- Test interface: the existing optional
  `build_runtime_scenario(directory=...)` seam keeps its signature; both
  temporary-directory prefixes now honor the same resolved parent.
- Report data: content-free directory names, Git/worktree metadata, aggregate
  counts, and disposition classes only.

## Safety and privacy checklist

- [x] No real mailbox, provider, vault, credential, legacy LocalData, private
  data, or customer content was read.
- [x] No email send, delete, archive, analysis, or provider action was added.
- [x] Tests use synthetic fixtures and disabled providers only.
- [x] No directory, worktree, Git administrative entry, artifact, stage, or
  failure site is deleted, moved, overwritten, repaired, or cleaned.
- [x] Topology collection is non-recursive and content-free for unrelated and
  private-data-bearing locations.
- [x] No migration, cutover, confirmation, verifier, Issue #38 mutation, or
  Issue #39 action is authorized or executed.

## Pre-execution checklist

- [x] Read `AGENTS.md`, project status, and the required tooling,
  architecture, and linter constraints.
- [x] Read the task-brief rules and template.
- [x] Confirmed the task goal, non-goals, exact five-file allowlist, and public
  test seam with the operator.
- [x] Confirmed no real mailbox, key, private data, LocalData, or customer data
  access is required.
- [x] Confirmed the existing dirty roots, failed sites, registered worktrees,
  and damaged refs are preserve-only.
- [x] Confirmed Superpowers workflows are disabled for this project.

## Design

1. `build_runtime_scenario(directory=...)` treats the supplied directory as the
   sole parent for both `issue57-synthetic-*` scenario owners and the shared
   `issue57-approved-python-source-*` owner.
2. The shared approved-source cache remains process-local and read-only after
   construction. Reuse is allowed only while its parent is identical to the
   first caller-owned parent; a different parent fails closed rather than
   silently escaping or retargeting the cache.
3. The default no-argument behavior uses the current fixture module's Repository
   Root as the caller-owned parent and may not select a drive root, the global
   system temporary directory, or `D:\Projects`.
4. The regression test exercises the public fixture seam with a caller-owned
   parent and proves both Issue #57 prefixes are created only beneath it.
5. The classification report uses directory metadata plus Git/worktree metadata
   only. It records no file content, private identifiers, ACL text, LocalData,
   secrets, or provider/mailbox/vault evidence.

## Acceptance criteria

1. The confirmed public seam test fails on the frozen baseline and passes after
   the fix.
2. The fix removes every drive-root parent selection from the Issue #57 fixture.
3. A supplied caller-owned parent owns both Issue #57 temporary directory
   prefixes.
4. A second different parent is rejected while the process-local shared cache is
   live.
5. The content-free report reconciles every top-level directory in `D:\` and
   `D:\Projects`, plus all registered worktrees, into an explicit
   classification or an unresolved disposition gate.
6. No observed directory or Git administrative state is mutated.
7. Focused tests, full discovery, project-status generation, maintenance scan,
   leakage scan, and dual Standards/Spec review pass before publication is
   proposed.
8. Work stops at the publication and disposition approval boundary.

## Test plan

- `python -B -m unittest tests.test_cutover_managed_activation_fixture_boundaries`
- `python -B -m unittest discover -s tests -p "test_cutover_managed_activation_*.py"`
- `python -B -m unittest discover -s tests`
- `python -B scripts/generate_project_status.py --output docs/operations/project_status_log.md`
- `python -B scripts/maintenance_scan.py`
- repository leakage scan and `git diff --check`

All Python commands use
`D:\Projects\email_ai_assistant\.venv\Scripts\python.exe`. Tests must not access
real LocalData, private data, provider, mailbox, vault, or real cutover surfaces.

## Rollback

Before publication, rollback means reverting only the allowlisted repository
files in this task. Existing directories and worktrees are never rollback
targets. No cleanup command is authorized.

## Manual decisions

- Publishing the implementation requires a separate approval.
- Every directory or worktree disposition requires a separate approval after the
  complete classification is shown.
- Issue #38 closure gates and Issue #39 execution remain separately authorized.

## Completion record

- Actual changed files are exactly the five allowlisted files above.
- RED evidence:
  - explicit caller parent produced one new
    `D:\issue57-approved-python-source-*` directory and no approved-source
    directory below the caller parent;
  - a second different caller parent silently reused the live shared source
    fixture;
  - the no-argument seam created neither Issue #57 prefix below the current
    Repository Root.
- GREEN evidence:
  - three final fixture-boundary tests passed in 18.594 seconds;
  - 76 final managed-activation tests passed in 233.253 seconds;
  - three R2 runtime-publication consumer tests passed in 144.312 seconds;
  - final full discovery ran 2,753 tests in 2,626.838 seconds and passed with three
    skips;
  - project-status generation exited zero; maintenance scan exited zero with
    only the same 19 low stale-document findings; repository leakage scan
    exited zero with no findings; `git diff --check` exited zero;
  - the final documentation, status, mechanical-rule, linter, maintenance, and
    leakage supplemental set ran 95 tests in 27.161 seconds and passed;
  - the current worktree had zero Issue #57 temporary directories after each
    verification, while the historical external counts remained unchanged at
    seven under `D:\` and two under `D:\Projects`.
- Topology classification fingerprint:
  `ff050dfca4c84853276714f0ddc1d999de4000aa2fb140e858d8058249ff26dc`.
- Remaining work: publication and disposition approvals.
