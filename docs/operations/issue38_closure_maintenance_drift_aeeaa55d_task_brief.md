---
last_update: 2026-08-29
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #38 Closure Maintenance Drift at `aeeaa55d` Task Brief

## 1. Task

- Type: `fix`
- State: `implemented`
- Governing baseline: `master@aeeaa55d01a2113af722e0a67efe8be63fc43771`

## 2. Goal

Restore the exact Solo Maintainer Closure maintenance-evidence match by
classifying only these two reviewed, low-risk historical draft documents:

- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`

The documents remain stale historical drafts. This task records that fact; it
does not refresh their dates, change their content, or treat them as current
governance.

## 3. Non-goals

- Do not add any other maintenance finding or path to the registry.
- Do not weaken exact-set, duplicate, severity, category, or owner-document
  validation.
- Do not modify either classified document.
- Do not change closure confirmation, the protected verifier, Issue #38 review
  semantics, or Issue #39 execution contracts.
- Do not repair the unrelated damaged Git ref, fetch tags, prune, clean, delete,
  overwrite, or execute a real Project Container cutover.
- Do not access a provider, mailbox, vault, credential, private store, or real
  customer data.

## 4. Evidence and diagnosis

On the frozen baseline, repository leakage and generated-status evidence pass.
The read-only maintenance scan returns 24 exact low-risk `stale_doc`
classifications while the frozen closure registry contains 22. Their exact
difference is the two paths named above, causing live `prepare` to fail closed
with `R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED`.

## 5. Scope

Expected changes are limited to:

- `backend/r2_solo_maintainer_closure/local_evidence.py`
- `tests/test_r2_solo_maintainer_closure.py`
- exact-count synchronization in the active architecture, tooling, mechanical,
  task-template, and closure-runbook documents and their existing text guards
- this task brief
- generated `docs/operations/project_status_log.md`

## 6. Design

1. Add a deterministic regression that compares the independent reviewed-path
   oracle with the production registry and observe it fail on the baseline.
2. Extend the independent test oracle and the production registry by exactly
   the two approved paths.
3. Preserve exact set equality, uniqueness, and fail-closed behavior for every
   other finding.
4. After tests, PR, CI, and merge, rebuild an exact-master LF review worktree
   and rerun closure, protected verification, and the fourteen-item Issue #38
   final review against the new master.

## 7. Interfaces and data

- Database: none.
- API: none.
- AI JSON: none.
- Prompt: none.
- Provider, mailbox, vault, and host-mutation surfaces: unchanged.

## 8. Security and privacy

- [x] Only content-free repository metadata and synthetic tests are used.
- [x] No email is read, sent, deleted, archived, or analyzed.
- [x] No key, token, credential, private data, provider, vault, or mailbox is
  accessed.
- [x] Closure and verifier output remain non-authorizing for Issue #39.
- [x] Real Project Container cutover remains outside this authorization.

## 9. Acceptance criteria

1. A deterministic focused registry regression fails on the 22-entry baseline
   and passes with exactly 24 reviewed entries; a separate action-time scan
   verifies the real checkout.
2. The production registry and independent test oracle contain both approved
   paths exactly once and no other new path.
3. Missing, duplicate, additional, wrong-category, or wrong-severity findings
   continue to fail closed.
4. Focused closure tests, all guardrails, full unit discovery, generated status,
   maintenance scan, leakage scan, and `git diff --check` pass.
5. PR CI supplies the five required successful checks before merge.
6. Post-merge exact-master LF verification, closure, protected verifier, and
   Issue #38 final review are rebound to the new master; no real cutover occurs.

## 10. Test plan

- Focused red/green test in `tests.test_r2_solo_maintainer_closure`.
- `python -m unittest tests.test_r2_solo_maintainer_closure`
- architecture, static, and mechanical guardrail suites.
- `python -m unittest discover -s tests`
- project-status generation and exact normalized comparison.
- maintenance and repository-leakage scans.
- `git diff --check` and tracked-byte review before closure.

## 11. Rollback

Before merge, discard only this isolated branch. After merge, use a new revert
commit; do not rewrite protected history or delete closure evidence.

## 12. Manual gates

The maintainer authorized implementation, tests, PR, CI, merge, and the
post-merge closure/verifier/#38 review sequence. The fixed native-console
closure confirmation and the final human fourteen-item Issue #38 approval
remain personal-review gates. Issue #39 real cutover is not authorized.

## 13. Execution preflight

- [x] Read current `AGENTS.md`, `CONTEXT.md`, project status, applicable
  constraints, task-brief rules, and documentation rules.
- [x] Read the applicable `diagnosing-bugs` skill completely.
- [x] Confirmed Superpowers remains prohibited and unused.
- [x] Confirmed exact clean baseline, remote master, five successful checks,
  ruleset, and Issue states before branching.
- [x] Confirmed the exact two-path scope and no real-host authorization.

## 14. Completion record

- Red: the independent 24-path oracle reported exactly the two approved paths
  missing from the 22-entry production registry.
- Green: the focused closure suite passed after adding only those two paths.
- The first full discovery exposed that a real-worktree scan inside the new unit
  test raced with another test's temporary Python-runtime publication. The
  regression was tightened to a pure oracle-to-registry comparison; the real
  checkout remains an action-time maintenance scan.
- Final full discovery: `Ran 2867 tests in 4523.369s`, `OK (skipped=4)`.
- Architecture/static/mechanical guards, generated status, maintenance scan,
  and repository leakage scan passed before final publication checks.
