---
last_update: 2026-09-04
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Protected verifier materialized maintenance fix task brief

## 1. Task name

Repair Solo Maintainer Closure maintenance observation in the protected
verifier's Gitless materialized repository.

## 2. Task type

```text
bugfix
```

## 3. Current status

```text
merged_with_generated_status_forward_correction_worktree_only
```

## 4. Goal

Make the private closure adapter reuse the exact repository root and sorted
tracked-path tuple already carried by its verified `RepositorySnapshotV1` when
collecting stable maintenance evidence. Preserve the ordinary parameterless
maintenance interface and all closure schemas, fingerprints, eligibility rules,
and public entry points.

## 5. Diagnosed failure

The protected verifier reconstructs the selected master tree without `.git`.
The closure adapter discarded the verified tracked-path tuple and called the
parameterless maintenance observation, whose leakage scan attempted
`git ls-files`. That failed as `leakage_scope_unavailable`, was mapped to
`MAINTENANCE_OBSERVATION_SCAN_FAILED`, then to closure evidence rejection, and
finally surfaced as `R2_SOLO_MAINTAINER_CLOSURE_INVALID`.

The same materialized repository succeeded when scanned through the existing
explicit-root maintenance seam with its verified tracked-path tuple.

## 6. Exact scope

Add:

```text
docs/operations/protected_verifier_materialized_maintenance_fix_task_brief.md
```

Modify:

```text
backend/r2_solo_maintainer_closure/local_evidence.py
tests/test_r2_solo_maintainer_closure.py
tests/test_r2_solo_maintainer_closure_architecture.py
docs/constraints/architecture_constraints.md
docs/constraints/tooling_constraints.md
docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
docs/operations/project_structure.md
```

Delete:

```text
none
```

## 7. Design

`local_evidence._maintenance_observation(root, tracked_paths)` calls
`maintenance_scan._collect_materialized_stable_observation(root,
tracked_paths)`. The maintenance module continues to own scanner composition,
stable projection, deterministic ordering, duplicate rejection, error mapping,
and counts. The closure adapter continues to own the independent exact
twenty-four-entry registry, proof fingerprint, and eligibility decision.

The root and tracked paths are not new caller inputs. They are the values already
validated and bound into the closure's repository snapshot. The public closure
surface remains parameterless `prepare()` plus exact `confirm(...)`.

## 8. Non-goals

This task does not change the maintenance CLI, add a public path or callback,
modify or replace closure artifacts, retry protected verification, commit, push,
open or merge a pull request, roll over evidence, create a new closure, approve
Issue #38, or authorize Issue #39.

## 9. Acceptance criteria

The closure adapter passes the exact verified root and tracked-path tuple to the
internal materialized observation seam and never calls the parameterless seam.
The existing Gitless materialized observation test remains green. The ordinary
parameterless and explicit materialized observations remain equivalent in a real
checkout. Missing, duplicate, additional, or failed maintenance evidence still
fails closed. Focused closure, maintenance, architecture, documentation,
leakage, and repository tests must pass before separate commit authority is
requested.

## 10. Authorization boundary

Implementation and tests are authorized from exact base
`201c011174aee3bc5ffc30c85cb70655b437bb70` on branch
`codex/protected-verifier-materialized-maintenance-fix`. Commit, push, PR,
merge, closure rollover, new closure, protected-verifier retry, Issue #38 review,
and Issue #39 authority remain zero.

## 11. Post-merge generated-status drift correction

PR #131 merged the maintenance fix at exact master
`6ae6f846b56c7e089ce66edd4f92b974052690df`. The subsequent closure prepare
correctly failed closed because adding this active task brief increased the
generated active-document count from 136 to 137, while the checked-in
`project_status_log.md` had not been regenerated after the document was added.
The repository, GitHub, and materialized maintenance evidence stages otherwise
remained consistent; the mismatch was isolated to the generated-versus-frozen
status snapshot gate.

The forward correction regenerates the checked-in project status from the
merged tree and adds a regression test that compares normalized generated
status with the normalized checked-in snapshot. It creates or mutates no
closure artifact and changes no closure schema, evidence semantics,
confirmation, publication, verifier behavior, or Issue #38/#39 authority. The
changed frozen source, test, and generated-status bytes necessarily produce new
derived source and evidence fingerprints. This correction does not retry
closure prepare or protected verification.
