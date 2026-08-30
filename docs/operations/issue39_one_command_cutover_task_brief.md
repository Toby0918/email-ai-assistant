---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Issue 39 one-command Project Container cutover task brief

## 1. Task name

```text
Issue 39 one-command fail-closed Project Container cutover
```

## 2. Task type

```text
security
```

## 3. Current status

```text
in_progress
```

The operator approved design, implementation, synthetic Windows verification,
documentation, status generation, commit, push, PR, CI repair, and merge. Live
incident disposition, closure confirmation, protected verification, and host
cutover remain outside this implementation run and require a later explicit
execution authorization.

## 4. Goal

Implement one fixed-target Windows command that coordinates the existing R2
preflight, evidence, transaction, validation, and recovery contracts for the
canonical Project Container. The command must fail closed, retain every
partial state, and provide a deterministic recovery direction without exposing
an arbitrary path, command, adapter, or cleanup surface.

The fixed Windows wheelhouse now exists create-only at
`D:\Projects\email_ai_assistant-runtime\issue39-wheelhouse`. It contains 31
hash-locked wheels totaling 21,523,533 bytes. The SHA-256 of
`wheelhouse-manifest-v1.json` is
`5709429425f9eab1028157cd81df8638944d686c15b8db7db5bba6f0df9eddc2`.
The manifest binds `requirements-ci-windows.lock`, whose SHA-256 is
`531f8054b8d8d908fe73f6a74ba42bd9b5dfe931b002b81647572c06bf08f8c0`.

A path-only check found the historical 12,288-byte SQLite source at the
previously documented legacy role. Its contents were not opened. Therefore
the conditional first-start empty-database initialization is not applicable;
the existing stopped-service, create-only database migration contract remains
in force.

## 5. Non-goals

- Do not run the real Solo Maintainer closure confirmation or protected verifier.
- Do not run the real incident-stage disposition or Project Container cutover.
- Do not modify Issues 38 or 39, a GitHub ruleset, provider state, mailbox,
  vault, recovery media, private evaluation data, or other private data.
- Do not add force, overwrite, replace, delete, prune, cleanup, path selection,
  alternate target, environment unlock, or caller-supplied adapter options.
- Do not collapse closure confirmation, Issue 38 review, Issue 39 execution
  confirmation, and recovery confirmation into one authority.
- Do not claim that green CI authorizes live execution.

## 6. Basis

- GitHub Issue 39, `Execute the live Project Container cutover`.
- `AGENTS.md`.
- `docs/decisions/0009-project-container-and-repository-boundaries.md`.
- `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md`.
- `docs/operations/project_container_migration_task_brief.md`.
- `docs/constraints/tooling_constraints.md`.
- `docs/constraints/architecture_constraints.md`.
- `docs/constraints/linter_constraints.md`.
- `docs/constraints/ci_guardrails.md`.
- `docs/constraints/mechanical_rule_translation.md`.

The canonical target is fixed at `D:\Projects\email_ai_assistant`; its sole
Repository Root is `main`, with siblings `Runtimes`, `LocalData`,
`RuntimeTemp`, `Logs`, `Artifacts`, `Worktrees`, `Config`, and
`OperatorPrivate`.

## 7. Scope

Expected additions or changes:

- `backend/r2_issue39_orchestrator/`: closed orchestration contracts and state machine.
- A fixed Windows production binder for the canonical Project Container roles.
- `scripts/execute_project_container_cutover.py`: the fixed no-path operator command.
- Exact incident-stage disposition code for the reviewed Issue 38 stage only.
- Existing production roots and production composition allowlists needed for
  Issue 39 reachability.
- Focused portable, architecture, leakage, and test-owned Windows tests.
- Project structure, constraints, ADR, runbook, and generated status records.

## 8. Technical design

### 8.1 Public interfaces

The public operator seam runs only from the code-fixed initial launcher
worktree:

```powershell
Set-Location 'D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement'
& 'D:\Projects\email_ai_assistant\.venv\Scripts\python.exe' -I -B scripts\execute_project_container_cutover.py run
```

It accepts exactly the `run` verb. It accepts no path, target, force, cleanup,
adapter, authorization-file, endpoint, provider, mailbox, vault, or private-data
argument. Unknown or extra input fails before a host capability is acquired.
The wrapper also rejects a current directory or script root other than the
fixed launcher, including the legacy Repository Root and reparse aliases,
before importing the live orchestrator. The existing exact-master and clean
Git readiness then revalidates the launcher checkout.

The incident-stage disposition is not a generic file mover. It recognizes one
code-fixed source leaf, archive leaf, two artifact filenames, byte lengths,
SHA-256 hashes, and DACL transition. It uses DACL-only Windows APIs and one
same-volume no-replace directory move. Failure retains the source or destination
and never deletes, repairs, overwrites, or rolls back content.

