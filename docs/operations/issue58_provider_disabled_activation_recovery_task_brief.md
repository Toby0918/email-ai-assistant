---
last_update: 2026-07-29
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 58 provider-disabled activation and legacy recovery task brief

## 1. Task name

```text
Issue #58 verify provider-disabled activation and legacy recovery transaction
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

Implement only Issue #58 from exact remote
`master@dcb53169f7c8e73b6bf5387a02b18d4e6741d6ee`. Prove, inside a
caller-owned synthetic sandbox, provider-disabled new-service activation,
classified failure, explicit journal-driven rollback, failed-Container
preservation, exact original topology restoration, and provider-disabled
legacy-service health.

## 5. Non-goals

- Do not start, stop, probe, discover, inspect, or modify any real service.
- Do not access or modify any real repository, worktree, ACL, Runtime,
  SQLite database, browser, mailbox, provider, credential, vault, private
  store, or private data.
- Do not accept an arbitrary launcher, process, command, executable, port,
  Config, role, path, environment file, environment mapping, or retry policy.
- Do not enable a provider, inherit provider settings, read legacy
  environment, write synthetic analysis into the legacy database, repair or
  delete retained state, or guess recovery operations.
- Do not implement Issue #59, modify Issues #38/#39, close parent Spec #50,
  merge the pull request, or perform any real lifecycle operation.

## 6. Background and references

- GitHub Issue #58, parent Spec #50, and closed blockers #56/#57.
- `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- `docs/decisions/0009-project-container-and-repository-boundaries.md`.
- `docs/security/project_container_cutover_contracts.md`.
- `docs/operations/project_container_migration_task_brief.md`.
- Issue #51 authorization and receipt contracts, Issue #52 journal
  classification, Issue #56 repository reversal, and Issue #57 managed
  publication receipts.
- Tooling, architecture, linter, mechanical, CI, documentation, testing,
  leakage, and maintenance constraints.

The dirty root and every pre-existing worktree are preserved. Work occurs only
in `D:\Projects\email_ai_assistant_issue_58_activation_recovery` on
`codex/issue-58-provider-disabled-recovery`.

## 7. Scope

Expected additions:

- `backend/cutover_service_lifecycle/` for closed activation, health,
  rollback, legacy-recovery, receipt, failure-classification, and real-lock
  contracts.
- Focused `tests/test_cutover_service_lifecycle_*.py` modules and synthetic
  sandbox fixtures.
- This task brief.

Expected synchronized changes:

- Issue #58 tooling, architecture, static, mechanical, security, decision,
  project-structure, status, testing, leakage, and maintenance contracts.
- The project-status generator and generated status log.

No frontend, provider client, mailbox, vault, private-knowledge,
private-evaluation, normal-runtime API, real service manager, CLI, workflow,
scheduler, dependency, cleanup, or arbitrary host adapter is in scope.

## 8. Technical approach

### 8.1 TDD public seams

Tests observe only these Issue-approved public seams:

1. `ProviderDisabledServiceController` with exact sealed new-service and
   legacy-service adapter roles;
2. strict start and health evidence bound to one fresh UUIDv4 nonce;
3. `ProviderDisabledLifecycleTransaction.activate_new_service()` consuming
   one complete Issue #57 `ManagedActivationReceiptSetV1`;
4. the code-fixed synthetic request and strict deterministic-rules,
   zero-provider-attempt, exactly-one-new-row activation result;
5. closed activation failure classification;
6. `rollback_and_recover_legacy()` through one exact journal-driven staged
   rollback adapter and one dedicated provider-disabled legacy Config;
7. strict activation, failed-Container, rollback, incident, and legacy
   recovery receipts;
8. the dual-authorization default-locked real lifecycle constructor.

Each vertical slice starts with one failing public behavior test, implements
the minimum behavior, and reruns the focused suite before the next slice.

### 8.2 Service-controller capability boundary

The controller accepts only exact nominal `NewServiceAdapter` and
`LegacyServiceAdapter` bundles. New service exposes fixed provider-disabled
start, exact health, one fixed synthetic analysis, exact persisted-row
observation, and exact containment/stop. Legacy service exposes only dedicated
provider-disabled recovery start, exact health, and stop. There is no generic
launch, command, process, shell, path, environment, Config mutation, provider,
database-query, retry, or alternate adapter surface.

Each start receives a controller-created fresh UUIDv4 nonce. Health must match
the started role, PID, start time, executable fingerprint, listening-port
owner, Profile fingerprint, LocalData/database role, nonce, and the exact
disabled primary/fallback provider state. A stale nonce, stale process, port
owner mismatch, Runtime/Config/Profile/LocalData drift, provider attempt, or
ambiguous identity fails closed.

### 8.3 New-service activation

Activation first reconstructs and verifies all four Issue #57 receipts and
their common operation/Profile/master/authorization chain. Runtime and Config
receipt fingerprints are bound to the fixed new-service start. No legacy
environment or provider setting is available to the adapter.

