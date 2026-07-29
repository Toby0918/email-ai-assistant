---
last_update: 2026-07-28
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 56 reversible repository and worktree transaction task brief

## 1. Task name

```text
Issue #56 reversible mixed-topology repository and worktree transaction
```

## 2. Task type

```text
security
```

## 3. Current status

```text
in_progress
```

## 4. Goal

Implement the bounded Issue #56 forward and reverse transaction from exact
remote `master@96fceda6e85316dd6b17ef516adf96491d28cb6d`. The executable proof
must run only in a caller-owned synthetic Windows sandbox, preserve the
original Repository Root plus exactly eleven reviewed worktrees and their
opaque Git administrative entries, publish the reviewed mixed topology without
clobbering, and restore every original physical and administrative identity
from durable content-free journal evidence.

## 5. Non-goals

- Do not read, move, repair, clean, or modify the real Repository Root, any
  existing worktree, real Git administrative record, service, ACL, Runtime,
  SQLite database, provider, mailbox, vault, private store, or private data.
- Do not add a real cutover command, CLI, HTTP route, scheduler, workflow,
  arbitrary path/ref/Git command surface, or authorization issuer.
- Do not make clone, repository copy, fetch, reset, stash, prune, worktree
  remove, worktree repair, deletion, replacement, alternate-target selection,
  or cleanup available to the transaction.
- Do not modify or close Issues #38/#39, parent Spec #50, or implement Issues
  #57 through #59.
- Do not merge the resulting pull request.

## 6. Background and references

