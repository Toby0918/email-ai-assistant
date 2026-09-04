---
last_update: 2026-09-03
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Maintenance observation deepening task brief

## 1. Task name

Deepen the stable maintenance observation used by Solo Maintainer Closure.

## 2. Task type

```text
refactor
```

## 3. Current status

```text
completed_worktree_only
```

## 4. Goal

Move fixed scanner composition, stable finding projection, deterministic
ordering, duplicate rejection, and aggregate severity counts behind one deep
maintenance interface. Keep the Solo Maintainer Closure adapter independently
responsible for its exact twenty-four-entry reviewed registry, canonical proof
fingerprint, and eligibility decision.

## 5. Non-goals

- Do not change maintenance CLI arguments, output, messages, fixes, or exit codes.
- Do not clean, edit, reclassify, or delete any stale document.
- Do not change generated-status semantics or repository leakage policy.
- Do not cache or persist maintenance observations.
- Do not change, roll over, replace, or recreate closure evidence.
- Do not approve Issue #38 or authorize or execute Issue #39.
- Do not commit, push, open a PR, merge, or mutate GitHub.

## 6. Basis

- Exact base commit `828a8ddad409d1974e83eea34ba9985df099d997`.
- The approved architecture candidate and completed grilling decisions.
- The 2026-09-03 follow-up approval to update the fixed generated-status AST
  digest in its existing mailbox transport guard after the approved generator
  change.
- `AGENTS.md`, `CONTEXT.md`, ADR 0010, and the current architecture, tooling,
  mechanical, testing, and closure constraints.
- The observed calendar-stability repair where rendered maintenance text crossed
  the closure identity seam.

## 7. Exact Add/Modify/Delete allowlist

### Add

```text
docs/operations/maintenance_observation_deepening_task_brief.md
```

### Modify

```text
scripts/maintenance_scan.py
backend/r2_solo_maintainer_closure/local_evidence.py
tests/test_maintenance_scan.py
tests/test_r2_solo_maintainer_closure.py
tests/test_r2_solo_maintainer_closure_architecture.py
docs/constraints/architecture_constraints.md
docs/constraints/tooling_constraints.md
docs/templates/agent_task_brief_template.md
tests/test_architecture_constraints.py
docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md
docs/operations/project_structure.md
scripts/generate_project_status.py
tests/test_generate_project_status.py
tests/test_mailbox_transport_constraints.py
docs/operations/project_status_log.md
```

### Delete

```text
none
```

Any other path requires a new explicit scope decision before modification.

## 8. Technical design

`scripts.maintenance_scan` will expose one parameterless fresh observation
interface. It will return observer-owned immutable values containing only the
stable `severity`, `category`, `path`, and `doc` fields plus internally derived
counts. It will own deterministic sorting, reject duplicate or malformed
records, map scanner failures to fixed content-free errors, and never calculate
a closure fingerprint.

An explicit internal materialized-tree entry will accept only a repository
root and a sorted unique safe tracked-path tuple. It will use the same fixed
scanner composition and stable projection without accepting caller scanners or
silently switching based on `.git` presence.

The closure adapter will consume the stable observation, independently require
the exact reviewed twenty-four-entry classification registry, and retain the
existing canonical fingerprint mapping and `EVIDENCE_REJECTED` failure. The
closure-owned scanner reconstruction will be removed.

The existing `Finding`, scanner functions, `collect_findings`, report renderer,
CLI parameters, output, and exit behavior remain compatible.

## 9. Data and interface changes

- Database, HTTP, provider, prompt, frontend, mailbox, vault, and SQLite: none.
- Maintenance CLI: unchanged.
- New internal Python values: stable finding, observation, and fixed error.
- New production seam: parameterless fresh stable observation.
- New test-only/internal seam: explicit materialized stable observation.
- Closure manifest and receipt schemas: unchanged.

## 10. Security and privacy checks

- The observation is fresh, read-only, uncached, and unpersisted.
- No arbitrary callback, path, scanner, command, network, provider, mailbox,
  vault, private-data, authorization, mutation, or cleanup capability is added
  to the production seam.