The controller submits exactly one code-owned synthetic request. The only
accepted result is a valid deterministic-rules result with zero provider
attempts and the same request fingerprint. A separate exact observation must
prove new LocalData contains exactly one corresponding synthetic row. The row
is retained as activation evidence. No customer or private content is used.

Known pre-mutation start rejection returns `SAFE_ABORT` without containment or
rollback. Known post-mutation validation failures return `ROLLBACK_REQUIRED`, prohibit
forward resume, and require explicit recovery authorization before rollback.
Identity, journal, reparse, provider-boundary, or safety ambiguity returns
`INCIDENT_STOP`. Incident containment may stop only the exact proven new
service identity; an unproven identity causes no guessed stop.

### 8.4 Journal-driven rollback

Rollback receives one exact sealed adapter whose stages are fixed:

1. prove the exact new service stopped;
2. preserve new external worktrees and Git administrative evidence;
3. move the canonical failed Container no-clobber and seal
   `FailedContainerPublicationReceiptV1`;
4. restore main, Git records, and all eleven original worktree directories
   strictly from committed journal entries;
5. reverify failed-Container classification and complete legacy
   prerequisites.

Every stage binds the same committed journal-head fingerprint. The sealed
failed-Container receipt must exist before the main-extraction/restoration
stage. No caller supplies a reverse action, path, role, count, or alternate
target. The retained state is exactly
`FAILED_CONTAINER_PRESERVED_WITH_LEGACY_MAIN_EXTRACTED` and is never reported
as a runnable nine-zone Container.

Before legacy start, exact parent/finance descriptors, original database and
sidecar state, legacy Runtime identity, canonical repository identity, Git
records, and the eight embedded plus three external original worktrees are
reverified.

### 8.5 Legacy recovery

Legacy recovery uses one code-owned `LegacyRecoveryConfigV1` with both
providers disabled and `reads_environment=False`. Its adapter has no
synthetic-analysis method, so recovery cannot write a synthetic row to the old
database. Start uses a new UUIDv4 recovery nonce distinct from activation.

Legacy health validates the exact legacy process, Runtime, port ownership,
Profile, legacy database role, nonce, and provider-disabled state. Start and
health are each attempted once. Any failure returns exactly
`INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED`; no alternate launcher, changed
Config, retry, or provider enablement is possible.

### 8.6 Receipts, content-free output, and real lock

Public values are strict immutable closed-schema values containing only fixed
statuses, fingerprints, allowlisted aggregate counts, and receipt
fingerprints. They contain no paths, commands, process command lines,
credentials, message content, database rows, SIDs/SDDL, Git names, exceptions,
or free text. Errors expose fixed codes; tests capture `repr`, stdout, stderr,
and logs for leakage checks.

The real constructor separately validates exact
`CutoverExecutionAuthorizationV1` and `RecoveryAuthorizationV1` bindings. A
missing, wrong, expired, malformed, test, or mismatched value is blocked. Even
with both exact values, the pre-Issue-#39 constructor returns
`BLOCKED_NO_APPROVED_COMMAND` and executes nothing.

## 9. Data structure or interface changes

### Database changes

None. Tests use only synthetic sandbox databases. The new-service synthetic
row is test evidence; the legacy synthetic database remains unchanged.

### API changes

Internal synthetic-only Python contracts and one default-locked real
constructor. No HTTP, browser, CLI, scheduler, service-manager, or workflow
entry point.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real service or host state is accessed or changed.
- [x] All executable lifecycle proof is confined to test-owned synthetic
  sandboxes.
- [x] No provider client, environment file, credential, mailbox, vault,
  private store, or private-data reader is available.
- [x] New and legacy roles, Runtime, Config, database role, port ownership,
  Profile, nonce, and process identity are exact and fail closed.
- [x] Reverse stages are fixed and journal-head bound; no arbitrary recovery
  action or cleanup capability is added.
- [x] Receipts, journal, stdout, stderr, logs, and errors remain content-free.

## 11. Prompt injection protection

No email or AI prompt is processed. Synthetic request, health evidence,
journal evidence, receipt mappings, and adapter results are untrusted and pass
only closed schemas, exact nominal types, fixed enums, bounded counts, UUIDv4
validation, and opaque fingerprints. No value is interpreted as a command.

## 12. Acceptance criteria

1. Every Issue #58 acceptance criterion has focused executable coverage or an
   exact mechanical guard.
2. Controller and lifecycle seams accept only fixed new/legacy roles and
   cannot invoke arbitrary launchers, processes, commands, Config, or
   provider settings.
3. New activation binds #57 Runtime/Config evidence, one fresh UUIDv4 nonce,
   exact health, one deterministic-rules request, zero provider attempts, and
   exactly one retained new LocalData row.
4. Every activation failure is classified; known validation failure requires
   explicit rollback, while identity/journal/reparse/provider/safety ambiguity
   incident-stops with exact-identity-only containment.
