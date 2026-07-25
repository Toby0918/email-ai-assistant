---
last_update: 2026-07-25
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 34 content-free Container Audit task brief

## 1. Task name

```text
Issue #34 manual content-free ContainerAudit
```

## 2. Task type

```text
security
```

## 3. Current status

```text
accepted
```

## 4. Goal

Implement the pure, manual `ContainerAudit` contract from Issue #34 on remote
`master@ebe9f9ef85014abb670a6fb7b37fe2463f055469`. The audit must compare a
trusted immutable content-free policy with observations from seven injected
read-only metadata adapters, fail closed on any unknown, malformed, incomplete,
unreadable, aliased, reparse-bearing, or drifting evidence, and return only a
fixed status plus fixed aggregate counts.

## 5. Non-goals

- Do not perform a real Project Container audit or probe this host's ACL,
  volume, Git, worktree, runtime, SQLite, or filesystem security state.
- Do not create a CLI, default adapter, real Windows adapter, composition root,
  scheduler, background task, or automation entry point.
- Do not create, repair, move, copy, delete, rename, replace, or chmod a path.
- Do not create or modify an ACL, account, runtime, database, artifact,
  worktree, Config file, container directory, or volume.
- Do not open or enumerate ignored credentials, extension signing material,
  private datasets, raw mail, raw vault, recovery material, or
  `OperatorPrivate` content.
- Do not access a mailbox, provider, vault, private store, credential manager,
  DPAPI, BitLocker private content, or network service.
- Do not combine `ContainerAudit` with repository leakage scanning or the
  maintenance scan.
- Do not add an import or call from normal runtime, local service, cleanup,
  browser, frontend, or a scheduled workflow.
- Do not implement migration evidence, rehearsal, cutover, activation,
  rollback, cleanup, or Issues #35 through #40.
- Do not change the public HTTP API, public SQLite schema, AI-result schema,
  prompt, model route, provider default, browser permission, or mailbox
  command set.
- Do not merge the resulting pull request or close parent Spec #29.

## 6. Background and references

