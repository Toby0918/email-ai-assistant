---
last_update: 2026-07-28
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 55 fixed-role Windows ACL and filesystem primitives task brief

## 1. Task name

```text
Issue #55 fixed-role Windows ACL and no-clobber filesystem primitives
```

## 2. Task type

```text
security
```

## 3. Current status

```text
ready_for_review
```

## 4. Goal

Implement the bounded Issue #55 primitive layer on remote
`master@34cc9b614a6b3b5c2d21e76bdfd74fe28c78aebc`. Prove direct-Windows-API,
fixed-role ACL handling and handle-bound, identity-preserving, no-replace
filesystem mutation inside a test-owned NTFS sandbox. Every effect must consume
an already durable Issue #52 journal INTENT and return a content-free
observation suitable for the observed and committed journal records.

## 5. Non-goals

- Do not run a real Project Container ACL operation, filesystem mutation,
  cutover, rollback, recovery, service operation, Runtime build, SQLite copy,
  repository/worktree move, or artifact publication.
- Do not access or modify the root workspace, another worktree, the finance
  project, a production path, a real service, mailbox, provider, vault,
  private store, credential, browser profile, or private data.
- Do not add an arbitrary path, command, ACL, principal, policy, shell, script,
  transcript, repair, delete, replace, retry-at-another-target, or recursive
  normalization surface.
- Do not invoke or construct `icacls`, PowerShell, a command shell, or a
  replayable ACL transcript.
- Do not modify Issue #38 or #39, implement Issues #56 through #59, merge the
  pull request, or close parent Spec #50.

## 6. Background and references

