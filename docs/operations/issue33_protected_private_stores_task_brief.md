---
last_update: 2026-07-23
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 33 protected private and external stores task brief

## 1. Task name

```text
Issue #33 Project Container protected-root enforcement for private stores
```

## 2. Task type

```text
security
```

## 3. Current status

```text
verification_complete_review_pending
```

## 4. Goal

Apply the authoritative `RepositoryPlacement.protected_roots` contract to every
existing private-knowledge, private-evaluation, mailbox-vault, recovery, and
strict external sales-policy location decision. Moving the Repository Root to
`email_ai_assistant\main` must never make another Project Container location
appear external.

## 5. Non-goals

- Do not implement Managed Container Mode from Issue #32.
- Do not implement the Container Audit or any work from Issues #34 through #40.
- Do not perform a real Project Container, Repository Root, runtime, data,
  private-store, vault, or recovery migration.
- Do not access a real mailbox, raw vault, private dataset, DPAPI material,
  BitLocker private content, provider, credential, or key.
- Do not change raw-vault encryption, removable-volume, NTFS, BitLocker,
  lock-state, recovery-volume separation, key-envelope, or recovery-rewrap
  contracts.
- Do not add provider, browser, public HTTP, SQLite, mailbox, background,
  polling, scheduling, cleanup, or hot-reload capability.
- Do not change public AI JSON, prompt, browser permissions, mailbox transport,
  or normal runtime dependency directions.

## 6. Background and authority

- GitHub Issue #29: Project Container specification.
- GitHub Issue #33: approved implementation ticket.
- GitHub Issue #30: completed `RepositoryPlacement` compatibility seam.
- PR #43: merged; Issue #31 is closed.
- Issue #30 is closed and is the sole blocker for Issue #33.
- Implementation base: remote `master` at
  `a42430d7433d84188558ab7ac5e5a32555a7ee60`.
- `AGENTS.md`
- `CONTEXT.md`
- `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md`
- `docs/decisions/0009-project-container-and-repository-boundaries.md`
- `docs/operations/project_container_migration_task_brief.md`
- `docs/security/private_knowledge_handling.md`
- `docs/constraints/tooling_constraints.md`
- `docs/constraints/architecture_constraints.md`
- `docs/constraints/linter_constraints.md`

The authoritative Managed protected-root set remains exactly
`(project_container,)`. That one root protects the Project Container itself,
`main`, `Runtimes`, `LocalData`, `RuntimeTemp`, `Logs`, `Artifacts`,
`Worktrees`, `Config`, `OperatorPrivate`, and every descendant. It must not be
reconstructed from the seven ordinary `OperationalLayout` paths or expanded
into nine narrower roots.

## 7. Scope

Expected additions or changes:

- `backend/project_layout/`
- `backend/private_knowledge/storage_policy.py`
- `backend/private_knowledge/snapshot_path.py`
- private-knowledge startup and CLI policy bindings
- `backend/private_evaluation/repository_path.py`
- private-evaluation stage and final repository policy bindings
- `backend/mailbox_ingest/drive_policy.py`
- `backend/mailbox_ingest/existing_vault_policy.py`
- mailbox-vault service and recovery preflight bindings
- `backend/mailbox_ingest/sales_policy_file.py`
- focused synthetic policy and architecture tests
- architecture, tooling, testing, security, operations, and status documents

## 8. Technical approach

1. Add one read-only, standard-library-only project-layout policy value that is
   created from freshly validated `RepositoryPlacement` evidence. Preserve the
   current flat-repository transition through a separately validated
   compatibility path, but fail closed on partial Managed placement.
2. Keep Managed protected roots as the single Project Container root and
   Standalone protected roots as Repository Root plus explicit state root.
3. Make each domain path policy consume the trusted policy value internally.
   No CLI flag, environment variable, config file, HTTP field, browser field,
   or ordinary request may provide, replace, narrow, or default the roots to an
   empty tuple.
4. Check both original and resolved target views against every protected root.
   Reject aliases, parent references, reparse components, missing or unreadable
   required state, and identity drift before private I/O or host-security
   probes.
5. Preserve create semantics for legitimate missing targets by validating the
   stable existing parent where the existing contract creates a new encrypted
   store or recovery file.
6. Map placement and native failures to each domain's existing fixed,
   content-free error family.
7. Revalidate both current and new recovery paths for recovery rewrap before
   opening key material. Keep recovery volume requirements unchanged.
8. Add mechanical guards so only approved isolated policy modules depend on the
   pure project-layout value and no public/runtime/browser surface can weaken
   the protected-root contract.

