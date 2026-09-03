---
last_update: 2026-09-03
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue #38 Closure Maintenance Calendar Stability Task Brief

## 1. Task

Type: `fix`

State: `implemented`

Governing diagnostic baseline: `master@3bcbf99ed2c1f0e091e7fb857cafb37c173cb987`

## 2. Goal

Keep the `maintenance_scan_output` closure proof stable when the exact reviewed
maintenance classifications and repository evidence are unchanged across calendar
days. Preserve fail-closed rejection of every missing, duplicate, additional,
wrong-severity, wrong-category, wrong-path, or wrong-owner-document finding.

## 3. Non-goals

- Do not change the reviewed twenty-four-entry classification registry.
- Do not suppress, rewrite, or falsify the human-readable maintenance report.
- Do not weaken repository, hosted evidence, ruleset, closure, attestation, or
  Execution Confirmation validation.
- Do not rewrite or reissue active closure evidence.
- Do not run Issue #39 readiness, roster, prepare, binder, action runner, recovery,
  or cutover.
- Do not mutate GitHub Issues, pull requests, rulesets, services, host layout,
  durable cutover state, mailbox, provider, vault, credential, or private data.

## 4. Evidence and diagnosis

One content-free comparison between the stored closure and a freshly derived
manifest found six leaf differences. The sole source difference was
`evidence_records[13].source_fingerprints[0].fingerprint`, which maps to the
`maintenance_scope` gate and `maintenance_scan_output` source. The exact Git tree,
hosted evidence, GitHub guardrail snapshot, reviewed twenty-four classifications,
and every other local proof remained equal.

`scripts/maintenance_scan.py` renders stale-document messages using
`date.today()`, while the closure proof currently hashes every `Finding` field,
including that rendered age. The stored closure was confirmed three calendar days
before the diagnostic, so unchanged findings acquired different message text and
therefore a different closure identity.

## 5. Scope

Expected changes are limited to:

- `AGENTS.md`
- `backend/r2_solo_maintainer_closure/local_evidence.py`
- `tests/test_r2_solo_maintainer_closure.py`
- `tests/test_architecture_constraints.py`
- `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md`
- `docs/operations/r2_solo_maintainer_closure_runbook.md`
- applicable closure text in `docs/constraints/`
- `docs/templates/agent_task_brief_template.md`
- this task brief
- generated `docs/operations/project_status_log.md`

## 6. Approved seam and design

The regression seam is the existing `build_local_source_proofs(...)` closure
boundary. Time is a system boundary; the test supplies two synthetic maintenance
finding sets with identical reviewed classification facts and different rendered
age messages, then requires the public proof identity to remain equal.

Production continues to execute the real read-only maintenance scan and require
exact set equality against the fixed registry. After that validation, the proof
identity includes only stable structured finding fields already approved by the
contract: `severity`, `category`, `path`, and `doc`. Human-facing `message` and
`fix` remain available in the maintenance report but are not closure identity.

## 7. Interfaces and data

Database changes: none.

API changes: none.

AI JSON changes: none.

Prompt changes: none.

The internal maintenance-proof fingerprint changes once. Existing closure evidence
remains immutable historical evidence and is not rewritten by this task.

## 8. Security and privacy

- Only content-free repository metadata and synthetic findings are used.
- No email is read, sent, deleted, archived, or analyzed.
- No provider, key, token, credential, mailbox, vault, or private data is accessed.
- Closure and attestation remain non-authorizing for Issue #39.
- Real Project Container cutover remains outside this authorization.

## 9. Acceptance criteria

1. The behavior-level regression fails before the implementation change and passes
   after it.
2. Identical reviewed classification facts produce the same maintenance proof when
   only rendered message/fix text changes.
3. Missing, duplicate, additional, or reclassified findings continue to fail
   closed.
4. Focused closure tests, architecture/static/mechanical guards, full unit discovery,
   generated status, maintenance scan, leakage scan, and `git diff --check` pass.
5. No closure evidence, GitHub state, service, host layout, durable state, or Issue
   #39 execution state is created or mutated.

## 10. Test plan

First run the new focused behavior test and record red. Apply the minimal stable
projection, rerun the focused test and closure suite, then perform the repository's
required full verification and maintenance checks.

## 11. Rollback

Before integration, discard only these uncommitted worktree changes. After a future
merge, use a new revert commit; do not rewrite protected history or delete closure
evidence.

## 12. Execution preflight

- [x] Read `AGENTS.md`, `CONTEXT.md`, current project status, applicable constraints,
  ADR 0010, task-brief rules, and documentation rules.
- [x] Read the applicable `diagnosing-bugs` and `tdd` skills completely.
- [x] Confirmed the approved behavior seam and red-green order.
- [x] Confirmed Superpowers remains prohibited and unused.
- [x] Confirmed the launcher worktree was clean before this task.
- [x] Confirmed no real-host, closure-publication, or Issue #39 authorization.

## 13. Applicable closure checklist

- [x] The closure package and public `prepare()` / `confirm(...)` seams remain
  unchanged.
- [x] Five hosted checks, one guardrail snapshot, fourteen gates, eight gap proofs,
  and all zero-count authority and safety boundaries remain unchanged.
- [x] Fresh maintenance evidence still requires exactly twenty-four reviewed
  low-risk `(severity, category, path, doc)` classifications.
- [x] Missing, duplicate, additional, or reclassified findings still fail closed.
- [x] Dynamic rendered maintenance text is excluded only after exact classification
  validation and cannot widen the approved set.
- [x] Confirmation, publication, protected verification, rollover, and Execution
  Confirmation behavior remain unchanged.
- [x] Tests use synthetic/content-free inputs and grant no cutover authority.

## 14. Completion record

Actual changes:

- `local_evidence.py` now projects validated maintenance findings through only
  `severity`, `category`, `path`, and `doc` before fingerprinting.
- The closure behavior suite proves that identical classifications with rendered
  ages 30 and 31 produce the same `maintenance_scan_output` proof.
- `AGENTS.md`, ADR 0010, the closure runbook, active architecture/tooling/mechanical
  constraints, and the task-brief checklist document the stable identity boundary;
  the architecture constraint test enforces the updated checklist marker.

Verification:

- Red: the new behavior test produced distinct proof fingerprints for ages 30 and
  31 on the unmodified implementation.
- Green: the new test and two existing maintenance fail-closed tests passed.
- Focused closure suite: 27 tests passed.
- Closure plus architecture/static/mechanical guardrails: 120 tests passed.
- Full discovery after status generation: 2,924 tests passed with 4 expected skips.
- Maintenance scan returned exactly the reviewed 24 low-risk stale-document
  findings; repository leakage output was empty; `git diff --check` passed.

Remaining work:

The worktree changes are uncommitted. Any future integration, CI, merge, closure
evidence rollover/reissue, Issue #38 review, or Issue #39 readiness/cutover requires
its own governed authorization. Existing closure evidence was not modified.