5. Rollback seals failed Container before main restoration and restores the
   exact original main, Git evidence, and 8+3 worktrees from one committed
   journal head.
6. Legacy recovery uses dedicated environment-independent disabled Config,
   changes no legacy analysis rows, binds a fresh nonce, and makes no retry or
   alternate selection after failure.
7. Real lifecycle construction stays locked without both exact authorizations
   and remains non-executable before Issue #39.
8. Windows sandbox, focused, affected, full, constraints, compile, frontend
   syntax, manifest, leakage, maintenance, diff, and dual-axis review gates
   pass.

## 13. Test plan

- TDD vertical slices: contracts; exact adapter roles; UUIDv4 start/health;
  #57 receipt binding; fixed synthetic activation; failure classification;
  incident containment; staged rollback; every reverse boundary; legacy
  recovery success/failure; content-free outputs; real lock; architecture.
- Cover success, every activation validation field, provider attempts, stale
  process/nonce, all rollback stage failures, failed target collision, main
  restoration, Git/worktree restoration, ACL/database preservation, legacy
  health, and incident containment.
- Run focused Issue #58 tests after every slice.
- Run affected Issue #51 through #57, ContainerAudit, architecture, static,
  mechanical, status, documentation, transport, leakage, and maintenance
  tests.
- Run the project `.venv` full unittest suite.
- Run compileall, frontend JavaScript syntax, extension manifest parsing,
  project-status generation, maintenance scan, repository leakage scan, and
  `git diff --check`.
- Perform parallel Standards and Spec review from the exact fixed point;
  repair and re-review every P1/P2 and record P3 without scope expansion.

## 14. Rollback plan

Before publication, revert only Issue #58 allowlisted files in this isolated
worktree. Test fixtures clean up only their own temporary sandbox after
assertions. No real host state exists to reverse. After publication, a normal
Git revert of the Issue #58 commits is sufficient.

## 15. Questions requiring human confirmation

None. The Issue and request fix the synthetic seam, forbidden capabilities,
test matrix, PR, and no-merge boundary. Any Issue #59 work, real constructor
unlock, real lifecycle operation, cleanup, merge, or parent-Spec closure
requires separate approval.

## 16. Pre-execution checklist

- [x] Read `$implement`, `$tdd`, `$code-review`, and GitHub workflow rules.
- [x] Read `AGENTS.md`, `CONTEXT.md`, status, task-brief, tooling,
  architecture, linter, security, and decision boundaries.
- [x] Live-verified Issue #58, parent #50, closed #56/#57, the native
  dependency graph, and exact remote master.
- [x] Inventoried and preserved the dirty root and every existing worktree.
- [x] Created a clean sibling worktree and `codex/` branch from the exact SHA.
- [x] Fixed the TDD public seams and confirmed no real host/private capability
  is required.

## 17. Remote provider private-context checklist

Not applicable. Providers stay disabled; no provider client or content is
available.

## 18. Administrator stage-evaluation checklist

Not applicable.

## 19. Final dataset build and interactive judge checklist

Not applicable.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable.

## 21. Repository placement and operational layout checklist

- [x] No real Container, service, Runtime, database, repository, worktree,
  ACL, browser, provider, mailbox, credential, vault, or private zone is
  accessed or changed.
- [x] Activation consumes exact #57 receipts and fixed new/legacy service
  roles only.
- [x] Rollback is staged, journal-head bound, no-clobber, and preserves failed
  Container plus new external/Git evidence.
- [x] Legacy recovery uses fixed provider-disabled injected Config and does
  not write synthetic analysis.
- [x] Real construction remains blocked before Issue #39.
- [x] Issue #59, Issues #38/#39, and parent #50 remain unchanged.

## 22. Post-execution record

Implementation and local validation are complete in the isolated worktree.

- Added the exact synthetic provider-disabled service controller, activation
  contracts, safe-abort/rollback/incident state machine, fixed staged rollback,
  dedicated legacy recovery, content-free receipts/results, and locked real
  constructor.
- TDD evidence includes intentional RED failures for missing contracts,
  controller, rollback, real lock, Windows retained-state evidence, status
  generation, exact Cutover-contract consumer allowlisting, and `SAFE_ABORT`.
- Focused: 26 tests passed in 29.183 seconds.
- Affected: 514 tests passed in 1676.426 seconds; 1 platform-conditional skip.
- Full: 2334 tests passed in 1857.377 seconds; 3
  platform-conditional skips.
- Constraint/architecture/status/transport/leakage suite: 165 tests passed in
  17.255 seconds.
- Compileall, frontend JavaScript syntax, extension manifest JSON,
  `git diff --check`, maintenance scan, and repository leakage scan passed;
  maintenance found no cleanup findings and leakage total was zero.
- No real service, repository/worktree, ACL, Runtime, SQLite, browser,
  mailbox, provider, credential, vault, private data, or root-worktree state
  was accessed or changed.
- Standards/Spec review, allowlist publication, remote CI, and PR recording
  remain to be completed below before handoff.
