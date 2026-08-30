---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 39 fixed incident binding drift task brief

## 1. Task name

```text
Issue 39 exact retained-incident binding repair
```

## 2. Task type

```text
fix
```

## 3. Current status

```text
ready_for_review
```

## 4. Task goal

Repair the fixed Issue 39 incident-disposition binding so zero-mutation readiness
recognizes the exact retained incident evidence directory that exists on the
reviewed host. Preserve the existing exact artifact hashes, protected DACL,
fixed archive parent, same-volume no-replace move, zero-delete behavior, and
absence of any caller-selected path.

## 5. Non-goals

- Do not move, rename, copy, delete, clean, or change the DACL of real evidence.
- Do not execute incident disposition, evidence publication, cutover, resume,
  rollback, service control, repository relocation, or managed publication.
- Do not accept an arbitrary source, destination, fingerprint, path, environment
  override, or alternate artifact set.
- Do not weaken exact artifact-length, SHA-256, DACL, reparse, fixed-volume,
  destination-absence, or no-replace validation.
- Do not modify Issue 38, Issue 39, the GitHub ruleset, provider, mailbox, vault,
  private-data, or cleanup surfaces as part of the code repair.

## 6. Background and basis

The authorized real-cutover preflight found the expected historical artifacts
intact under the exact leaf
`.r2-solo-maintainer-closure-v1.incident-794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721`.
The production binding still names the obsolete `.stage-794aea72...` source,
so both source verification and archived-state verification fail closed before
any confirmation or host mutation.

Related documents:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/operations/issue39_project_container_cutover_runbook.md`
- `docs/operations/issue39_one_command_cutover_task_brief.md`
- `docs/decisions/0012-issue39-project-container-cutover-orchestration.md`
- `docs/security/project_container_cutover_contracts.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/ci_guardrails.md`
- `docs/constraints/mechanical_rule_translation.md`

## 7. Scope

Expected changes:

- `backend/r2_issue39_orchestrator/incident_binding.py`
- `tests/test_r2_issue39_incident_disposition.py`
- governed Issue 39 runbook/ADR/constraint documentation that pins the exact
  retained incident leaf
- `docs/operations/project_status_log.md` through the normal generator

## 8. Technical design

1. Add a regression test at the production binding seam that pins the exact
   retained incident leaf for both source and deterministic destination.
2. Change only the private code-fixed leaf from the obsolete `.stage-...` name
   to the exact reviewed `.incident-...` name.
3. Keep the parent directories, two artifact bindings, byte lengths, SHA-256
   hashes, source DACL, no-replace move, zero-delete counts, and parameterless
   operator surface unchanged.
4. Synchronize active runbook, ADR, security, architecture, tooling, linter,
   mechanical, and CI statements without creating an alternate compatibility
   alias.

## 9. Data and API changes

### Database changes

```text
None.
```

### API changes

```text
None. The public operator command remains exactly one `run` verb.
```

### AI output JSON changes

```text
None.
```

### Prompt changes

```text
None.
```

## 10. Security and privacy checks

- [x] No real mailbox or private message data is read.
- [x] No email is sent, deleted, or archived.
- [x] No provider or credential surface changes.
- [x] Production paths remain private, code-fixed, and absent from public values.
- [x] Tests use only production-binding string assertions and test-owned
  temporary Windows fixtures.
- [x] No real incident evidence is changed during implementation or tests.

## 11. Prompt Injection protection

Not applicable. The fixed command accepts no email, model, or free-form input.

## 12. Acceptance criteria

1. A focused regression test fails on the obsolete `.stage-794aea72...` binding
   and passes only with the exact retained `.incident-794aea72...` leaf.
2. Source and destination use the same single code-fixed leaf under their
   existing fixed parents.
3. Artifact names, lengths, SHA-256 hashes, source DACL, no-replace behavior,
   and zero delete/cleanup counts remain unchanged.
4. Unknown, alternate, copied, collided, drifted, reparse, or caller-selected
   sources remain unreachable or fail closed.
5. Focused, architecture, static, mechanical, status, maintenance, leakage, and
   full unit suites pass.
6. PR, five required CI checks, and post-merge master checks pass before a new
   closure or Issue 38 review is attempted.

## 13. Test plan

- Focused production binding regression test.
- Existing Issue 39 incident disposition and CLI tests.
- Issue 39 governed-enablement and cutover-guard repair tests.
- Architecture, static linter, mechanical-rule, and status-generator suites.
- `python -m unittest discover -s tests`.
- `python scripts/maintenance_scan.py`.
- `python scripts/repository_leakage_scan.py`.
- `git diff --check`.

## 14. Rollback plan

Revert the single-purpose code/documentation commit through the normal governed
Git workflow. Do not move or reconstruct real incident evidence as a code
rollback mechanism.

## 15. Human confirmation questions

None. The operator explicitly authorized this exact binding repair, task brief,
tests, PR, CI, merge, and the post-merge closure review chain. Real cutover is
not authorized by this repair.

## 16. Pre-execution checklist

- [x] Read `AGENTS.md`, `CONTEXT.md`, project status, relevant constraints,
  active Issue 39 runbook, task brief, ADR, and security contract.
- [x] Confirmed the exact retained evidence leaf, two artifact identities, and
  protected DACL through read-only observation.
- [x] Confirmed the current code-fixed source and archive destination are absent.
- [x] Confirmed the implementation worktree is isolated, clean, and based on
  exact `d72bfbbc82b9860d7f318881cdca26fd0e9e3e49`.
- [x] Confirmed no real-host disposition or cutover is in implementation scope.

## 17. Repository placement and operational layout checklist

- [x] The Issue 39 orchestrator remains the sole production cutover root.
- [x] The operator script remains fixed to one launcher and one `run` verb.
- [x] Source and destination remain code-fixed with no arbitrary path surface.
- [x] Publication remains same-volume, no-replace, identity-preserving, and
  zero-delete.
- [x] Real evidence remains untouched by automated tests.
- [x] Closure, Issue 38 approval, and real cutover remain separate authorities.

## 18. Execution record

```text
Actual changed files:
- backend/r2_issue39_orchestrator/incident_binding.py
- tests/test_r2_issue39_incident_disposition.py
- tests/test_r2_issue39_governed_enablement.py
- this task brief and the governed Issue 39 runbook/ADR/security/constraint docs
- docs/operations/project_status_log.md through the normal generator

Verification completed:
- red regression reproduced twice on the obsolete `.stage-...` binding
- focused incident/governance/CLI/cutover-guard tests: 29 passed
- architecture/static/mechanical/status/readiness tests: 144 passed
- real-host read-only observation after the fix: SOURCE_VERIFIED
- full suite: 2,901 tests run; 2,894 passed, 5 skipped, 2 environment
  errors because an unrelated user-owned EPUB preview server already owns
  127.0.0.1:8765; both errors fail closed with
  R2_ISSUE39_LEGACY_SERVICE_AMBIGUOUS

Remaining work: maintenance/leakage scans, review, PR, clean CI, merge, and the
separately governed post-merge exact-master closure review chain. The existing
preview server was not stopped or modified.
```