- GitHub Issue #29: governed Project Container specification.
- GitHub Issue #34: approved content-free manual audit ticket.
- PR #45: merged at the exact remote baseline for this task.
- Issues #32 and #33: closed prerequisites.
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/operations/issue32_managed_container_mode_task_brief.md`
- `docs/operations/issue33_protected_private_stores_task_brief.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`
- `docs/constraints/mechanical_rule_translation.md`
- `docs/constraints/ci_guardrails.md`
- `docs/operations/testing_checklist.md`
- `docs/operations/documentation_rules.md`

## 7. Scope

Expected implementation and test paths:

- `backend/container_audit/`
- `tests/test_container_audit.py`
- `tests/test_architecture_constraints.py`
- `AGENTS.md`
- Project Container architecture, tooling, linter, mechanical, structure,
  testing, ADR, migration, and status documentation
- this task brief

The maintenance scan, repository leakage scan, normal runtime, launchers,
browser code, workflows, mailbox package, provider package, vault package, and
private-store packages remain unchanged.

## 8. Technical approach

### 8.1 Public seam

The sole execution seam is:

```python
run_container_audit(
    *,
    policy: TrustedAuditPolicy,
    adapters: ContainerAuditAdapters,
) -> ContainerAuditResult
```

The function accepts no path, environment, Config root, HTTP value, browser
value, CLI override, secret, account, or host capability. There is no default
policy and no default adapter. A direct function call is the manual boundary;
later separately approved tickets own any real host composition.

### 8.2 Trusted policy

The frozen, repr-redacted policy separates reviewed expected values from
observed adapter evidence. It carries only content-free host-specific values
that Issue #34 cannot safely hardcode:

- schema version;
- expected Project Container opaque identity;
- expected container ACL fingerprint;
- expected disabled `OperatorPrivate` ACL fingerprint;
- expected fixed NTFS volume identity;
- exact approved linked-worktree opaque roster;
- whether approved worktrees must be clean;
- exact SQLite phase expectation: absent or stopped-and-present.

The policy cannot carry or relax the code-fixed nine-entry allowlist, Config
key allowlist, runtime versions, SQLite filename, metadata bounds, provider
defaults, path relationships, status schema, or public count schema. Missing,
duplicate, malformed, unsorted, or unknown policy evidence fails before any
adapter is called.

### 8.3 Code-fixed contract

The implementation fixes:

- top-level entries:
  `main`, `Runtimes`, `LocalData`, `RuntimeTemp`, `Logs`, `Artifacts`,
  `Worktrees`, `Config`, and `OperatorPrivate`;
- exact Config keys:
  `EMAIL_AGENT_LOG_LEVEL` and
  `EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS`;
- Config metadata limit: 16 KiB;
- Python version: `3.12.13`;
- SQLite runtime version: `3.50.4`;
- runtime executable relationship:
  `Runtimes/venv/Scripts/python.exe`;
- pinned runtime relationship:
  `Runtimes/python-3.12.13-sqlite-3.50.4`;
- normal database relationship:
  `LocalData/email_agent.sqlite3`;
- stopped-and-present SQLite state accepts no WAL, SHM, or journal sidecar;
- Config, Logs, and Artifacts are direct, non-recursive metadata inventories;
- Logs metadata is bounded to the current log, two rotated backups, and PID
  metadata; Artifacts direct metadata is bounded to 256 entries;
- `OperatorPrivate` is accepted only as disabled;
- raw vault and recovery are accepted only as not provisioned;
- public status is exactly `container_audit_passed` or
  `container_audit_failed`;
- public counts are exactly `accepted` and `rejected`, with one result counted.

These limits bound inspection. They do not approve arbitrary content or future
artifact semantics.

### 8.4 Injected adapters

`ContainerAuditAdapters` contains exactly seven target-bound read-only
adapters:

1. filesystem metadata;
2. ACL metadata;
3. volume metadata;
4. Git metadata;
5. worktree metadata;
6. runtime metadata;
7. SQLite metadata.

Adapters return strict frozen, repr-redacted evidence values, not a generic
`is_valid` boolean. Evidence contains only fixed enums, exact names where the
contract requires them, non-negative bounded counts/sizes, opaque identities,
opaque fingerprints, completeness flags, canonical/reparse/readability flags,
and stable relationship booleans. It contains no path, account, SID, branch
name, Config value, SQLite row, file content, exception, reader, handle, client,
key, or mutation callable.

### 8.5 Validation order

1. Validate the exact policy before invoking an adapter.
2. Validate filesystem evidence, the exact nine-entry direct inventory,
   Config key-only metadata, bounded Logs/Artifacts metadata, disabled
   `OperatorPrivate`, and not-provisioned vault/recovery states.
3. Validate fixed NTFS volume evidence against the independent expected
   identity.
4. Validate container and disabled-`OperatorPrivate` ACL evidence against the
   independent expected fingerprints.
5. Validate one `main` Repository Root and one Git common directory.
6. Validate the exact approved linked-worktree roster and common-directory
   relationships.
7. Validate the exact pinned Python and SQLite runtime versions and runtime
   relationships.
8. Validate the policy-selected SQLite absent or stopped-and-present metadata
   state, integrity, schema completeness, aggregate count, and sidecars.
9. Validate cross-adapter identity and volume bindings.
10. Repeat the seven observations in the same bounded order and require exact
    equality with the first validated snapshot.
11. Return the fixed success result only after the complete second pass.

Any first-pass failure stops further metadata reads. Any adapter exception,
invalid evidence, cross-domain mismatch, or second-pass drift maps to the same
fixed failure result without inspecting or formatting the exception.

### 8.6 Public result

The public result has no diagnostic detail:

```json
{
  "status": "container_audit_passed | container_audit_failed",
  "counts": {
    "accepted": 0,
    "rejected": 1
  }
}
```

Success uses `accepted=1, rejected=0`; failure uses
`accepted=0, rejected=1`. Counts never expose a partial stage, item name,
worktree count, database count, path, identity, fingerprint, matched value, or
native error.

## 9. Data structure or interface changes

### Database changes

None. The SQLite adapter returns content-free read-only evidence only. It
cannot write or expose rows.

### API changes

No HTTP API change. One pure internal Python audit interface is added.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real mailbox, provider, vault, private store, credential, or private
  dataset is accessed.
- [x] No real Container or host-security probe is implemented or run.
- [x] No secret-bearing content adapter or field exists.
- [x] Expected policy and observed evidence are independent.
- [x] OperatorPrivate content cannot enter the evidence or result.
- [x] Raw vault and recovery are represented only by the fixed
  `not_provisioned` state.
- [x] Public output contains only fixed status and fixed counts.
- [x] Unknown adapter exceptions are neither formatted nor logged.
- [x] Every adapter and test is synthetic, offline, and read-only.
- [x] The audit cannot be reached from normal runtime, cleanup, browser, or
  scheduled workflows.

## 11. Prompt injection protection

This task does not process email, attachments, prompts, or provider output.
Metadata names and adapter values remain untrusted data and cannot select a
call target, path, command, provider, mailbox, reader, secret source, or output
field. Unknown strings and enum values fail closed.

## 12. Acceptance criteria

1. Every Issue #34 acceptance criterion is satisfied.
2. Exact nine-entry inventory and exact-case names are required.
3. Unexpected entries, duplicate identities, aliases, reparse evidence,
   unreadable state, incomplete inventories, malformed values, and identity
   drift fail closed.
4. One `main` Repository Root, one Git common directory, approved worktree
   relationships, exact ACL fingerprints, and exact fixed NTFS volume identity
   are verified against independent trusted policy where required.
5. Exact Python/SQLite versions, normal SQLite filename/state, Config key
   allowlist, and bounded Logs/Artifacts metadata are verified.
6. OperatorPrivate remains disabled and raw vault/recovery remain not
   provisioned without opening their content or probing external stores.
7. Public success and failure expose only the two statuses and fixed
   accepted/rejected counts.
8. The package has no filesystem, ACL, volume, Git, subprocess, SQLite,
   mailbox, provider, vault, private-store, credential, logging, scheduling,
   mutation, or content-reader capability.
9. Normal runtime, cleanup, leakage scan, browser, root wrappers, and scheduled
   workflows do not import, reference, or invoke the audit.
10. Focused tests, architecture/static/mechanical guards, full regression,
    compile checks, status generation, maintenance scan, repository leakage
    scan, and diff checks pass.
11. Standards review has no P1/P2 findings and Spec review has no findings.

## 13. Test plan

The pre-agreed TDD seams are:

- public audit seam:
  `run_container_audit(policy=..., adapters=...)`;
- strict trusted-policy and evidence value seam;
- each of the seven target-bound synthetic adapter protocols;
- fixed public result seam;
- architecture guard seam for import, call-target, capability, maintenance,
  leakage, browser, and scheduled-workflow isolation.

Use RED -> GREEN vertical slices:

1. Fully valid synthetic policy and two-pass evidence return fixed success.
2. Exact nine-entry filesystem inventory, alias, reparse, unreadable,
   incomplete, malformed, and drift failures.
3. Independent ACL and NTFS volume expectation failures.
4. Unique Git root/common directory and exact worktree relationship failures.
5. Runtime, Config, Logs, Artifacts, OperatorPrivate, and vault/recovery
   failures.
6. SQLite absent and stopped-present metadata failures.
7. Adapter exception canaries, fixed public output, and second-pass drift.
8. Architecture and no-consumer/no-host-capability guards.

Run the focused audit test after each slice. Regularly run architecture,
mechanical, and affected project-layout tests. Final verification uses the
project Python 3.12.13 / SQLite 3.50.4 environment and includes full unittest
discovery, compileall, JavaScript syntax checks, manifest validation,
project-status generation, maintenance scan, repository leakage scan, and
`git diff --check`.

Pre-change focused baseline:

- 89 tests passed across project layout, Managed Container Mode,
  architecture, and mechanical suites; 1 host-capability test skipped.

## 14. Rollback plan

Revert only this branch's pure audit package, synthetic tests, mechanical
guards, and documentation. No real Container, host security, runtime, database,
worktree, mailbox, provider, vault, private store, credential, ACL, or external
state is created or changed.

## 15. Questions requiring human confirmation

None. Issue #34 defines the scope and the user authorized automatic acceptance
after TDD, dual-axis review, P1/P2 repair, re-review, and complete verification.
Real ACL/volume values, host adapters, preflight composition, migration
evidence, rehearsal, cutover, cleanup, or Issue #35 through #40 work requires
separate authorization.

## 16. Pre-execution checklist

- [x] Read the requested `$implement`, `tdd`, and `code-review` skills.
- [x] Read `AGENTS.md`, `CONTEXT.md`, and the current status log.
- [x] Read tooling, architecture, linter, task-brief, ADR, migration,
  mechanical, CI, and documentation rules.
- [x] Verified PR #45 merged as
  `ebe9f9ef85014abb670a6fb7b37fe2463f055469`.
- [x] Verified Issues #32 and #33 are closed.
- [x] Verified Issue #34 is open, `ready-for-agent`, and has no open blocker.
- [x] Verified remote `master` is exactly
  `ebe9f9ef85014abb670a6fb7b37fe2463f055469`.
- [x] Created clean independent worktree
  `D:\Projects\email_ai_assistant\.worktrees\issue-34-container-audit` and
  branch `codex/issue-34-container-audit`.
- [x] Confirmed root `master@f071781` and all pre-existing worktrees remain
  untouched.
- [x] Confirmed no real audit, mailbox, provider, vault, private-store,
  credential, or host-security access is needed.

## 17. Remote provider private-context checklist

Not applicable. Provider routes, remote input, runtime knowledge, privacy
transformation, and budgets are unchanged. All providers remain disabled.

## 18. Administrator stage-evaluation checklist

Not applicable. Raw-vault to evaluation staging remains disabled and unchanged.

## 19. Final dataset build and interactive judge checklist

Not applicable. No private dataset, provider judge, TTY workflow, or evaluation
report is opened or created.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. Manual mailbox sync and current-click evidence are unchanged.

## 21. Repository placement and operational layout checklist

- [x] No third placement mode is added.
- [x] The audit validates but does not construct, move, or repair placement.
- [x] The exact Managed Container nine-entry contract is code-fixed.
- [x] Trusted policy cannot be supplied or narrowed through public HTTP,
  environment, Config, frontend, normal runtime, or CLI.
- [x] Repository leakage scanning remains rooted at the Repository Root.
- [x] Maintenance scanning remains a separate repository-hygiene tool.
- [x] Tests are synthetic/offline and do not run a real audit.

## 22. Post-execution record

Actual changed files:

- Pure audit contract and validators:
  `backend/container_audit/__init__.py`,
  `backend/container_audit/adapters.py`,
  `backend/container_audit/audit.py`,
  `backend/container_audit/contract.py`,
  `backend/container_audit/filesystem_checks.py`,
  `backend/container_audit/policy.py`, and
  `backend/container_audit/system_checks.py`.
- Synthetic fixtures and acceptance coverage:
  `tests/container_audit_fixtures.py`,
  `tests/test_container_audit.py`,
  `tests/test_container_audit_contract.py`,
  `tests/test_container_audit_fail_closed.py`,
  `tests/test_container_audit_filesystem.py`,
  `tests/test_container_audit_sqlite.py`,
  `tests/test_container_audit_success.py`, and
  `tests/test_container_audit_system.py`.
- Mechanical isolation and documentation-date guards:
  `tests/test_architecture_constraints.py` and
  `tests/test_multimodal_documentation_contracts.py`.
- Generated handoff accuracy:
  `scripts/generate_project_status.py`,
  `tests/test_generate_project_status.py`, and
  `tests/test_mailbox_transport_constraints.py`, plus
  `docs/operations/project_status_log.md`.
- Boundary and operator documentation: `AGENTS.md`, `CONTEXT.md`, `README.md`,
  ADR 0009, the Project Container migration brief, tooling/architecture/linter/
  mechanical constraints, project structure, testing checklist, task-brief
  template, generated project status, and this task brief.

Test results:

- Every implementation and review repair was driven from an observed RED
  failure to focused GREEN. The focused ContainerAudit matrix has 38 passing
  tests.
- The post-review architecture/static/mechanical matrix has 70 passing tests.
- The first full regression exposed one stale expected front-matter date after
  this task updated `docs/operations/testing_checklist.md`; the focused RED was
  corrected by synchronizing that exact documentation contract.
- The first generated status RED exposed stale text that still grouped Issue
  #34 with unstarted Issues #35 through #40. The generator now reports the
  offline Issue #34 boundary without adding an executable/module import, call,
  composition, or consumer to the script. Its reviewed AST fingerprint,
  focused status contract, mailbox no-sync guard, and mechanical audit
  isolation guard pass.
- The repaired full unittest discovery passes 1,793 tests with 2 expected
  skips while both remote provider switches are explicitly disabled.
- Project Python is `3.12.13` and project SQLite is `3.50.4`.
- Python compileall passes for 383 files; all 10 frontend JavaScript files pass
  `node --check`; the browser-extension manifest parses successfully.
- Maintenance scan with `--fail-on-high` reports no findings. The explicit
  tracked-plus-untracked repository leakage scan reports `total=0`.
- `git diff --check` passes; Windows line-ending conversion notices are
  informational only.

Review results:

- Initial gap analysis found three P1 and several P2 omissions. The accepted
  implementation closes the direct-child binding, strict malformed-evidence,
  mechanical isolation, pinned-runtime, Logs-role, aggregate-bound, and
  acceptance-matrix gaps through RED-to-GREEN tests.
- Initial Spec review found two P2 gaps: the Git metadata did not prove the
  exact direct-child `main/.git` relationship, and root command wrappers were
  outside the consumer guard. Both were repaired and the final Spec re-review
  reported no findings.
- Standards review and re-review found nested Python, dynamically constructed
  capability, root-wrapper, and nested non-Python package-inventory escapes.
  Each P2 received a hostile RED fixture and a recursive exact-inventory or AST
  guard repair. Final Standards re-review reported no P1/P2 findings.
- Ordinary non-blocking P3: `tests/container_audit_fixtures.py` and some test
  methods are long. They remain test-only synthetic scaffolding; refactoring
  them is outside the narrow Issue #34 production contract.

Incomplete items:

- No Issue #34 implementation, P1/P2 repair, Spec finding, or required
  verification item remains.
- No real adapter, CLI, composition root, host probe, Container audit, repair,
  migration, cleanup, scheduled call path, mailbox/provider/vault/private-store
  access, or Issue #35 through #40 work was added.
- Delivery remains intentionally limited to a scoped commit, branch push, and
  non-draft pull request containing `Closes #34`. The pull request is not
  auto-merged, and parent Spec #29 remains open.

Follow-up suggestions:

- A separately authorized test-maintenance task may split the long synthetic
  fixture and test methods without changing the audit contract.
- Do not begin Issue #35 through #40 without separate authorization.