- GitHub Issue #56, parent Spec #50, and closed prerequisite #55.
- `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- `docs/decisions/0009-project-container-and-repository-boundaries.md`.
- `docs/security/project_container_cutover_contracts.md`.
- `docs/operations/project_container_migration_task_brief.md`.
- Issue #51 through #55 task briefs and their existing contract, journal,
  preflight, evidence, and filesystem seams.
- Tooling, architecture, linter, mechanical, CI, documentation, testing, and
  maintenance constraints.

The root workspace contains user-owned dirty state and many existing
worktrees. This task uses only the clean sibling worktree
`D:\Projects\email_ai_assistant_issue_56_repository_transaction` on
`codex/issue-56-repository-transaction`.

## 7. Scope

Expected additions:

- `backend/cutover_repository_transaction/` for closed values, durable
  content-free journal records, fixed Git discovery/recreation, opaque
  administrative preservation, synthetic forward/reverse composition, exact
  verification, and the locked real constructor.
- Focused `tests/test_cutover_repository_transaction_*.py` modules and
  synthetic Windows fixtures.
- This task brief.

Expected synchronized changes:

- Exact Issue #56 architecture, tooling, static, mechanical, CI, security,
  decision, project-structure, status, testing, and leakage contracts.
- The project-status generator and generated status log.

No frontend, provider, mailbox, vault, private-knowledge, private-evaluation,
normal-runtime, service, Runtime/data/artifact, dependency, or cleanup code is
in scope.

## 8. Technical approach

### 8.1 TDD public seams

Tests observe only these Issue-approved seams:

1. a closed synthetic roster contract with exactly eight embedded and three
   external reviewed worktrees;
2. an opaque caller-owned Windows sandbox transaction scope that cannot be
   constructed from an arbitrary path through the public package;
3. `run_forward_synthetic_transaction(...)`, accepting only that scope and a
   fixed crash/failure selector;
4. `run_reverse_synthetic_transaction(...)`, deriving restoration work only
   from verified durable journal and observed sandbox state;
5. strict content-free journal records and forward/reverse receipts;
6. the default-locked real transaction constructor.

Each vertical slice is one public failing test, minimal implementation, and
focused GREEN. Git and Windows filesystem APIs are system boundaries; only the
private test-sandbox binder may supply their concrete path bindings and
deterministic race/crash cut points.

### 8.2 Reviewed mixed topology

The bound sandbox contains one existing Repository Root plus exactly eleven
clean linked worktrees. Roles `worktree_01` through `worktree_08` are embedded;
roles `worktree_09` through `worktree_11` are external. Every role binds one
placement, original physical identity, target parent/leaf, reviewed ref and
commit, clean state, Git common-directory identity, administrative-entry
identity/fingerprint, and preservation role.

Git discovery is fixed and read-only. The Git executable version, full bounded
binary-content digest, and opened binary identity are reduced to one
profile-bound fingerprint. Each execution holds a handle that denies write
sharing, then revalidates the identity and content before and after use. Each
administrative entry is located by the verified relationship returned by Git,
must be one direct child of the reviewed common-directory worktree namespace,
is fingerprinted as opaque bounded bytes, and is moved without parsing or
editing its contents.

### 8.3 Forward boundaries

The fixed forward boundaries are:

1. `source_frozen`;
2. `worktrees_preserved`;
3. `legacy_renamed`;
4. `container_published`;
5. `non_main_zones_published`;
6. `main_published`;
7. `worktrees_recreated`;
8. `repository_final_verified`.

Every original physical worktree is moved no-replace to its same-volume
preservation role before any counterpart is created. Every original
administrative entry is moved no-replace out of the live namespace. The
original Repository Root object is first renamed to the reviewed legacy role,
then moved by same-volume identity-preserving relocation into `main`; it is
never cloned or copied.

The Container and eight non-main zones are create-only. The Container-create
COMMITTED record retains the actual #55 object identity; unchanged
ContainerAudit policy receives that identity as its trusted cross-domain
selection and requires exact equality with the freshly observed Container.
Clean recreation uses
only the reviewed ref and commit and must create exactly one fresh physical
counterpart plus one live administrative entry per worktree. Targets are
reserved/create-only and identity-bound before the fixed `git worktree add`
operation; any collision, reparse, race, volume/ref/dirty/admin drift, extra
worktree, or unexpected Git layout fails closed.

### 8.4 Durable journal ordering

The transaction journal lives only inside the bound sandbox. Records use
strict canonical create-only files, exact sequence and hash chaining, and
closed direction/boundary/mutation/event values. Every physical move,
administrative move, directory publication, and Git worktree recreation has a
durable `INTENT` before the effect, an exact observed identity record after the
effect, and a `COMMITTED` record only after an independent stable reread
matches OBSERVED exactly. Administrative rereads bind identity plus opaque
content; Git rereads repeat the reviewed relationship/ref/commit/clean-state
observation.

When an explicit reverse request encounters a safely classifiable incomplete
forward action, exact before-effect state appends `ABORTED/NOT_APPLIED`; exact
after-effect state appends only the missing `OBSERVED` and/or `COMMITTED`
facts. Neither path replays the effect. Ambiguous state remains
`INCIDENT_STOP`.

Records, receipts, stdout, stderr, logs, errors, and repr expose no path,
worktree/ref/object/admin name, Git command, administrative bytes, native
error, exception, or content. Only fixed status/boundary values, opaque
fingerprints, and bounded counts are allowed.

### 8.5 Reverse and crash classification

Reverse starts only from a verified journal prefix and current observation,
including every complete forward boundary and each safely classified forward
crash gap.
It preserves the new Container, new worktree physical state, and new Git
administrative entries as failed evidence before restoring any original
object. It then extracts the original `main` identity to the original canonical
Repository Root, restores all original opaque administrative entries and all
eleven original physical identities, and verifies the exact original topology.

Committed forward boundaries reverse in strict LIFO order. A crash before
effect is `SAFE_ABORT` for that mutation; exact expected-after observation may
complete the missing observed/committed facts without replay; ambiguous,
drifting, corrupt, or unclassifiable state is `INCIDENT_STOP`. Reverse has the
same intent/effect/observed/committed crash coverage and never guesses, repairs,
deletes, or overwrites. An explicitly repeated reverse call may resume only
after exact stage-specific safe classification, retained-failed-evidence
verification, and checkpoint verification, and executes only the remaining
fixed mutations. Failed-evidence verification occurs before any resumed
mutation; no background or ambiguous resume exists.

### 8.6 Existing seams and real lock

Windows moves and create-only directories consume the exact Issue #52 durable
INTENT permit through Issue #55 handle-bound no-replace primitives. Final
forward verification uses unchanged ContainerAudit filesystem, Git, and
embedded-worktree validators for the actual nine-zone synthetic metadata;
the three external worktrees remain under the separate exact #56 Git topology
verification. Final reverse also applies the unchanged object-policy seam to
the journal-bound retained failed Container identity and inventory. Final
forward and reverse Git verification also compare all non-intentional reviewed
selections, including local refs and remote configuration. This does not
fabricate a full host audit
or Issue #57 Runtime evidence. Final reverse verification independently proves
the original Git/worktree inventory and identities.

The real transaction constructor validates only exact
`CutoverExecutionAuthorizationV1` context and still returns
`BLOCKED_NO_APPROVED_COMMAND` before Issue #39. Missing, test, wrong-phase, and
malformed authorization remain blocked.

## 9. Data structure or interface changes

### Database changes

None.

### API changes

Internal synthetic-only Python contracts and a locked real constructor. No
HTTP, CLI, browser, service, or scheduled entry point.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real repository, worktree, administrative record, ACL, service,
  Runtime, SQLite, provider, mailbox, vault, private store, or private data is
  accessed by the transaction.
- [x] Every executable mutation is confined to a caller-owned synthetic
  Windows sandbox.
- [x] The roster is exactly eight embedded plus three external reviewed
  worktrees.
- [x] Paths, refs, commits, Git names, administrative bytes, commands, and
  exceptions never cross the public boundary.
- [x] Every physical/administrative mutation requires durable INTENT first.
- [x] No replace, repair, delete, clone, copy, fetch, reset, stash, prune, or
  cleanup capability is added.
- [x] Providers remain disabled and no network capability is added.

## 11. Prompt injection protection

Not applicable to email or AI input. Git output, filenames, refs,
administrative bytes, profile values, journal bytes, and observations are all
untrusted. They are accepted only through closed schemas, fixed parsers, exact
relationships, and opaque fingerprints; none is interpreted as an arbitrary
command or instruction.

## 12. Acceptance criteria

1. Every Issue #56 acceptance criterion is covered by a focused executable
   test or exact mechanical guard.
2. The complete synthetic roster is exactly eight embedded and three external
   worktrees, all clean and bound to reviewed ref/commit/common/admin/physical
   identities.
3. All eight forward boundaries and their reverse boundaries pass, including
   exact original Repository Root identity relocation to `main`.
4. Every original physical worktree and opaque administrative entry is
   preserved no-replace before counterpart creation.
5. Every physical/admin mutation has durable INTENT, exact observed identity,
   and COMMITTED records; safe crash gaps reconcile without blind replay.
6. Target collision, reparse, volume, ref, dirty, Git executable, worktree,
   administrative layout/name reuse, identity drift, race, and unexpected
   extra-worktree cases fail closed without clobbering.
7. Reverse preserves the complete new failed state and restores the original
   Repository Root, Git administrative entries, and all eleven physical
   worktree identities.
8. Journal, receipts, results, repr, stdout, stderr, and logs remain
   content-free.
9. The real constructor remains locked without an exact execution
   authorization and before a later approved Issue #39 command.
10. Windows sandbox, focused, affected, full, constraints, compile, frontend
    syntax, manifest, leakage, maintenance, diff, and dual-axis review gates
    pass.

## 13. Test plan

- TDD vertical slices: contracts/roster; sandbox binding; Git discovery and
  executable binding; durable journal; physical/admin preservation; Container
  and zones; main relocation; clean worktree recreation; forward verification;
  reverse restoration; crash matrices; race/drift/collision; real lock;
  architecture/leakage.
- Run the focused Issue #56 suite after every slice.
- Run affected Issue #51 through #55, ContainerAudit, reparenting,
  architecture, static, mechanical, status, documentation, transport,
  leakage, and maintenance tests.
- Run `python -B -m unittest discover -s tests`.
- Run `python -B -m compileall -q backend scripts tests`, every frontend
  JavaScript file through `node --check`, and parse the extension manifest.
- Regenerate the project status, rerun full tests and maintenance, then perform
  parallel Standards and Spec review from the exact fixed point.

## 14. Rollback plan

Before publication, remove or repair only Issue #56 allowlisted files in this
isolated worktree. Tests retain their synthetic failed state until independent
assertions and then dispose only the caller-owned sandbox parent. No real host
state exists to reverse. After publication, a normal Git revert of the Issue
#56 commit is sufficient.

## 15. Questions requiring human confirmation

None. Issue #56 and this request fix the synthetic seams and safety boundaries.
Any real command composition, real authorization issuance, Runtime/data/
artifact work, service activation/recovery, Issue #57 through #59, cleanup, or
merge needs separate approval.

## 16. Pre-execution checklist

- [x] Read `$implement`, `$tdd`, `$code-review`, and GitHub workflow rules.
- [x] Read `AGENTS.md`, `CONTEXT.md`, status, task-brief, tooling,
  architecture, linter, mechanical, CI, security, and decision rules.
- [x] Live-verified Issue #56, parent #50, closed blocker #55, and the exact
  remote master.
- [x] Inventoried and preserved the dirty root and every existing worktree.
- [x] Created a clean sibling worktree and `codex/` branch from the exact SHA.
- [x] Fixed the TDD public seams and confirmed no real host/private capability
  is required.

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

- [x] No real Repository Root, worktree, Container, service, Runtime, SQLite,
  ACL, or production directory is accessed or changed.
- [x] Exact sandbox authorization and opaque bindings prevent arbitrary path,
  ref, administrative, or Git command mutation.
- [x] The original Repository Root becomes `main` only by same-volume,
  identity-preserving relocation.
- [x] Every worktree physical/admin object and every new target is no-clobber.
- [x] Reverse preserves failed evidence before exact restoration.
- [x] The real constructor remains blocked before later composition approval.
- [x] Issues #57 through #59, #38/#39, and parent #50 remain unchanged.

## 22. Post-execution record

Implementation and local verification are complete in the isolated
`codex/issue-56-repository-transaction` worktree. No transaction read or
mutated the real Repository Root or any pre-existing worktree.

- Focused Issue #56 Windows sandbox suite: 48 tests passed in 2016.558
  seconds.
- Affected #51-#55, ContainerAudit, evidence, reparenting, preflight, status,
  and transport suite: 430 tests passed in 407.013 seconds with one expected
  skip.
- Dedicated architecture/static/mechanical/status/transport suite: 159 tests
  passed in 36.726 seconds.
- Full verified-runtime suite: 2230 tests passed in 2413.633 seconds with
  three expected skips.
- Python compile, every frontend JavaScript syntax check, extension manifest
  parsing, repository leakage scan, and the read-only maintenance scan passed;
  the maintenance scan reported no findings.
- Standards re-review has no P1/P2 and Spec re-review has no P1/P2/P3.
  Standards recorded one non-blocking P3: `reverse.py` obtains
  `verify_resume_checkpoint` through the importing `reverse_resume.py` module
  rather than directly from `reverse_checkpoint.py`. Per Issue #56 scope, it
  is recorded without expanding this change.
- Remote publication remains pending at this record point. Merge, parent Spec
  closure, and Issues #57-#59 remain unauthorized.
