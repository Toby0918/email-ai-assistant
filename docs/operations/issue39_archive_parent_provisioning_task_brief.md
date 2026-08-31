---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 39 fixed archive-parent provisioning task brief

## 1. Task name

```text
Issue 39 fixed incident archive-parent readiness and provisioning repair
```

## 2. Task type

```text
fix
```

## 3. Current status

```text
implementation_complete_pending_ci
```

## 4. Task goal

Repair the production-only Issue 39 incident-disposition path so the exact
archive parent `D:\IncidentArchives\email_ai_assistant\issue38` can be created
safely when its fixed hierarchy is absent. Bind that readiness state into the
fresh incident confirmation and retain the existing exact evidence, same-volume
no-replace move, restored DACL, and zero-delete boundaries.

## 5. Non-goals

- Do not execute the real incident disposition or Project Container cutover.
- Do not create, remove, rename, clean, or change the DACL of the real archive
  hierarchy or real retained incident evidence during implementation or tests.
- Do not add a CLI path, environment override, callback, registry, discovery,
  fallback, force, cleanup, repair, or caller-selected destination.
- Do not change `D:\` security, owner, group, SACL, or any unrelated directory.
- Do not weaken exact incident artifact hashes, source DACL, same-volume,
  no-reparse, destination-absence, identity, no-replace, or zero-delete checks.
- Do not authorize Issue 39 live cutover. Post-merge closure, protected
  verification, and Issue 38 review remain separate governed ceremonies.

## 6. Background and basis

The authorized real command reached the incident-disposition phase and returned
`BLOCKED_ISSUE39_PREPARE` with zero cutover host actions. Read-only diagnosis
proved the exact retained source and artifacts remain valid, the destination is
absent, and the entire fixed archive-parent hierarchy is absent. The production
adapter currently opens `binding.destination.parent` without provisioning it,
while its Windows fixture always creates that parent in advance. The fixture
therefore omitted the real missing-parent mode.

The repair is based on frozen master
`eb84674f1d303f1e98be098880b81d82a1ed222d` and its tree
`3903eb33753b15c55e26a62822f1dc266e575168`.

Related documents:

- `AGENTS.md`
- `CONTEXT.md`
- `docs/operations/issue39_project_container_cutover_runbook.md`
- `docs/operations/issue39_fixed_incident_binding_drift_task_brief.md`
- `docs/decisions/0012-issue39-project-container-cutover-orchestration.md`
- `docs/security/project_container_cutover_contracts.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/ci_guardrails.md`
- `docs/constraints/mechanical_rule_translation.md`

## 7. Scope

Expected implementation scope:

- one narrow archive-parent binding/readiness/provisioning module inside
  `backend/r2_issue39_orchestrator`;
- incident binding, confirmation, disposition, and zero-readiness integration,
  including the confirmed parent fingerprint and a held lease through rename;
- the test-owned incident fixture and focused Issue 39 tests;
- Issue 39 ADR, runbook, security and executable constraint statements;
- generated `docs/operations/project_status_log.md`.

## 8. Technical design

1. Keep the only production archive hierarchy code-fixed as the exact local
   components `D:\`, `IncidentArchives`, `email_ai_assistant`, and `issue38`.
2. Add no public constructor and no caller path. The production observer and
   provisioner are parameterless. A private nominal binding exists only so the
   existing test-owned Windows fixture can exercise the same native code.
3. The zero-mutation observer opens every existing component without following
   reparses and requires fixed-drive NTFS, directory type, exact normalized
   placement, stable handle identity, and the exact archive DACL on every
   controlled child. It classifies only `READY`, `PROVISIONABLE`, or `BLOCKED`.
4. Bind the parent-state and exact opened-identity fingerprint into
   `Issue39ZeroMutationReadinessV1` and therefore into the already fresh
   incident-disposition confirmation. A blocked parent never reaches
   confirmation or mutation.
5. After that confirmation, reopen the fixed root and existing prefix, require
   the observed presence/identity fingerprint to equal the confirmed value,
   then hold the root and every created/validated component through rename and
   artifact reread. Create each absent child relative to its held parent using
   native `FILE_CREATE`; a collision never opens, replaces, adopts, or retries
   the competing object in the same attempt.
6. Apply the final protected DACL at object creation. It contains exactly three
   non-inherited allow ACEs: current token SID, LocalSystem, and built-in
   Administrators, each with object/container inheritance and Full Control.
   Owner/group/SACL are not modified by a later path-based operation.
7. Reobserve each held handle and the complete chain after creation. Any NTFS,
   fixed-drive, reparse, placement, identity, or DACL mismatch fails closed.
8. Only a complete `READY` observation permits the existing source-DACL bridge,
   same-volume no-replace incident move, artifact reread, and archive verifier.
9. Partial create-only state is retained on failure. There is no automatic
   delete, cleanup, replace, ACL repair, or pathname rollback.

## 9. Data and API changes

### Database changes

```text
None.
```

### Public API changes

```text
None. The operator command remains exactly the fixed parameterless `run` flow.
```

### AI output JSON and prompt changes

```text
None.
```

## 10. Security and privacy checks

- [x] The production path is code-fixed and absent from every public value.
- [x] Tests use only a test-owned temporary directory on Windows.
- [x] No real incident artifact, mailbox, provider, credential, vault, private
  store, or customer data is read by the test workflow.
- [x] Creation is handle-relative, create-only, no-replace, NTFS-only, fixed
  drive, non-reparse, exact-placement, exact-DACL, and identity-reverified.
- [x] The volume root and unrelated parents are never ACL-mutated.
- [x] Failure preserves evidence and creates no delete/cleanup authority.

## 11. Prompt injection protection

Not applicable. The path, components, policy, command, and acknowledgement are
code-owned; no email, model output, or free-form caller value is consumed.

## 12. Acceptance criteria

1. A Windows regression starting with the complete test archive hierarchy
   absent fails on the old implementation and passes only after the production
   seam creates all three exact children and archives the source.
2. The test proves source absence, destination identity/artifacts, final source
   DACL preservation, exact parent policy, and zero deletions.
3. Existing wrong-DACL, reparse, non-NTFS, destination collision, create race,
   or placement drift stops before the incident move and preserves competitors.
4. Zero-readiness is eligible for exact `PROVISIONABLE` and `READY` states,
   rejects `BLOCKED`, and changes its fingerprint when parent state changes.
5. Production entry points remain parameterless and no arbitrary path or
   alternate archive leaf becomes reachable.
6. Focused, static, architecture, mechanical, status, maintenance, leakage,
   and full unit suites pass.
7. The PR receives all five required `completed/success` checks and is merged
   before a new exact-master closure chain begins.

## 13. Test plan

- Red/green missing-parent Windows incident regression.
- Parent-ready, partial-ready, collision, wrong-DACL, and reparse cases using
  only test-owned temporary objects.
- Zero-readiness fingerprint and CLI ordering tests.
- Existing Issue 39 incident, CLI, governed-enablement, and cutover-guard tests.
- Architecture, linter, mechanical-rule, and documentation guards.
- `python -m unittest discover -s tests`.
- `python scripts/maintenance_scan.py`.
- `python scripts/repository_leakage_scan.py`.
- `git diff --check`.

## 14. Rollback plan

Revert the single-purpose code and documentation commit through the governed Git
workflow. Do not remove any real or test-retained partial directory as part of
code rollback; cleanup remains separate and explicit.

## 15. Human confirmation questions

None. The operator explicitly authorized this exact repair, task brief, tests,
PR, CI, merge, and post-merge closure review chain. Real cutover is excluded.

## 16. Pre-execution checklist

- [x] Fresh remote master is exact `eb84674f1d303f1e98be098880b81d82a1ed222d`.
- [x] Issue 38 is closed and Issue 39 is open.
- [x] The implementation worktree is clean and branched from exact master.
- [x] The real source/destination diagnosis was read-only and recorded zero
  cutover host actions.
- [x] The missing-parent test seam and fixed production seam are identified.
- [x] No real cutover is in scope.

## 17. Repository placement checklist

- [x] The fixed Issue 39 orchestrator remains the sole production consumer.
- [x] The script and CLI remain one fixed launcher and one `run` verb.
- [x] No production code imports a test helper.
- [x] No new dependency, service, scheduled task, or external API is added.
- [x] Closure, protected verification, Issue 38 review, and cutover remain
  separate authorities.

## 18. Execution record

```text
Implemented:
- exact fixed three-component archive-parent binding;
- zero-mutation PROVISIONABLE/READY/BLOCKED observation and fingerprint;
- parent-handle-relative native FILE_CREATE with at-create protected exact DACL;
- incident confirmation/disposition integration with the confirmed parent
  fingerprint surviving into the disposition boundary;