## 9. Data and interface changes

### Database changes

None.

### HTTP API changes

None.

### AI output JSON changes

None.

### Prompt changes

None.

### Backend policy changes

Add a pure trusted protected-root value and internal policy binding. Existing
public error families, encrypted formats, CLI commands, and operator arguments
remain unchanged.

## 10. Security and privacy checks

- [x] No real mailbox, vault, dataset, provider, DPAPI, or BitLocker access.
- [x] No email send, delete, archive, move, forward, or reply capability.
- [x] No credential, key, account, record, path, matched value, or native
  exception in public errors.
- [x] No new dependency or package.
- [x] Tests use only synthetic paths, temporary directories, injected identity
  evidence, and fake volume probes.
- [x] Raw-vault encryption and recovery-volume separation remain unchanged.
- [x] Private evaluation remains offline and aggregate-only.
- [x] Providers remain disabled by default.

## 11. Prompt injection protection

Not applicable. This task handles path metadata and fixed policy evidence only.
It does not process email bodies, attachments, prompts, or provider output.

## 12. Acceptance criteria

1. All Issue #33 acceptance criteria pass.
2. The Project Container root, all nine approved zones, and every descendant are
   rejected at every in-scope project-external storage seam.
3. Original and resolved path views, aliases, reparse components, required
   missing/unreadable state, and identity drift fail closed.
4. Legitimate synthetic external authority, candidate, snapshot, evaluation
   stage, evaluation dataset, vault, recovery, and sales-policy locations
   continue to pass their existing separation contracts.
5. Existing raw-vault, encryption, recovery, private-store separation, and
   fixed error contracts remain unchanged.
6. Public HTTP, browser, normal runtime, and CLI arguments cannot supply or
   weaken protected roots.
7. Focused policy, architecture, transport, and complete regression tests pass.
8. Standards review has no P1/P2 findings and Spec review has no findings.

## 13. TDD seams and test plan

The pre-agreed public seams are:

- `RepositoryPlacement.protected_roots` and the trusted protected-location
  policy derived from it.
- Private-knowledge authority, candidate, staging, and snapshot policies.
- Private-evaluation `.pkevalstage` and `.pkeval` repository policies.
- New and existing mailbox-vault plus init/current/new recovery policies.
- Strict external sales-policy file loading.
- Architecture and transport guards that keep the contract private and
  offline.

Use vertical RED -> GREEN slices:

1. Managed and flat protected-root derivation, identity, alias, and reparse
   behavior.
2. Private-knowledge storage and snapshot behavior.
3. Private-evaluation stage and final repository behavior.
4. Mailbox vault and recovery behavior, including current recovery rewrap.
5. Strict external sales-policy behavior.
6. Mechanical dependency and no-public-weakening guards.

Focused suites include:

```text
tests.test_project_layout
tests.test_private_knowledge_storage_policy
tests.test_private_knowledge_snapshot
tests.test_private_knowledge_runtime_bootstrap
tests.test_private_evaluation_repository
tests.test_private_evaluation_staging
tests.test_private_evaluation_dataset_builder
tests.test_mailbox_vault_policy
tests.test_manage_mailbox_vault
tests.test_mailbox_sales_policy_file
tests.test_architecture_constraints
tests.test_static_linter_constraints
tests.test_mailbox_transport_constraints
```

Final verification uses the project Python 3.12.13 environment, full unittest
discovery, compile checks, JavaScript syntax checks, manifest validation,
project-status generation, maintenance scan, repository leakage scan, and Git
diff checks.

## 14. Rollback

Revert only this branch's source, test, and documentation changes. No real
directory, ACL, volume, vault, recovery, runtime, mailbox, or provider state is
created or changed.

## 15. Human confirmation required

None for the approved Issue #33 implementation. Any scope expansion, real
migration, host-security operation, private-data access, provider access, or
destructive action requires new authorization.

## 16. Pre-execution checks

- [x] Read `AGENTS.md`, project status, required constraints, ADR 0009, and the
  Issue #30 task brief.
- [x] Confirmed PR #43 merged and Issue #31 closed.
- [x] Confirmed Issue #33 is OPEN, `ready-for-agent`, and blocked only by closed
  Issue #30.
- [x] Confirmed remote `master` is exactly `a42430d7433d84188558ab7ac5e5a32555a7ee60`.
- [x] Created clean independent worktree and branch
  `codex/issue-33-protected-private-stores`.
- [x] Preserved root `master@f071781` without pull, merge, rebase, or
  implementation.