- Duplicate, malformed, partial, or failed scans fail closed.
- Underlying exceptions do not cross into closure results.
- Closure keeps an independent exact registry and cannot be self-certified by
  the maintenance scanner.

## 11. Prompt injection protection

Not applicable. The task does not read email content or call an AI provider.

## 12. Acceptance criteria

1. Rendered `message` and `fix` changes do not change stable observation values.
2. Input order is normalized deterministically and exact duplicates fail closed.
3. Scanner or input failure yields only a fixed maintenance observation error.
4. Live and explicit materialized scans produce the same stable observation for
   the same repository state.
5. Closure no longer reconstructs scanner ordering or stable fields.
6. Closure still rejects a missing, duplicate, or additional classification.
7. Existing maintenance CLI behavior remains unchanged.
8. The exact Add/Modify/Delete diff matches this brief.
9. Focused, architecture, static, mechanical, status, maintenance, leakage, and
   complete repository tests pass before any later Git authorization is sought.

## 13. Test plan

Use vertical TDD slices through the approved observation seam. Start with the
missing parameterless interface, add stable-field and ordering behavior, add
duplicate/malformed/failure behavior, add explicit materialized equivalence,
then migrate closure tests from private helper patching to the stable
observation seam. Finish with architecture ownership checks and the full gate.

## 14. Rollback plan

Before any commit, revert only the allowlisted working-tree edits after
inspecting the exact diff. No closure artifact or retained evidence is a rollback
surface. After a future merge, use a separately reviewed forward corrective PR.

## 15. Human confirmation questions

None for the authorized worktree-only implementation. Commit, push, PR, merge,
closure rollover, new closure, Issue #38 approval, and Issue #39 remain outside
authority.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, `CONTEXT.md`, ADR 0010, and relevant constraints.
- [x] Completed architecture candidate selection and grilling.
- [x] Confirmed the exact Add/Modify/Delete allowlist.
- [x] Created a separate worktree from exact master.
- [x] Confirmed no real mailbox, provider, vault, private data, or host mutation
  is in scope.

## 22. Issue #110 Solo Maintainer Closure / Execution Confirmation checklist

- [x] The public closure package remains exactly ten files with the unchanged
  `prepare()` and `confirm(...)` facade.
- [x] The closure-owned exact twenty-four-entry registry remains independent.
- [x] Only stable `(severity, category, path, doc)` fields enter closure identity.
- [x] Human-facing `message` and `fix` remain report-only.
- [x] No cache, arbitrary callback, authorization, cleanup, or host effect is
  added.
- [x] No live closure or protected verifier will run from the dirty development
  worktree.

## 23. Execution record

The implementation was completed on branch
`codex/maintenance-observation-depth` from exact base
`828a8ddad409d1974e83eea34ba9985df099d997` without a commit, push, PR,
merge, closure operation, Issue #38 approval, or Issue #39 authority or
execution.

TDD recorded failing tests before each stable-observation, closure-consumer,
fixed-error, materialized-input, and Windows-safe-path implementation slice.
The final focused maintenance, closure, architecture, generated-status, and
mailbox-transport run passed 97 tests. The final complete repository run passed
2,939 tests in 6,040.430 seconds with four expected skips. The maintenance CLI
and stable observation both reported exactly 24 low, zero medium, and zero high
findings; repository leakage returned zero findings; and `git diff --check`
passed.

Independent Standards and Spec reviews found raw malformed-input exceptions,
duplicated scanner composition, and incomplete Windows tracked-path rejection.
The implementation was corrected to centralize fixed scanner composition and
reject heterogeneous, drive-qualified, rooted, backslash, traversal, ADS,
reserved-device, NFKC device-alias, control-character, overlong-component, and
root-probe-invalid inputs through fixed content-free errors. Final re-review
reported no Standards finding and no implementation/spec defect. Four
test-generated `issue57-*` directories were moved to the Windows Recycle Bin
only after separate explicit cleanup approval; no other cleanup occurred.