- missing-parent, partial-prefix, wrong-DACL, competing-create, parent-
  replacement, reparse, filesystem, placement, binding, readiness, CLI,
  architecture, mechanical, and documentation regressions;
- synchronized ADR, runbook, security, constraints, status generator and log.

Verification:
- red regression: missing parent returned INCIDENT_STOP on the old code;
- focused archive-parent/incident/zero-readiness/CLI: 23 passed;
- architecture 51 passed; static linter 31 passed; mechanical 11 passed;
- governed enablement 6 passed; status generator 37 passed;
- exact failure follow-up: host architecture 7 passed, preflight architecture
  8 passed, mailbox transport 15 passed;
- Issue 39 suite: 108 passed, 2 skipped, 2 environment errors caused by the
  unrelated existing Python process on 127.0.0.1:8765;
- full suite before exact static-allowlist follow-up: 2,909 run, 2,898 passed,
  5 skipped, 4 static failures subsequently fixed and focused-green, plus the
  same 2 environment errors;
- git diff --check, maintenance scan, and repository leakage scan: exit 0.

Local full-suite acceptance remains pending rather than recorded as passed:
the two production-native Windows cases are blocked by the unrelated pre-
existing listener on `127.0.0.1:8765`. That user-owned process is not stopped
or modified by this task. The required clean-host CI result remains pending and
must be recorded before merge.

No real archive parent, incident evidence, disposition, cutover, resume,
rollback, provider, mailbox, vault, or private-data operation was executed.
Remaining: two-axis review, commit finalization, PR, CI, merge, and the separate
post-merge exact-master closure/protected-verifier/Issue 38 review chain.
```