The exact retained source/archive leaf is
`.r2-solo-maintainer-closure-v1.incident-794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721`.
The earlier `.stage-794aea72...` spelling is stale historical preparation state
and is not a compatibility alias or accepted production source.

### 8.2 Orchestration seam

One single-use orchestrator owns a closed ordered plan:

1. Validate the fixed invocation without acquiring a host mutation capability.
2. Use only local reads and fixed GitHub GETs to prove the exact closure
   artifacts, current eligible master, Issue 38 closed state, fixed inputs,
   complete linked-worktree roster, and incident-stage state.
3. Validate the visible directly connected Windows console.
4. If the reviewed incident source still exists, obtain its separate fresh
   confirmation and perform only its fixed same-volume no-replace disposition.
5. Recompute the complete preparation after disposition and reject any closure,
   master, Issue 38, input, roster, placement, identity, or cleanliness drift.
6. Build the exact V3 production binding and fixed Adapter catalog.
7. Run current topology, host baseline, and evidence review in fixed order.
8. Publish and independently verify one create-only migration-evidence package.
9. Run evidence verification and final-audit readiness in fixed order.
10. Stop and independently prove the legacy service stopped.
11. Execute the journaled forward transaction through final audit and validation.
12. Perform two fresh terminal observations and emit only
    `PROJECT_CONTAINER_CUTOVER_SUCCEEDED` after the durable success seal.

Each existing Execution Confirmation remains one action, append-before-attempt,
single-use, and bound to the current journal head. The one command guides those
fixed confirmation ceremonies inside one process invocation; it does not turn
one confirmation into umbrella authority.
Before every Issue 39 V3 confirmation, the owning adapter displays one strict
`ISSUE39_CONFIRMATION_CONTEXT_V1` line containing only the closed phase,
operation, command, direction, verified current-state label, and bounded
sequence. The operator enters only the following candidate fingerprint and
fixed acknowledgement. Context display failure stops before confirmation input
or host effect.

### 8.3 Failure and recovery

Before any committed host effect, a failure returns `SAFE_ABORT`. After a
committed effect, the command inspects durable state and either performs only
the separately confirmed fixed rollback plan or returns `INCIDENT_STOP`.
Resume never retries an ambiguous effect. Failed Containers, legacy source,
migration evidence, journals, and the archived incident stage are retained.

### 8.4 Deep-module boundaries

- Orchestrator contracts contain only closed content-free values.
- The state machine knows order and status, not paths or host APIs.
- The fixed production binder is the sole owner of canonical paths and host capabilities.
- Incident disposition is a separate narrow adapter and cannot enumerate or
  accept arbitrary siblings.
- Provider, mailbox, vault, private-data, cleanup, and GitHub mutation modules
  are unreachable from the command graph.

### 8.5 Ticket-sized implementation slices

1. Closed orchestration vocabulary and zero-capability gate.
2. Fixed incident-stage contract and Windows test-owned adapter.
3. Closure and Issue 38 readiness bridge.
4. Production binding, confirmation, and Adapter dispatch wiring.
5. Fixed canonical host binder and forward transaction.
6. Durable restart classification and separately confirmed recovery.
7. CLI, architecture/leakage guards, runbook, and status integration.

Every slice follows red, green, refactor and keeps the public seams above stable.

### 8.6 Durable confirmation ledger

The Issue 39 ledger is a create-only directory of sequential, hash-named R2
journal frames. Each frame is written with exclusive creation, flushed, read
back, and byte-compared before a later frame or host action is allowed. Reopen
sorts the bounded namespace, requires an exact sequence with no extra entry,
reconstructs the complete `R2TransactionJournalV2`, and verifies every stored
head. A collision, malformed frame, missing frame, extra frame, prefix drift,
or binding mismatch retains all bytes and returns `INCIDENT_STOP`.

The action runner persists the fresh single-use Execution Confirmation claim
and `INTENT` before it calls the bound action. It persists observation and
commit frames after exact stable post-state observation; those two frames carry
the same canonical actual-effect evidence fingerprint, including validation
service identity/nonce, rule result/row, provider count, database proof, and
audit evidence. A persistence failure
therefore has zero action calls before the effect, while a post-effect crash is
classified from two stable reads and committed with a fresh `resume`
confirmation without repeating the effect. Exact pre-effect failure uses the
same classification and a fresh confirmation; ambiguity always stops.
The same rule applies to reverse effects before their rollback marker. A
retained legacy-recovery intent remains bound to its pending transition across
a fresh resume claim and cannot be replaced by the new claim token.

### 8.7 Fixed production action catalog

The catalog has no registration or caller-selected dispatch surface. It binds
six foundation actions, one reconstruction action for every worktree in the
fresh complete roster, eight managed-unit prepare/publish actions, and seven
two-start validation actions. The portable six-worktree synthetic baseline is
exactly 27 actions; the 2026-08-29 read-only live roster had 14 linked
worktrees and would derive 35 actions. Each catalog item binds sequence, phase,
command, host-effect
classification, implementation key, and distinct pre/post state fingerprints
to the fresh preparation fingerprint.