- GitHub Issue #55 and parent Spec #50.
- Closed prerequisites Issues #52 and #53.
- `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- `docs/decisions/0009-project-container-and-repository-boundaries.md`.
- `docs/security/project_container_cutover_contracts.md`.
- `docs/operations/project_container_migration_task_brief.md`.
- Issue #51 through #54 task briefs.
- Tooling, architecture, linter, mechanical, CI, documentation, testing, and
  maintenance constraints.

The root workspace has user-owned dirty state and existing worktrees. This task
uses only the clean sibling worktree
`D:\Projects\email_ai_assistant_issue_55_acl_filesystem` on
`codex/issue-55-acl-filesystem`.

## 7. Scope

Expected additions:

- `backend/cutover_host_mutation/` for portable contracts, fixed receipts,
  Windows ACL capture/apply/verify, sandbox-bound filesystem primitives,
  authorization locks, and fixed failures.
- Focused `tests/test_cutover_host_mutation_*.py` modules and synthetic
  fixtures.
- This task brief.

Expected synchronized changes:

- Exact Issue #55 architecture, static, mechanical, leakage, documentation,
  testing, project-structure, and status contracts.
- The project-status generator and generated status log.

No frontend, provider, mailbox, vault, private-knowledge, private-evaluation,
normal-runtime, service wrapper, dependency, or workflow code is in scope.

## 8. Technical approach

### 8.1 TDD public seams

Tests observe only the Issue-approved seams:

1. fixed-role ACL descriptor capture and exact comparison;
2. complete source-tree ACL compatibility observation;
3. new-empty-Container ACL policy application;
4. fixed-zone inheritance verification;
5. create-only directory publication;
6. same-identity no-replace file/object publication;
7. four closed ACL receipt types;
8. the default-locked real mutation constructor.

Each slice follows one public failing test, minimal implementation, and focused
GREEN. Windows system APIs, time, and deterministic race cut points are system
boundaries and may be injected only through private test factories.

### 8.2 Fixed-role ACL boundary

The ACL adapter is constructed with exact source, parent, finance, new
Container, and eight fixed new-zone bindings. Its public operations accept no
path, SID, SDDL, account, command, or arbitrary policy input. Parent and finance
are capture-and-compare roles only; the sole apply operation is hard-bound to
the newly created empty Container.

Capture uses opened handles and direct Windows security APIs. Raw token SID,
security descriptor, DACL, and canonical SDDL exist only in the shortest local
native context and are immediately projected to SHA-256 fingerprints. Public
values contain no path, SID, SDDL, account, native error, or exception detail.

Container creation atomically installs a protected construction DACL with one
non-inheritable current-operator ACE. Its fixed access mask permits only list,
traverse, read attributes, read control, write DAC, and synchronize; it omits
add file, add subdirectory, and delete child. Root, marker, parent, and target
handles remain held by the single-use guarded claim until the final ACL effect.
The exact final Container DACL is protected and contains only inheritable Full
Control allow ACEs for the current token user, LocalSystem, and built-in
Administrators. `SetSecurityInfo` runs through the held target handle and is
mechanically limited to DACL plus protected DACL security-information flags;
owner, group, and SACL pointers are always null. Owner and group are captured
and compared before and after. The absence of owner, group, and SACL flags is
the executable proof that the final operation cannot modify those portions.

### 8.3 Source compatibility and inheritance

The source tree is read-only, bounded, complete, and observed twice. Reparse
objects, protected existing DACLs, incomplete or drifting inventory, and
descriptor fingerprints outside the reviewed content-free compatibility policy
fail closed. No existing object receives ACL apply or recursive normalization.

After the Container policy is applied, the eight fixed new zones are created
create-only and verified as direct children. Each must have only the three
expected inherited Full Control ACEs, an unprotected DACL, the exact parent
identity and volume, and no reparse state.

### 8.4 Filesystem mutation primitives

Each primitive is an immutable, construction-time path binding within one
test-owned sandbox. Operations accept no runtime path:

- create one absent directory under an opened stable parent;
- publish one bound file no-replace;
- move one bound file or directory no-replace while preserving identity.

The primitives hold the approved root, marker, source, and parent handles
across the effect, reject reparse components, aliases, cross-volume state,
target appearance, source or parent identity drift, and any pre-existing
target. Directory creation calls `NtCreateFile` with the approved parent handle
as `RootDirectory`, one fixed path component, and `FILE_CREATE`. Windows
publication sets no-replace and verifies the original 128-bit file ID and
volume at the new role. No primitive repairs, removes, replaces, or selects an
alternate target.

### 8.5 Journal ordering

Every mutation method requires both the exact Issue #52 `JournalRecordV1`
INTENT and its store-issued durable permit. The permit is consumed before the
native effect. The method verifies its pre-bound before/expected-after
fingerprints and returns a pathless observation containing the journal effect
fingerprint plus actual object/parent/volume/identity proof fingerprints.

### 8.6 Authorization and sandbox lock

Windows integration is available only through a package-private constructor
bound to an exact, unexpired `TestSandboxAuthorizationV1`, a marker, and one
caller-owned temporary NTFS root. Original and resolved scope, root/marker
identity, parent relationships, volume, and reparse state are revalidated on
every effect.

The real mutation constructor returns a fixed blocked result without an exact
`CutoverExecutionAuthorizationV1`, explicitly rejects test authorization, and
still exposes no real path or mutation capability before a later approved
composition ticket.

## 9. Data structure or interface changes

### Database changes

None.

### API changes

Internal Python contracts and Windows test-sandbox composition only. No HTTP,
CLI, browser, service, or scheduled entry point.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real mailbox, provider, vault, private data, service, Runtime,
  database, repository, worktree, or production path is accessed.
- [x] Windows effects are confined to a caller-owned temporary NTFS sandbox.
- [x] ACL work uses direct Windows APIs and creates no command or transcript.
- [x] Parent and finance have no apply capability.
- [x] Existing trees are capture-and-compare only and never normalized.
- [x] Public values contain only fixed statuses, fingerprints, and bounded
  allowlisted counts.
- [x] Every effect consumes a durable journal INTENT before mutation.
- [x] Providers remain disabled and no network capability is added.

## 11. Prompt injection protection

Not applicable to email or AI input. All profile, authorization, receipt,
fingerprint, role, and journal values are untrusted and require exact nominal
types and closed schemas. No string is interpreted as a command, path override,
principal, ACL transcript, script, exception, or free-form instruction.

## 12. Acceptance criteria

1. Every Issue #55 acceptance criterion is covered by an executable focused
   test or a fixed mechanical guard.
2. Windows ACL tests prove token SID binding, protected construction guard,
   child-insertion exclusion, exact final DACL, owner/group equality, no SACL
   apply capability, parent/finance equality, source reparse/incompatibility
   rejection, and exact fixed-zone inheritance.
3. Windows filesystem tests prove opened-handle identity, parent identity,
   handle-relative `FILE_CREATE`, ancestor/reparse/target races, identity
   drift, cross-volume rejection, no-replace, no-clobber, and same-file-ID
   publication.
4. Directory/file create-only operations reject every existing target and
   perform no repair, removal, replacement, or alternate selection.
5. Each mutation rejects a missing, forged, replayed, wrong-action, or
   non-durable journal permit and returns an observation on success.
6. `AclBaselineReceiptV1`, `AclCompatibilityReceiptV1`,
   `AclApplyReceiptV1`, and `AclPostVerifyReceiptV1` are closed,
   content-free, repr-redacted values with fixed failure codes.
7. Linux runs portable contract and injected primitive tests without claiming
   Windows ACL, NTFS, or native-handle evidence.
8. The real constructor rejects test authorization and remains blocked without
   a real execution authorization and later approved command composition.
9. Focused, affected, full, constraints, compile, frontend syntax, manifest,
   leakage, maintenance, diff, and dual-axis review gates pass.

## 13. Test plan

- TDD vertical slices: portable values and receipts; journal-gated portable
  primitive; Windows token/descriptor capture; Container apply; source
  compatibility; inheritance; create-only directory; no-replace move/file
  publication; race/drift/cross-volume; authorization; architecture/leakage.
- Run the focused Issue #55 suite after every slice.
- Run affected cutover contracts, journal, preflight, ContainerAudit,
  migration-publication, architecture, static, mechanical, status,
  documentation, transport, leakage, and maintenance tests.
- Run `python -B -m unittest discover -s tests`.
- Run `python -B -m compileall -q backend scripts tests`, every frontend
  JavaScript file through `node --check`, and parse the extension manifest.
- Regenerate the project status, rerun full tests and maintenance, then perform
  parallel Standards and Spec review from the exact fixed point.

## 14. Rollback plan

Before publication, remove or repair only the Issue #55 allowlisted source,
tests, and documentation in this isolated worktree. Test temporary directories
are automatically removed. No real host state exists to reverse. After
publication, a normal Git revert of the Issue #55 commit is sufficient.

## 15. Questions requiring human confirmation

None. Issue #55 and this request fix the seams and safety boundaries. Any real
command composition, real authorization issuance, repository/worktree move,
Runtime/data/artifact work, service activation/recovery, Issue #56 through #59,
or cleanup needs separate approval.

## 16. Pre-execution checklist

- [x] Read `$implement`, `$tdd`, and `$code-review` skill rules.
- [x] Read `AGENTS.md`, `CONTEXT.md`, status, task-brief, tooling,
  architecture, and linter rules.
- [x] Live-verified Issue #55, parent #50, and closed blockers #52/#53.
- [x] Verified remote `master` exactly matches the requested SHA twice.
- [x] Inventoried and preserved the dirty root and all existing worktrees.
- [x] Created a clean sibling worktree and `codex/` branch from the exact SHA.
- [x] Fixed the TDD seams and confirmed no real host/private capability is
  required.

## 17. Remote provider private-context checklist

Not applicable. Provider input, runtime knowledge, budgets, routes, and public
schemas are unchanged. All providers remain disabled.

## 18. Administrator stage-evaluation checklist

Not applicable. No private-evaluation staging surface is imported or invoked.

## 19. Final dataset build and interactive judge checklist

Not applicable. No dataset, provider judge, TTY workflow, or report is opened.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. Mailbox synchronization and current-click evidence remain
unchanged.

## 21. Repository placement and operational layout checklist

- [x] No real repository, worktree, Container, service, Runtime, SQLite, ACL,
  or production directory is accessed or changed.
- [x] Fixed-role bindings and test-sandbox authorization prevent arbitrary
  path mutation.
- [x] Parent and finance remain capture-and-compare only.
- [x] Existing trees are not recursively normalized.
- [x] Create-only and no-replace behavior never repairs or deletes a target.
- [x] The real constructor remains blocked before later composition approval.
- [x] Issues #56 through #59, #38/#39, and parent #50 remain unchanged.

## 22. Post-execution record

Implementation was completed in the isolated
`codex/issue-55-acl-filesystem` worktree from exact remote
`master@34cc9b614a6b3b5c2d21e76bdfd74fe28c78aebc`. Commit `3f220e0`
introduced the fixed-role ACL and no-clobber primitives; commit `b315742`
closed the review-discovered race and failure-boundary gaps.

The first Spec review found two P1 issues: directory creation was not
parent-handle-relative, and the empty-directory check could race with child
insertion before final ACL apply. The repair now uses
`NtCreateFile(FILE_CREATE)` relative to a held parent handle with a protected
construction DACL that grants no add-file, add-subdirectory, or delete-child
right. Root, marker, parent, and target handles remain held through a
single-use guarded claim; the DACL-only `SetSecurityInfo` is the final
linearization point. Ancestor replacement, child insertion, ordinary claim,
and replayed claim tests cover the boundary.

The first Standards review found two P2 issues: some public operations could
leak dynamic native failures, and the sandbox marker could be selected as a
publication source. The repair wraps each complete public native operation in
the fixed content-free error boundary, rejects the marker as a source, holds
root/marker/source/parent handles, and revalidates the sandbox anchors after
the effect. Source reparse points are captured without traversal and rejected;
fixed zones must be the exact eight non-reparse direct children of the held
Container.

Parallel re-review of the complete baseline-to-HEAD diff passed both axes with
no P1, P2, or P3 findings. Local validation after the repair completed as
follows:

- Issue #55 focused Windows/portable/contract/architecture tests: 47 passed.
- Affected `test_cutover_*` tests: 168 passed.
- Affected `test_real_host_preflight*` tests: 62 passed.
- Architecture/static/mechanical/leakage/status/transport constraints: 164
  passed.
- Status-generator and mailbox-transport pin tests: 43 passed.
- Full verified-root-environment suite: 2,181 passed in 305.058 seconds with
  three expected skips.
- `compileall`, ten frontend `node --check` runs, extension manifest parsing,
  `git diff --check`, project-status regeneration, and the read-only
  maintenance scan all passed; the maintenance scan reported no findings.

One earlier full-suite attempt used the dependency-incomplete system Python
and produced import errors for pinned project packages such as `bs4` and
`openai`; that environment-invalid run is not test evidence. The authoritative
full run used the root repository's verified Python 3.12.13 environment, with
SQLite 3.50.4, beautifulsoup4 4.15.0, and openai 2.45.0.

All Windows mutations remained inside caller-owned temporary NTFS sandboxes.
No real ACL, repository, worktree, service, Runtime, SQLite, provider, mailbox,
vault, private store, private data, Issue #38/#39 state, or parent Spec #50
state was accessed or modified.