- [x] Preserved all existing worktrees.
- [x] Focused pre-change baseline: 109 tests passed, 1 skipped.

## 17. Remote provider private-context checklist

No provider input, privacy transformation, runtime-card content, or provider
budget changes. Providers remain disabled and verification is offline.

## 18. Administrator stage-evaluation checklist

Path policy only. The existing exactly-200, dual-review, fingerprint, one-record,
hidden-key, distinct-format, fixed-output, and no-network contracts remain
unchanged.

## 19. Final dataset build and interactive judge checklist

Path policy only. The existing create-only publication, stage/final separation,
TTY, judge, aggregate-only, zero-retry, and no-production-switch contracts remain
unchanged.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. No sync or current-click evidence behavior changes.

## 21. Execution record

Actual files changed:

- Added `backend/project_layout/protected_location.py` and exported the
  immutable `ProtectedLocationPolicy`, including revalidation of an explicit
  Standalone placement without exposing a caller-supplied roots tuple.
- Bound private-knowledge authority, candidate, staging, and snapshot paths to
  the internally derived policy, including stable existing-parent evidence for
  legitimate missing create targets.
- Bound private-evaluation stage/final repository paths, mailbox new/existing
  vault paths, current/new recovery paths, and the strict external sales-policy
  reader to the same complete protected-root contract.
- Added `backend/mailbox_ingest/protected_storage_path.py` so mailbox path
  evidence is checked before any injected or host volume probe.
- Added request stripping and exact architecture guards that prevent public,
  CLI, environment, configuration, frontend, or ordinary-runtime protected-root
  weakening.
- Updated the relevant architecture, tooling, mechanical-rule, security,
  testing, operations, ADR, task-template, project-context, and entry-rule
  documents.
- Added synthetic/offline coverage for all Project Container zones, positive
  external stores, original/resolved views, aliases, reparse state, missing and
  unreadable evidence, identity drift, recovery rewrap, fixed errors, and
  dependency direction. A cross-domain matrix also proves an explicit
  Standalone state root stays protected while locations outside both
  Standalone roots remain valid; no Standalone private capability is enabled.

Verification:

- Pre-change focused baseline: 109 tests passed, 1 skipped.
- Each implementation slice was driven from an observed RED failure to focused
  GREEN.
- Current focused matrix after review fixes: 247 tests passed, 1 skipped.
- The Standards re-review casing-alias regression produced three failing
  subcases before the fix; the corrected targeted test and 96-test protected
  store matrix pass, with 1 expected skip.
- Pre-review full regression: 1,721 tests passed, 1 skipped, with both provider
  environment switches explicitly disabled.
- Post-initial-review full regression: 1,728 tests passed, 1 skipped, with both
  provider environment switches explicitly disabled.
- Project Python 3.12.13, SQLite 3.50.4, and all pinned dependency versions
  match the documented baseline.
- Python compile checks, all 10 frontend JavaScript syntax checks, browser
  manifest JSON validation, and 43 focused leakage/maintenance/status tests
  pass.
- Generated `docs/operations/project_status_log.md` records the Issue #33
  branch.
- `scripts/maintenance_scan.py --fail-on-high` reports no cleanup findings.
- `git diff --check` passes; line-ending conversion warnings are informational
  for the existing Windows checkout policy.
- Standards/Spec re-review and final staged-diff verification remain pending.

Open items:

- Initial Standards review reported one P2 exact reserved-field documentation
  mismatch; the architecture document and executable exact-list assertion are
  now synchronized. Its P3 stale front-matter dates were also corrected.
- Initial Spec review reported one P1 gap for explicit Standalone state-root
  propagation. Every in-scope domain policy now accepts and revalidates a
  trusted placement context, and the six new RED-to-GREEN cases cover private
  knowledge, snapshots, private evaluation, vault/recovery, and sales policy.
- The first Standards re-review reported one P2 Windows casing-alias gap in
  partial-Managed preclassification. Managed container, repository, and zone
  names are now compared with case-folded values before any flat-layout
  compatibility path can be selected.
- Standards P3 judgement call: private-knowledge and mailbox modules retain
  similar domain-specific path-evidence flows. This is non-blocking because
  their fixed error families and create/read semantics differ; any shared
  primitive refactor requires a separately bounded task.
- Standards and Spec re-review against
  `a42430d7433d84188558ab7ac5e5a32555a7ee60`.
- Scoped commit/push and a non-draft PR containing `Closes #33`.

Follow-up:

- Do not begin Issue #32 or Issues #34 through #40.