Rollback walks only the durable committed catalog prefix in reverse order.
Every reverse action has its own fresh `rollback` confirmation and durable
intent, moves the synthetic active object no-replace to a retained rollback
object, and never deletes or cleans it. The Windows tests cover full success,
pre-effect and post-effect restart, partial failure with LIFO rollback,
collision, preparation drift, and ledger-write failure before action dispatch.

## 9. Data and API changes

### Database changes

No schema change. The historical SQLite source exists, so the existing
stopped-service, absent-sidecar, create-only LocalData publication remains
authoritative. No empty first-start database is introduced.

### HTTP API changes

None.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real mailbox or private data is read during implementation or tests.
- [x] No email is sent, deleted, or archived.
- [x] Providers remain disabled and no key crosses the operator seam.
- [x] Public outputs are fixed and content-free.
- [x] Tests use anonymous values and test-owned temporary Windows directories.
- [x] Real incident disposition and cutover remain separately authorized.

## 11. Prompt injection protection

Not applicable. The command accepts no email or model input and calls no provider.

## 12. Acceptance criteria

1. The script has one fixed `run` verb and no arbitrary path or force surface.
2. Missing closure eligibility, open Issue 38, wrong master, stale confirmation,
   retained unexpected stage, or any drift stops before host mutation.
3. The exact nine-zone layout and `main` repository placement are code-fixed.
4. Incident disposition accepts only the exact reviewed stage and preserves it
   at the exact archive destination with exact artifacts and final DACL.
5. Six preflight reads, one evidence publication, and the transaction plan run
   only in the reviewed order with a fresh single-use confirmation per action.
6. Service quiescence precedes SQLite and directory mutation.
7. Repository identity, the fresh bounded complete linked-worktree roster,
   Runtime, LocalData, CRX, Config, provider-disabled activation, two-start
   validation, and final audit all bind the terminal success seal. The portable
   synthetic baseline contains six linked worktrees: two embedded and four
   external. Production always uses the fresh complete roster; the 2026-08-29
   read-only live observation contained 14 linked worktrees.
   Every worktree is bound by exact placement, Git identity, physical identity,
   administrative identity, branch, commit, common directory, and clean-status
   fingerprints. Any addition, removal, dirtiness, or identity drift after
   prepare stops before the next host effect.
8. Failure is classified as safe abort, rollback required, or incident stop;
   there is no cleanup or ambiguous automatic retry.
9. Portable tests exercise contracts only. Windows tests mutate and clean up
   only their own synthetic temporary directories.
10. Full unit tests, maintenance scan, leakage scan, mechanical constraints,
    documentation checks, and hosted CI pass before merge.

## 13. Test plan

- Focused orchestrator contract, state-machine, CLI, architecture, and leakage tests.
- Windows incident-stage DACL/move tests in a test-owned temporary directory.
- Windows end-to-end success, each fixed failure boundary, crash/restart,
  rollback, collision, reparse, drift, and retained-state tests.
- Existing R2 production binding, Adapter, composition, publication, recovery,
  closure, verifier, and obsolete-surface suites.
- `python -m unittest discover -s tests`.
- `python scripts/maintenance_scan.py`.
- `python scripts/leakage_scan.py`.

On Windows these commands must use the project Python 3.12.13 executable at
`D:\Projects\email_ai_assistant\.venv\Scripts\python.exe`. A different Python
3.12 patch release correctly fails the pinned Runtime source-manifest check.

## 14. Rollback plan

Code rollback is the normal Git revert of this single-purpose change. Live host
rollback is never inferred from code rollback: it uses only the journal-derived
reverse plan, fresh recovery confirmation, no-replace transitions, retained
failed Container, and final legacy health verification.

## 15. Human confirmation questions

None for implementation. The operator has approved the scope above. A later
explicit authorization is still required to execute incident disposition,
closure confirmation, protected verification, or the real cutover.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md` from the exact LF worktree.
- [x] Read the current project status and governing constraint documents.
- [x] Confirmed the task goal, non-goals, and fixed public seams.
- [x] Confirmed no real mailbox, provider, vault, private data, or host cutover is in scope.
- [x] Confirmed all executable tests own their temporary objects.

## 17. Repository placement and operational layout checklist

- [x] Managed mode remains the exact `email_ai_assistant\main` relationship.
- [x] The nine top-level roles are fixed and no third placement mode is added.
- [x] Public CLI, environment, and configuration cannot select paths or protected roots.
- [x] Container audit remains content-free and fail-closed.
- [x] Publication is create-only and every partial state is retained.
- [x] No cleanup, provider, mailbox, vault, private-store, or private-data capability is added.
- [x] Receipts remain evidence and never become authority.
- [x] Real execution requires fresh closure, Issue 38, and Issue 39 gates.
