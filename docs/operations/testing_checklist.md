---
last_update: 2026-08-02
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# 测试检查清单

## Issue #95 managed-unit publication checks

Run `tests/test_r2_managed_unit_publication_v2.py` and its architecture
companion. Prove all 8 managed-unit transitions progress only after the full
foundation prefix, use fresh authority and one effect each, reconstruct from
every journal cut, and retain source/partial/failed evidence with zero
destructive actions. Exercise PRE/POST/AMBIGUOUS and reject missing ACL or
unit-semantic proof, including SQLite semantics for Database.

## Issue #94 foundation publication checks

Run `tests/test_r2_foundation_publication_v2.py` and its architecture companion.
Prove all 17 foundation transitions progress only in order with fresh authority
and one effect each, including eleven unique worktrees. Restart from intent,
classification, effect, and commit bytes; PRE must require a new intent, POST
must commit without replay, and AMBIGUOUS must incident-stop.

## Issue #93 unified journal checks

Run `tests/test_r2_transaction_journal_v2.py` and its architecture companion.
Prove full and every-cut-point fresh reconstruction; reject torn framing,
unknown types, duplicate sequence, wrong predecessor/owner, and authority
replay. Exercise exact PRE/POST/AMBIGUOUS two-observation inspection and prove
the receipt leaves journal bytes/head unchanged with zero mutation and zero
append.

## Issue #92 Git-byte state checks

Run `tests/test_r2_git_byte_state_v2.py` and its architecture companion. Prove
exact blob/checkout/index agreement; reject same-size edits, EOL/filter drift,
index-only/staged state, ref/common-state changes, original admin changes, and
reconstructed checkout changes. Require fourteen refs, five stable common
roles, eleven original and eleven reconstructed worktrees, fresh-process exact
receipt reconstruction, and zero ignored/private content reads.

## Issue #90 V2 transaction single-action checks

Run `tests/test_r2_transaction_production_v2.py` and
`tests/test_r2_transaction_production_v2_architecture.py`. The behavior suite
must prove execute/resume/rollback domain separation, one matching action per
invocation, exact genesis/head/transition/plan binding, zero action on mismatch,
no retry after non-unit completion, and no-issuer dormancy. The architecture
suite must reject loops, batch, retry, direction switch, paths, private keys,
issuer, cross-root imports, deletion, cleanup, provider, mailbox, vault,
credential, and private-data capability.

```powershell
python -m unittest tests.test_r2_transaction_production_v2
python -m unittest tests.test_r2_transaction_production_v2_architecture
```

## Issue #89 evidence publication V2 and genesis checks

Run `tests/test_r2_evidence_production_v2.py` and
`tests/test_r2_evidence_production_v2_architecture.py`. The behavior suite must
prove one create-only reviewed publication, exact evidence/package/manifest
identity binding, strict `R2JournalGenesisV2` round-trip, fresh-process replay
rejection, review/domain/binding/freshness negatives, and no-issuer dormancy.
The architecture suite must prove physical root separation, pure genesis,
receipt/authority separation, and absence of paths, private keys, issuer,
mutation, deletion, cleanup, provider, mailbox, vault, or private data.

```powershell
python -m unittest tests.test_r2_evidence_production_v2
python -m unittest tests.test_r2_evidence_production_v2_architecture
```

## Issue #88 production preflight V2 checks

Run `tests/test_r2_preflight_production_v2.py` and
`tests/test_r2_preflight_production_v2_architecture.py`. The first suite must
drive every fixed verb through a fresh signed synthetic envelope and prove one
matching read-only role call; wrong binding/domain/verb/freshness must call no
role. The second suite rejects private-key, issuer, mutation, path, selector,
payload, provider, mailbox, vault, or cross-process-root capability and pins the
no-external-issuer dormant result.

```powershell
python -m unittest tests.test_r2_preflight_production_v2
python -m unittest tests.test_r2_preflight_production_v2_architecture
```

## Issue #87 production binding V2 checks

Run `tests/test_r2_production_binding_contracts.py` and
`tests/test_r2_production_binding_architecture.py`. They must prove the exact
final-master-derived binding, ten commands, four authority domains, four
operator roles, four public-key roles, eighteen production roles, canonical
round-trip, durable claim freshness/order/head binding, fresh-process replay
rejection, pure imports, exact exports, and the absence of private signing or
operational capability.

```powershell
python -m unittest tests.test_r2_production_binding_contracts
python -m unittest tests.test_r2_production_binding_architecture
```

## Issue #86 final-master closure checks

Run the two focused public-seam suites before any downstream closure ticket:

The source files are `tests/test_r2_final_master_closure_contracts.py` and
`tests/test_r2_final_master_closure_architecture.py`.

```powershell
python -m unittest tests.test_r2_final_master_closure_contracts
python -m unittest tests.test_r2_final_master_closure_architecture
```

They must prove the exact finite gap/gate/finding registries, canonical
final-master binding, completed same-binding evidence, the sole terminal status,
fixed error handling, missing/duplicate/mixed rejection, pure imports, explicit
exports, and disjoint receipt/authority types. These tests use no provider,
mailbox, vault, credential, private data, real host, external Git operation, or
GitHub mutation.

## Managed Container Mode

- Build only a synthetic `email_ai_assistant/main` fixture with pre-created
  `Runtimes`, `LocalData`, `RuntimeTemp`, `Logs`, `Artifacts`, `Worktrees`, and
  `Config`; do not create or move the real Project Container.
- Prove exact placement fails before Config read or service start, and reject
  missing, alias, reparse, unreadable, or drifting operational evidence with
  fixed content-free errors.
- Verify the runtime executable, SQLite, attachment temp, log, PID, artifact,
  worktree, and non-secret configuration paths resolve only to their approved
  zones. Repeated preparation must preserve the existing attachment directory.
- Accept only `EMAIL_AGENT_LOG_LEVEL` and
  `EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS` from the bounded Config descriptor; reject
  credentials, provider settings, private paths, and path overrides. Hostile
  ambient environment values must be ignored.
- Verify lifecycle `start`, `status`, `health`, one fixed `example.test`
  `analysis`, SQLite persistence, and `stop` through loopback-only synthetic
  adapters. Assert no state enters `main/outputs`.
- Assert request handlers receive the resolved `AppConfig`, all providers and
  private knowledge remain disabled, and neither launcher calls the ambient
  config loader or private bootstrap.
- Re-run repository-root guards so frontend assets, Git, status generation,
  maintenance, and leakage scanning remain scoped to `main`.
- Confirm there is no HTTP, SQLite schema, prompt, AI-result, browser-permission,
  mailbox, provider, vault, credential, or Issues #34–#40 surface change.

## Standalone Verification Mode

- Use one pre-created absolute temporary directory with
  `--standalone-state-root` for start, status, health, analysis, restart, and
  stop.
- Verify health and analysis only with injected adapters in automated tests;
  use a synthetic `example.test` request for an explicitly authorized manual
  loopback smoke.
- Assert SQLite, attachment temporary files, logs, and PID state stay below the
  temporary root and do not enter repository `outputs/`.
- Reject injected reparse identity for operational directories and reject
  reparse writable file targets before lifecycle actions.
- Assert the ignored repository `.env` is not loaded and every provider,
  mailbox ingest, private evaluation, private knowledge, and raw-vault
  capability remains disabled.
- Re-run existing configuration, server, lifecycle, architecture, frontend
  safety, attachment-limit, click-confirmation, persistence, and cleanup tests.
- Confirm the check does not create Managed Container state or perform a real
  Project Container migration.

## Repository placement compatibility seam and protected private stores

- Focused tests call only the public `RepositoryPlacement`,
  `OperationalLayout`, `ProtectedLocationPolicy`, and flat transition adapter
  interfaces.
- Managed synthetic fixtures prove the exact canonical
  `email_ai_assistant\main` relationship and the complete Project Container
  protected-root set.
- Standalone fixtures require an explicit synthetic or temporary state root,
  reject overlap, retain the state classification, and never infer a Project
  Container.
- Missing/unreadable identity, wrong names/parents, reparse evidence, alias
  drift, and identity changes return only fixed placement codes.
- All seven operational locations are absolute; Managed paths use the approved
  Project Container siblings and Standalone paths stay under the explicit state
  root.
- The transition adapter preserves current `.venv`, `outputs`,
  `outputs/attachment_temp`, and `.worktrees` locations without adding a third
  placement mode.
- Managed policy uses one Project Container root and rejects the container,
  `main`, `Runtimes`, `LocalData`, `RuntimeTemp`, `Logs`, `Artifacts`,
  `Worktrees`, `Config`, `OperatorPrivate`, and every descendant for private
  knowledge, private evaluation, mailbox vault/recovery, and strict external
  sales-policy locations.
- Positive synthetic external authority, candidate, snapshot, evaluation,
  vault, recovery, and sales-policy paths retain their existing separation and
  fixed-error contracts.
- Explicit Standalone placement fixtures reject both Repository Root and state
  root at every private path policy while retaining valid locations outside both;
  the verification launcher still disables every private capability.
- Vault tests preserve NTFS, removable, full-encryption, protection, unlocked,
  and separate-volume evidence. Recovery rewrap validates and revalidates both
  current and new recovery paths before private material is opened.
- Architecture tests pin exact internal consumers, reject arbitrary-root
  construction, strip hostile request roots, and reject environment/config/
  frontend/CLI weakening seams.
- Package guards reject mutating or external-capability imports/calls. Automated
  tests remain synthetic/offline and create no real Managed Container data.

## Manual content-free ContainerAudit

- Run `python -B -m unittest discover -s tests -p "test_container_audit*.py"`
  with the pinned project interpreter. All fixtures must use opaque synthetic
  identities and callbacks; never probe the real Container, ACL, volume, Git,
  worktree, runtime, SQLite database, credentials, or private stores.
- Verify the exact nine direct top-level directories and reject missing,
  unexpected, wrong-case, non-directory, alias, unreadable, non-canonical,
  reparse, incomplete, or drifting evidence.
- Verify independent container and disabled-`OperatorPrivate` ACL fingerprints,
  fixed NTFS volume identity and exact audited-object bindings, one `main`
  Repository Root/common directory, and the exact approved worktree roster.
- Verify the pinned Python/SQLite runtime objects and versions, exact
  `Config/settings.env` key-only inventory, bounded role-only Logs metadata,
  bounded Artifacts metadata, and both expected-absent and stopped-present
  `LocalData/email_agent.sqlite3` states.
- Assert Config values, file content, SQLite rows, Git/worktree content,
  OperatorPrivate content, raw vault, recovery, paths, accounts, SIDs, readers,
  clients, and native exceptions cannot enter evidence or output.
- Every adapter exception, malformed value, first-pass failure, cross-adapter
  mismatch, and second-pass drift must return the same fixed failure status and
  `accepted=0, rejected=1`; success is only the complete stable two-pass result.
- Run the two architecture guards that pin the package capability allowlist and
  reject all normal-runtime, cleanup, leakage, browser/frontend, root-wrapper,
  and workflow consumers. Do not add a CLI, default/real adapter, scheduler,
  maintenance integration, or host composition under Issue #34.

## No-clobber migration evidence package

- Run
  `python -B -m unittest discover -s tests -p "test_migration_evidence_*.py"`
  with the pinned interpreter. Every source repository and target must live
  under a test-owned temporary directory; never pass the real Repository Root
  to the create seam.
- Verify exact local branch refs and independent bundle `verify/list-heads`,
  Git object integrity, local-only remote fingerprints, branch/HEAD/upstream
  and ahead/behind counts, selected root plus linked worktree identities, and
  injected content-free NTFS/ACL/volume evidence.
- Restore modified/staged/mixed/deleted/renamed tracked paths and approved
  untracked source/tests/docs from separate index/worktree layers. Compare
  fixed porcelain status and `ls-files --stage -z` records byte-for-byte in a
  fresh temporary repository.
- Prove explicit approval cannot override credentials, signing material,
  SQLite/sidecars, logs, PID state, environments, IDE state, private data,
  caches, or outputs; excluded canaries must never reach the checked reader.
- Reject global/system Git config, ambient secrets and Git overrides,
  fsmonitor, unbounded Git stdout, timeout descendants retaining stdout,
  Windows execution before Job assignment, Windows assignment/resume cleanup
  failure, POSIX process-group cleanup after parent reap, skip-worktree,
  assume-unchanged, unmerged/symlink/submodule index, non-local refs, missing
  root worktree selection, reparse/hardlink/path escape, oversize input, and
  source/index/worktree drift.
- Verify required Git/host/selection/snapshot evidence, canonical JSON,
  manifest comment identity, every file SHA-256, exact cross-references,
  bounded counts/sizes, and fixed content-free public status/counts.
- Exercise existing target, target racer, stage swap, short/partial write,
  semantic failure before publication, wrapper error after exact commit, and
  package verification above the per-source-file size limit. Never overwrite
  or roll back a final target by pathname.
- Run architecture/static/mechanical/leakage guards and assert there is no CLI,
  normal-runtime/browser/workflow consumer, real package, service stop, real
  repository/worktree move, ACL mutation, provider/mailbox/vault/private-store
  access, or Issues #37–#40 implementation.

## Synthetic repository reparenting rehearsal

- Run
  `python -B -m unittest discover -s tests -p "test_reparenting_rehearsal_*.py"`
  with the pinned interpreter. The public seam must accept no path; every run
  creates its own marker-bound `issue36-synthetic-*` temporary directory and
  must leave it intact on return. Tests own a parent temporary directory and
  tear it down only after observing the preserved topology.
- Verify the baseline is non-trivial: three local branch refs, one local-only
  remote fingerprint, `ahead=1`, `behind=0`, exact tracked/index/worktree state,
  reviewed untracked source hashes, two linked branch/HEAD values, and one
  unchanged Git common-directory identity.
- Patch the Issue #35 checked reader and prove only exact reviewed dirty source
  is opened. Credentials, signing material, runtime, outputs, IDE/cache,
  SQLite, logs and private canaries must remain in the legacy source with
  unchanged metadata.
- Exercise both injected `repair` and `recreate` choices. Repair must move the
  same worktree object and repair both pointers. Recreate must preserve the old
  physical worktree and administrative metadata before adding a clean active
  worktree from the existing common directory; never clone, prune or delete.
- Compare post-state branch, HEAD, refs, remote, ahead/behind, index/status,
  file hashes, branch attachment, clean linked status and common identity.
  Validate exact `email_ai_assistant/main`, sibling legacy-source separation,
  and a real pass through the injected synthetic ContainerAudit composition.
- Inject failure at evidence package, legacy rename, Container publication,
  main publication, worktree publication, and ContainerAudit. Each result must
  be fixed `rollback_verified` and prove an original source or independently
  verified preserved rollback topology. Main/worktree/audit failures must put
  the complete Container at the single sibling rollback path, repair reviewed
  relocated worktrees, and pass independent package/Git/filesystem assertions.
- Replace the marker with identical text and reject its changed filesystem
  identity before publication. Force the identity reader to simulate inode reuse
  and still require the fixed sibling hard-link anchor to reject publication.
  Also reject marker/anchor reparse state, reparse scope components, a
  non-local remote both directly and after builder return, and any
  non-canonical temporary scope. Inject remote drift inside review capture and
  require the captured fingerprint to mismatch the fixed local bare remote.
- Pre-create one recreate target and require fail-closed before any other
  worktree directory or administrative record moves; an empty existing target
  is still a no-clobber violation.
- Replace the direct `Worktrees` directory with a Windows junction to an
  outside-sandbox directory. Both preflight and the final recreate gate must
  reject it before Git writes through the reparse path.
- Run the exact package/import/consumer guards. Assert no public `Path`, CLI,
  normal-runtime/script/frontend/cleanup/leakage/workflow consumer, real host
  adapter, destructive filesystem call, network Git verb, real evidence
  package or real workspace mutation.

## Synthetic Managed runtime and LocalData activation rehearsal

- Run
  `python -B -m unittest discover -s tests -p "test_runtime_activation_rehearsal_*.py"`
  with the pinned interpreter. The public seam has one keyword-only, no-default
  `adapters` parameter and the exact runtime/filesystem/database/lifecycle/probe
  bundle; it has no path or default host adapter.
- Use only caller-owned `issue37-synthetic-*` temporary parents. Build exact
  `main`, `Runtimes`, `LocalData`, `RuntimeTemp`, `Logs`, `Artifacts`,
  `Worktrees` and `Config` topology and bind every evidence identity to that
  actual synthetic topology before teardown.
- Verify exact Python 3.12.13, SQLite 3.50.4 and dependency-lock identity/hash
  before and after a network-free rebuild of
  `Runtimes\venv\Scripts\python.exe`. The legacy venv and runtime source remain
  unchanged and are never rebuild inputs.
- Require lifecycle-manager stop output plus an independent stopped probe to
  echo the code-fixed `pre_publication` phase before the first database call.
  A stop timeout remains nonzero `unknown`, preserves PID state, and cannot
  open the SQLite publication gate.
- Exercise create-only SQLite publication, distinct stable source/destination
  identities, exact pre-activation SHA-256/size/count equality, integrity/schema
  success, absent WAL/SHM/journal, and source re-observation. Start, health and
  analysis must echo a fresh activation nonce bound to the initial gate.
  Final stop/probe must bind the same service and activation token under
  `post_activation`, reject replayed/old stop evidence, use a fresh stop token,
  and precede one-row destination and unchanged-source checks.
- Freeze the reviewed synthetic CRX identity/hash before rehearsal, reject a
  later source tamper, publish only create-only into the browser-extension
  artifact role, and require filesystem/probe destination equality. The adapter
  surface contains no signing-material reader, copier or enumerator.
- Bind attachment temp, log, PID and non-secret Config to their exact Managed
  roles. Start only the rebuilt venv executable with both providers disabled,
  no key/private knowledge/provider client, literal `127.0.0.1` health and
  exactly one user-confirmed persisted `rule_fallback` analysis.
- Inject runtime/database/artifact race, reparse, existing target, dependency,
  integrity and health failures. Every case returns fixed failure, preserves
  source/legacy/competitor state, stops any service it started, and performs no
  provider, external-network, mailbox, vault, private-store, credential or
  signing access.
- Run exact package/import/consumer guards and assert the production module has
  no filesystem, SQLite, subprocess, network, ContainerAudit, migration-evidence
  or default-host capability. Do not create a real migration evidence package or
  activate any real runtime, database, artifact or Project Container.

## Locked Cutover Profile, authorization, and receipt contracts

- Run
  `python -B -m unittest tests.test_cutover_profile_contract tests.test_cutover_authorization_contract tests.test_cutover_receipt_contract tests.test_cutover_contract_architecture`
  with the pinned interpreter. Fixtures must use only fixed opaque fingerprints,
  bounded integers and closed enum values; do not read or probe a real host.
- Verify `CutoverProfileV1` accepts only the closed Issue #51 mapping, produces
  deterministic canonical UTF-8 JSON and SHA-256 identity, and rejects duplicate
  keys, unknown fields, booleans-as-integers, non-canonical bytes and every
  path/drive/directory/SID/SDDL/Git-ref/command/free-text surface. Hostile
  mapping keys/values, lone surrogates and cyclic tampered state must return
  only the fixed contract error or invalid status.
- Exercise the four exact real-host authorization value types independently:
  preflight, evidence publication, cutover execution and recovery. Assert exact
  type, operation, phase, profile, master, operator, validity and external
  authorization-fingerprint bindings.
- Prove the package has no `create`, `issue` or `mint` route for real-host
  authorization. `TestSandboxAuthorizationV1`, mappings, duck-typed values and
  every receipt type must fail the real-host authorization validator. Mutated
  exact-type Profile or authorization instances must be fully reparsed and
  return `BLOCKED_AUTHORIZATION_INVALID`.
- Verify every authorization mismatch returns only its allowlisted fixed code
  and aggregate accepted/rejected counts, without paths, identifiers, native
  exceptions, arbitrary text or input echo.
- Verify every `ReceiptEnvelopeV1` type/status/count/detail combination against
  its closed matrix. Canonical parsing must reject duplicate/unknown keys,
  unknown enums, non-string/unhashable receipt types, incompatible families,
  invalid integers, binding drift and fingerprint mismatch.
- Cover all required preflight, evidence, ACL, repository, worktree, runtime,
  database, artifact, Config, activation, rollback and incident-stop receipt
  families. Receipt parsing and validation never grant authority.
- Assert `default_operator_entry()` accepts no path, adapter, callback, command
  or authorization and always returns `BLOCKED_NO_APPROVED_COMMAND` with one
  content-free blocked aggregate.
- Run architecture/static/mechanical/transport/leakage guards and assert
  `backend/cutover_contracts/` imports no filesystem, environment, network,
  process, SQLite, ACL, Git/worktree, runtime, browser, mailbox, provider, vault,
  private-store, logging, scheduler or dynamic-import capability. Exercise
  nested/non-source package files, parent-relative, dotted-standard-library,
  stdin/builtin aliases including `breakpoint`/`delattr`/`setattr`,
  package-wide issuer helpers, and equivalent static/dynamic production
  consumer import variants, including rebound dynamic-import call aliases,
  against the AST guard.
- Do not run a real host adapter, preflight, evidence publication, migration,
  cutover, resume, rollback or cleanup. Issue #52's synthetic-only package is the
  first exact contract consumer; Issue #53 adds only its exact locked read-only
  contracts bridge; Issue #54 adds only its exact locked evidence-composition
  contracts bridge. Issues #55 through #59 remain separate.

## Synthetic crash-safe journal and recovery classification

- Run
  `python -B -m unittest tests.test_cutover_journal_record_contract tests.test_cutover_journal_durability tests.test_cutover_journal_chain tests.test_cutover_journal_recovery tests.test_cutover_journal_crash_matrix tests.test_cutover_journal_architecture`
  with the pinned interpreter.
- Verify strict canonical records reject unknown/duplicate/non-canonical input,
  wrong hashes, missing/duplicate sequence, wrong previous hash, wrong operation/
  profile/owner binding and invalid transition before any pending write.
- On both synthetic platform traces, prove pending write, pending-file barrier,
  no-replace publication, published-file barrier, namespace barrier and stable
  reread order. Namespace barrier is required before an intent can precede an
  effect; no test may claim real NTFS/Linux durability.
- Cover every `TransactionCutPoint` before/after forward and reverse intent,
  effect, observation and commit. Exact pre-action may be retried only after
  fresh resume/recovery validation; exact expected-post must not repeat the
  effect.
- Prove each recovered owner has a new lease, stale stores cannot append or
  release it, and an effect requires a non-copyable/non-serializable store
  permit backed by one shared single-use issuance for the exact current lease,
  round-trip-validated active durable intent, and durable journal head. Prove
  copied, serialized, retargeted, replayed, head-stale, pending, and
  observed-stale permits fail closed. A deterministic two-thread first-mint
  race must produce at most one permit/effect winner; append, restart, permit
  claim and effect mutation share the exact synthetic operation gate.
- Cover every `DurabilityCutPoint` on Windows and Linux traces: empty,
  truncated pending, exact pending, unbarriered final and namespace-barriered
  final must each receive a fixed read-only classification with zero blind
  effects. After namespace publication loses its acknowledgement, separately
  continue from `INTENT`, `RESUME_BOUND`, `EFFECT_OBSERVED`, and `COMMITTED`;
  each prior head must appear in the ordered stable-reread prefix before a new
  record or effect.
- Prove recovery authority is pre-bound before mutation, replacement authority
  fails, execute/resume/recovery expiry uses half-open time bounds, rollback
  still works after execute expiry, and reverse steps are exact journal-derived
  LIFO with swapped observations.
- Prove renewed valid resume authority can append a new `RESUME_BOUND`; durable
  `APPLIED`/`NOT_APPLIED` observations stay authoritative; pending forward and
  reverse directions classify and recover distinctly; mismatched
  Profile/master/operator, identity, transition mapping, or post-effect
  observation cannot append or execute.
- Snapshot inspection must leave both journal and effect snapshots byte/value
  identical and return only status, phase, receipt fingerprint and allowlisted
  counts. Corrupt chain, unknown observation, broken identity mapping or unsafe
  ambiguity must be `INCIDENT_STOP`.
- Architecture guards must pin exact files/exports/imports/signatures, the exact
  Issue #52 and Issue #53 contract bridges, zero other consumers, absence of
  paths/callbacks/host capabilities, and 300-line file/50-line function bounds.
- All fixtures remain content-free and in-memory. Do not access or mutate a real
  filesystem target, service, ACL, Git repository/worktree, Runtime, SQLite,
  provider, mailbox, vault, private store, credential or private data.

## Content-free Windows real-host preflight composition

- Run
  `python -B -m unittest tests.test_real_host_preflight_portable tests.test_real_host_preflight_topology tests.test_real_host_preflight_gate tests.test_real_host_preflight_baseline tests.test_real_host_preflight_composition tests.test_real_host_preflight_architecture tests.test_real_host_preflight_leakage`
  on every supported platform. Run
  `tests.test_real_host_preflight_windows` and
  `tests.test_real_host_preflight_windows_composition` only on Windows and only
  against caller-owned temporary sandboxes.
- Verify portable observations are frozen, slotted and repr-redacted, bind
  volume identity, exact 128-bit file ID, object type, parent identity,
  normalized-name fingerprint, attributes and reparse metadata, and reject
  wrong exact types, incomplete evidence, aliases, and identity drift. Linux
  must not invoke native Windows observation or claim NTFS, Windows file-ID,
  Windows ACL, or real-host evidence.
- Build each Windows fixture beneath a fresh `TemporaryDirectory` and bind its
  original/resolved root and exact child marker identities to one
  package-private single-use permit and an exact in-memory
  `TestSandboxAuthorizationV1`. Reject missing/replaced markers, wrong phases,
  permit replay, absolute/parent-relative escape, authorization/scope
  mismatch, hard-link alias/reparse components, unexpected filesystem/volume,
  unreadable state, and outside-root targets before observation. For every
  existing-object, absent-object, and volume observation, reopen and validate
  the exact root and marker and hold both handle chains through the operation;
  reject deletion or same-name replacement after scope creation. Never pass a
  real repository, Project Container, finance
  project, service, ACL, worktree, Runtime, database, artifact, Config,
  credential, mailbox, provider, vault, or private-data target.
- Observe the same opened object twice and prove the 128-bit file ID and volume
  identity are stable. Between complete passes, separately inject source or
  parent replacement, target appearance, reparse insertion, expected-volume
  mismatch, Git drift and ACL drift; each case must fail closed and preserve an
  independently observed outside/sentinel state.
- Require `CurrentTopologyPreflight` to call every source, target-parent,
  target-absence, reparse, Git, ACL, and volume reader in each of two complete
  passes. Only exact equality, completeness, `content_observed=false`, expected
  relationships and clear reparse state may produce an accepted
  `CurrentTopologyPreflightReceiptV1`.
  Reconstruct every callback value and require the exact source, parent,
  finance, and target-absence normalized-name projections selected by the
  independent canonical Profile snapshot captured before any host callback;
  explicitly reject callback mutation of caller-owned Profile roles and an
  existing approved target hidden by a missing decoy.
- Require `PreMutationGate` to bind the accepted topology, one exact operation,
  a fresh UUIDv4 nonce, a short half-open validity interval and one consumed
  attempt. It must repeat source/parent/absence/reparse/Git/ACL/volume checks
  and reject stale, replayed, different-nonce, retargeted, target-appearance,
  replacement, or drifting evidence. A failed attempt is also consumed.
  Bind a topology receipt to at most one gate under sequential and concurrent
  attempts. Reject direct allocation, public-envelope wrapping, caller reset,
  copying, deep copying, serialization, and exact-class retyping of
  receipt/gate capabilities.
- Exercise each `RealHostBaselineCollector` callback separately: source root,
  projects parent, finance project, volume, operator SID, source ACL, parent
  ACL and finance ACL. Assert exact call counts, role separation, deterministic
  canonical aggregation, bounded exact ACL counts, complete evidence, and
  `content_observed=false` before exact projection into the existing
  repr-redacted `HostBaseline`.
- Pass the exact seven read-only callbacks through
  `backend.real_host_preflight.audit_bridge` to the existing
  `ContainerAuditAdapters`. Diff review must show no change to the final
  nine-zone policy. `FinalAuditCompositionReadyReceiptV1` must not call any
  callback or `run_container_audit`, return an audit-pass result, or claim that
  a final layout exists or passed. Tampered or replaced callback readers and
  adapter/binding identity mismatches must fail before readiness. Prepare must
  capture a detached canonical policy; run must snapshot that policy again and
  rebuild adapters from the seven captured readers before callbacks. A
  malicious callback that relaxes caller-owned or stored clean-worktree policy
  must not change the unchanged audit result. Deterministically pause after
  validation and replace the composition policy or reader tuple; run and
  readiness must continue using only the single validated local capture.
- Assert the real operator entry accepts no path, callback, command, adapter, or
  test authorization and always returns `BLOCKED_NO_APPROVED_COMMAND`,
  `blocked=1`, and `executed=0`. No helper may create, issue, mint, sign, renew,
  or store real-host authorization.
- Inject hostile raw path, SID, SDDL, account, Git name/ref, file ID, command,
  callback-exception and native-error tokens. Recursively inspect receipt
  mappings/canonical bytes, fixed results, `repr`, stdout, stderr, and captured
  logs; none may contain a hostile value or an open diagnostic field.
- Run exact package/public/import/cross-package consumer guards. Only
  `audit_bridge.py`, `baseline_bridge.py`, and `contracts_bridge.py` may cross
  into ContainerAudit, migration-evidence, and cutover-contract packages.
  Reject service-control, ACL apply, rename/move/delete, repository/worktree
  mutation, Runtime build, database copy, artifact/Config publication,
  provider, mailbox, vault, private-store/private-data, evidence-publication,
  migration, cutover, recovery, cleanup, scheduler, network, arbitrary command,
  and normal-runtime/script/frontend/workflow capabilities.
- Run affected ContainerAudit, migration-evidence, cutover-contract,
  architecture/static/mechanical/documentation/leakage tests, then the full
  unit suite and read-only maintenance scan. Green tests prove only locked
  composition and sandbox behavior; Issues #55 through #59 remain separate.

## Reviewed Migration Evidence publication and verification

- Run
  `python -B -m unittest tests.test_migration_evidence_publication_review tests.test_migration_evidence_publication_commit_binding tests.test_migration_evidence_publication_create_verify tests.test_migration_evidence_publication_package_observation tests.test_migration_evidence_publication_receipts tests.test_migration_evidence_publication_operator tests.test_migration_evidence_publication_architecture tests.test_migration_evidence_verifier_process tests.test_migration_evidence_verifier_architecture`
  with the pinned interpreter. Every repository, worktree, package, and target
  must be created by the fixture below one test-owned `TemporaryDirectory`.
  Never pass the real Repository Root, an existing worktree, or a real package
  target.
- Review must consume only the exact `CutoverProfileV1` dirty-source, local-ref,
  worktree, package-target, Git, and `RealHostBaseline` selections. Assert the
  complete `MigrationEvidenceReview` remains module-owned and in memory while
  `MigrationEvidenceReviewReceiptV1` exposes only opaque fingerprints and
  bounded counts. Remove and recreate the same package-target parent while
  forcing its identity fingerprint to collide; claim must still reject because
  the fixed synthetic marker hard-link anchor is missing.
- Create must require exact `EvidencePublicationAuthorizationV1`, exact review
  receipt, and exact confirmed review fingerprint. Mutate each Profile,
  selection, dirty-source, ref, worktree, Git, HostBaseline, target, review,
  receipt, authorization, and confirmation binding independently and require a
  fixed failure before or without publication.
- Assert create reruns complete discovery and fresh HostBaseline collection,
  preserves absent-target create-only/no-clobber semantics, and binds the
  confirmed source snapshot, creator-owned staged package/manifest/identity,
  resulting review, authorization, and aggregate counts into
  `MigrationEvidenceCreatedReceiptV1`. Post-rediscovery byte drift and
  post-commit same-review replacement must fail closed.
- Run verification only through the fixed separate read-only process. Require a
  bounded first read whose exact bytes enter the independent payload verifier,
  an identical target reread, and independent package/manifest hash and count
  recomputation. Timeout, non-zero exit, malformed/duplicate/unknown response,
  corruption, target collision, replacement, ABA substitution, and manifest
  mismatch must produce only fixed rejection.
- Architecture tests must prove creator modules cannot import, construct, or
  call the independent verifier. The verifier may import only the exact-payload
  core verify bridge, use `O_RDONLY`/read-only ZIP package access, and own no publication,
  create, write, replace, rename, link, unlink, remove, or delete capability.
  Pin the fixed worker module, `shell=False`, sanitized environment, bounded
  request/response/timeout, stderr discard, and whole-process-tree cleanup.
- Require `MigrationEvidenceReviewReceiptV1`,
  `MigrationEvidenceCreatedReceiptV1`, and
  `MigrationEvidenceVerifiedReceiptV1` to match exactly on operation, Profile,
  master, review/selection/Git/host bindings, package and manifest hashes,
  package identity, and applicable counts before
  `MigrationEvidenceReceiptSetV1` exists. Assert every receipt and the Set fail
  the exact real-host authorization validator.
- Before Issue #39, real review/publication/verification entries must reject
  missing, wrong-phase, malformed, and `TestSandboxAuthorizationV1` input and
  remain fixed locked even for structurally valid real authorization.
- Capture receipt/result `repr`, stdout, stderr, and logs for hostile synthetic
  inputs. Reject any path, ref, object ID, worktree name, command, content,
  native error, or exception text. No test may perform real host preflight,
  service stop, repository/worktree move, ACL apply, Runtime build, database
  copy, provider, mailbox, vault, private-store, or private-data access.
- Review the package description mechanically: it is evidence, not backup,
  Runtime artifact, private-data container, or migration authorization.

## Issue #55 focused acceptance

1. Run `test_cutover_host_mutation_contracts`,
   `test_cutover_host_mutation_portable`,
   `test_cutover_host_mutation_operator`, and
   `test_cutover_host_mutation_architecture` on every platform.
2. On Windows, run `test_cutover_host_mutation_windows_acl` and
   `test_cutover_host_mutation_windows_filesystem` only with test-created
   temporary NTFS roots.
3. Verify exact token SID binding, the protected no-add-child construction
   guard, child-insertion exclusion, protected three-principal final DACL,
   owner/group preservation and mechanical SACL non-update, parent/finance
   exact equality, source reparse/incompatibility, and eight inherited zones.
4. Verify durable-INTENT-first parent-handle-relative `FILE_CREATE`,
   directory/file/move effects, ancestor/reparse/identity drift, target race,
   cross-volume rejection, no-replace, and the same file ID after publication.
5. Run affected Issue #51/#52/#53/#54 architecture and contract suites, full
   unit tests, documentation/constraint checks, leakage checks, and the
   read-only maintenance scan. Do not interpret green tests as real-host
   authority.

## Issue #56 focused acceptance

1. Run
   `python -B -m unittest discover -s tests -p "test_cutover_repository_transaction_*.py"`.
2. Require exact 8 embedded + 3 external scope binding, complete forward and
   reverse boundary sets, original Repository Root identity at `main`, original
   physical/admin preservation before counterpart creation, exact failed-state
   retention, and full restoration.
3. Require durable INTENT/OBSERVED/COMMITTED triplets, all four crash gaps in
   both directions, explicit-reverse `ABORTED/NOT_APPLIED` before-effect
   reconciliation, missing-fact-only completion after effect,
   `SAFE_ABORT`/`SAFE_COMMIT_FACTS` exact classification, and `INCIDENT_STOP`
   for ambiguity without replay. Require an explicitly repeated reverse call
   to restore the exact original topology after every safely classified
   reverse crash gap.
4. Require target/admin collision, reparse, out-of-scope/volume, dirty/ref,
   physical/admin/executable/topology drift, same-name admin reuse,
   unsafe Git config/hook, unexpected admin namespace, invalid actual
   observation, final-zone inventory, after-INTENT target race, no-clobber,
   content-free
   journal/receipt/repr/stdout/stderr, and locked real-constructor tests.
5. Run affected Issue #51-#55, ContainerAudit, reparenting, architecture,
   static, mechanical, documentation, status, and maintenance suites before the
   full test command. Synthetic success is not real cutover authority.

## Issue #57 focused acceptance

1. Run
   `python -B -m unittest discover -s tests -p "test_cutover_managed_activation_*.py"`.
2. Require exact four-adapter composition, same-chain content-free receipts,
   fresh Runtime creation from Python 3.12.13 plus a complete dependency lock
   and captured bytes from the hash-locked offline wheelhouse, startup-hook
   rejection, held exact-tree verification, child-handle-relative
   publication, junction/reparse/ADS/extra/missing rejection, and fixed
   `-X frozen_modules=on -I -B -S`
   self-verification by the newly created Runtime. Require fixed archive/tree
   budgets, held-handle source bounds, pre-parser central-directory and
   pre-sort enumeration gates, bounded streaming extraction/hash, exact
   import-leaf proof without installed-code execution, in-sandbox Python
   source, typed receipt-set round trip, and transient child/root-ADS races
   that return no receipt and create no execution marker.
   The in-sandbox Python source must also prove a complete canonical-tree
   manifest, held write/delete-blocking source entries, reparse/ADS and
   post-authorization drift rejection before execution, early wheelhouse and
   remaining-aggregate limits, incremental stdout overflow termination, and
   a bounded deterministic held-source `managed-startup.zip` containing the
   complete approved `encodings` package plus held code-fixed
   `python312._pth`/`python._pth` isolation sentinels that order the archive
   before target directories and prevent transient pre-script
   `encodings.aliases`, frozen-`codecs`, and target `sitecustomize.py` marker
   execution.
3. Require stopped-service receipt and write-blocking source-handle coverage,
   WAL/SHM/rollback-journal rejection before copy and after final target
   verification, read-only SQLite integrity without application-row
   inspection, durable create-only copy, stable hash, and unchanged source
   identity.
4. Require profile-bound CRX format/size/hash copy and deterministic
   non-secret closed-schema Config publication. Cover collision, input drift,
   partial flush/copy failure, immutable-scope retargeting, ADS target names,
   held-parent replacement, concurrent writer, post-verification CRX mutation,
   source replacement, forbidden dynamic readers, no cleanup, content-free
   outputs, and locked real constructors.
5. Run affected Issue #37 and #51-#56 contracts/architecture, constraints,
   documentation, status, leakage, maintenance, and the full unit suite.
   Linux portable tests make no Windows execution claim; synthetic success is
   not real activation or cutover authority.

## Issue #58 focused acceptance

1. Run
   `python -B -m unittest discover -s tests -p "test_cutover_service_lifecycle_*.py"`.
2. Require exact new/legacy role adapters, the complete Issue #57
   operation/Profile/master/authorization receipt chain, verified
   Runtime/Config receipts, fresh UUIDv4 nonces, disabled providers, no
   legacy-environment inheritance, and exact health binding for PID, start
   time, executable, port owner, Profile, `LocalData` role, nonce, and
   provider state.
3. Require one fixed synthetic activation request, deterministic-rules output,
   zero provider attempts, and exactly one matching row in new `LocalData`.
   Legacy recovery must use its dedicated injected disabled Config and must
   not write a legacy synthetic row.
4. Cover successful activation, known pre-mutation `SAFE_ABORT`, every known
   post-mutation validation failure,
   every reverse boundary, immutable rollback-plan/stage evidence,
   unexpected-exception incident containment, legacy recovery failure,
   content-free outputs, and locked real constructors. The Windows sandbox
   must exercise the complete Issue #56 forward/reverse topology, resume every
   committed reverse boundary, reject a pre-existing failed-Container
   collision, and prove exact restoration of main, Git records, and all eleven
   worktrees while retaining failed/new evidence.
5. Run affected Issue #51-#57 lifecycle/architecture suites, constraints,
   documentation, status, leakage, maintenance, and the full unit suite.
   Synthetic success does not authorize a real service probe or operation,
   Issue #59, Issues #38/#39, merge, or parent Spec #50 closure.

## Issue #59 focused acceptance

1. Run the portable composition suite:
   `python -B -m unittest tests.test_cutover_composition_architecture tests.test_cutover_composition_operator_lock tests.test_cutover_composition_receipt_chain tests.test_cutover_composition_coverage_contract tests.test_cutover_composition_leakage tests.test_real_host_preflight_composition_root tests.test_migration_evidence_publication_composition_root tests.test_cutover_transaction_composition_root`.
2. On Windows, run
   `python -B -m unittest tests.test_project_container_composition_windows_end_to_end`.
   It must use only caller-owned temporary sandboxes and end at
   `LEGACY_RECOVERED` after actual synthetic preflight, evidence, ACL,
   repository/worktree, managed publication, failed activation, failed-
   Container preservation, reverse restoration, and legacy health. The
   ACL-through-activation forward roles must pass through transaction
   `execute()` before the committed journal prefix enters rollback. Assert
   the accepted #55 ACL policy is the #56 Profile ACL policy, the #56 forward
   receipt supplies the journal state, the #58 lifecycle consumes the exact
   #57 receipt-set fingerprint, and new-service data-role evidence equals the
   actual #57 database receipt. Construct no substitute publication receipt.
3. Run all affected #51-#58 contract, architecture, race, crash, no-clobber,
   leakage, real-lock, and Windows sandbox suites. Confirm every
   `SyntheticCrashGap` and all eleven worktree restoration paths remain
   covered.
4. Run compile, documentation/front-matter, architecture, static-linter,
   mechanical-rule, maintenance, repository-leakage, and diff checks, followed
   by the full unit suite from the final integrated snapshot.
5. Confirm every real constructor/entry rejects test authorization and returns
   `BLOCKED_NO_APPROVED_COMMAND` after valid real authorization. Confirm no
   operator root is imported by product runtime, browser, cleanup, scheduler,
   script, or workflow code. Confirm backend packages contain no executable
   test binder and test-only assembly cannot select or outlive its internally
   owned temporary scope. Confirm the scope owns every component
   `TemporaryDirectory` and closing it blocks each role/journal callback
   before the underlying fixture callback. Inject cleanup failure and a
   concurrent close/callback race; the scope must become irreversibly inactive
   first, invoke zero new underlying callbacks, and never expose a half-cleaned
   active lease.
6. Confirm every partial chain is an exact approved prefix, linked
   prior/current journal heads are exact, the terminal receipt changes the
   chain fingerprint, resume/rollback verify the initial head before a role,
   authorization expiry is rechecked before every boundary, and one journal
   owner rejects gate replay across composition objects.
7. Confirm #38 remains open/ready-for-human, R1 remains `NOT EXECUTABLE`, #39
   remains unstarted, and no real authorization or operation was issued.
8. The handoff must state that merging #59 changes the governing master,
   invalidates old R1, and requires all fourteen #38 approval items plus a new
   R2 against the exact final master before #39 can be considered.

## Issues #70-#83 R2 remediation acceptance

1. Run every issue-focused contract, architecture, static, process, Windows,
   journal-gap, recovery, audit, lifecycle, and leakage suite before its
   independent Conventional Commit.
2. Run `python -B scripts/verify_r2_synthetic_topology.py` on Windows. Require
   exact status `R2_SYNTHETIC_VERIFICATION_COMPLETE`, terminal
   `CUTOVER_SUCCESS`, counts 3 process types, 4 authorization domains, 9 zones,
   1 repository, 11 worktrees, 4 managed units, 2 independent audits, and 70
   semantic gap cases, with zero provider attempts, leakage, and real-host
   operations.
3. Confirm Start A performs one code-fixed `rule_fallback` analysis and one
   synthetic database write, then stops and passes the stopped audit. Confirm
   Start B uses a fresh process/nonce, performs no analysis or write, and passes
   a fresh final-running audit before final seal.
4. Confirm every forward and reverse semantic gap uses a fresh sandbox and
   enforces exact absent/present/ambiguous classification with no blind replay.
5. Confirm the three operator process types use real local stdin/stdout/stderr
   TTYs, execution and recovery use different fixed verbs, and all four
   authorization domains are nominally distinct. Public output must remain
   aggregate-only and content-free.
6. Confirm portable tests make no NTFS, ACL, TTY, process-isolation, or native-
   durability claim. Windows claims require the fresh physical NTFS run.
7. Confirm obsolete batched publication, R1 verification, in-process operator
   substitute, self-certified audit, and legacy R2 success are unreachable.
8. Record fresh criteria, matrix, script, bundle, complete-surface, and package
   fingerprints. The prototype fingerprint remains non-authorizing prior art.
9. Run `python -m unittest discover -s tests`, maintenance scan, repository
   leakage scan, generated-status check, and Standards/Spec dual review. Fix
   every P1/P2 finding and re-review before handoff.
10. Confirm #38, #50, and #39 remain unchanged, every real entry remains
    `BLOCKED_NO_APPROVED_COMMAND`, and no real command or host operation ran.

## Option C 多模态离线门

- all providers disabled by default；自动化只使用 synthetic DOM/media fixtures、fake provider 和 injected clock，不读取邮箱、不访问网络、不读取 `.env` 或 key。
- 覆盖 `exmail_visible_context.js` 的顶层/唯一可见同源 frame、可靠线程分段与 current-only 降级；覆盖 `exmail_visible_resource_classifier.js` 对业务内联图、签名头像、logo、tracker、隐藏/外部/归属歧义资源的分类。
- 覆盖图片、PDF 页面、DOCX/XLSX 内嵌媒体的清洗、大小限制、临时文件清理与 source 绑定；无文字业务照片只允许视觉定性结论。
- 覆盖 `openai_multimodal_client.py` 的固定 `https://api.openai.com/v1`、`gpt-5.6-sol`、Responses API、`text={"verbosity":"low"}`、`store=false`、`max_retries=0`、no tools 和 2,400 output tokens。OpenAI omits `text.format`; the JSON-only prompt is enforced by strict local validation.
- 覆盖 one OpenAI multimodal primary call、eligible failure 后 one DeepSeek text-only fallback、deterministic rules last；privacy/private-artifact/routing/budget block 必须是 zero fallback calls。
- 预算矩阵固定为 60-second POST wait、55-second backend、35-second OpenAI、10-second DeepSeek、12-second fallback minimum、8-second parser、5-second reserve；前端另有独立的 20-second resource collection。
- 覆盖 text/hybrid evidence、matching attachment insight 的 visual-only 定性增强、body-only fixed cross-language bridge，以及拒绝 global fields、identity、protected traits、precise facts、commands、commitments 和 outcomes。
- Tasks 1-7 的离线实现已通过各任务 review-clean 门；Task 8 只对齐文档。Task 9 synthetic provider and current-clicked Tencent smokes are complete。
- Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete: one OpenAI attempt was intercepted before network access, exactly one DeepSeek text-only request was made, DeepSeek SDK retries were zero, and no SQLite write occurred. The root `.env` was unchanged.
- Attachment Task 5 remains valid acquisition/cleanup evidence only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Current/history alignment, attachment coverage, deterministic reconciliation, and private human gold-standard gates now pass offline; branch integration and any new live operation still require their own authorization. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.

## Labeled MOQ grounding release checks

- Verify the finite accepted labels are `MOQ`, `minimum order qty`, `minimum order quantity`, `最低起订量`, and `最低订购量`; tests use recreated synthetic quantities only.
- Verify one-to-four alternatives only and the closed canonical unit set; an unknown-unit remains a local negative.
- Verify parser-owned source spans and that the complete alternative set is indivisible: consumers cannot split or omit one member.
- Verify bare slash pairs, dates, ratios, phone-like values, contact/signature clauses, compact quotation rows, and pending/non-final claims produce no final labeled MOQ fact.
- Verify invalid, unitless, unknown-unit, non-final, omitted-member, changed-member, and invented-unit model MOQ claims fail closed.
- Verify final labeled MOQ closes only the quantity request; sample, attachment, lead-time, quotation, and other open items retain their independent evidence state.
- Verify provider claim that a locally known MOQ remains pending falls back only for the conflicting public field, while unrelated grounded fields remain eligible.
- Verify local extraction remains the authority for exact MOQ alternatives; a provider cannot invent, replace, or complete an alternative member.

### Release markers

- Accepted label: `MOQ`
- Accepted label: `minimum order qty`
- Accepted label: `minimum order quantity`
- Accepted label: `最低起订量`
- Accepted label: `最低订购量`
- Local unknown-unit rejection.
- Conflicting public field fallback.
- Unrelated grounded fields remain eligible.

## 必测场景

- 普通客户询盘。
- 空正文邮件。
- HTML 邮件正文。
- 含引用历史的邮件。
- 含付款、合同或交期风险的邮件。
- 含 prompt injection 文本的邮件。
- AI 返回不可解析 JSON。
- 后端服务不可用。
- Cleanup Agent 只读扫描报告生成。
- 项目状态日志可以生成并反映当前阶段。
- 后端最小骨架不违反架构依赖方向。
- 脱敏 golden 样例集覆盖主要邮件类型。
- 本地规则分析器输出与 golden 样例预期保持一致。
- `start` 在启动进程前恰好清理一次过期附件，且新鲜附件保留。
- `restart` 在 stop/start 序列前恰好清理一次，不通过嵌套 `start` 重复清理。
- 附件清理失败返回通用可操作错误，不停止或启动服务，也不暴露文件名、内容、私有 URL、cookie、token、OCR 文本或私有路径。
- `status` 和 `/api/health` 不读取或显示附件内容。

## Tencent Exmail extension checks

- Click the extension icon and verify the side panel remains open after clicking or scrolling inside Tencent Exmail.
- Open one Tencent Exmail message and click `Analyze current email`.
- Verify one current-email payload is sent after the click.
- Verify message-scoped selected-text fallback works only for user-selected email content in the currently opened Tencent Exmail message.
- Verify local backend unavailable state is readable.
- Verify the extension does not send, delete, archive, move, or reply to mail.
- Confirm unpacked extension version `0.2.3`, and click `Reload` after updating its files.
- Verify only image, PDF, XLSX, and DOCX resources visibly associated with the opened message are eligible after the click.
- Verify the configured bounds: 5 files, 10 MiB per file, and 25 MiB total.
- If Tesseract is unavailable, verify image OCR degrades to metadata-only while email-body/rule analysis continues.
- At 320px width, verify the task card shows conclusion, current request, next step, key facts, and must-check items before any detail section.
- Verify history, attachments, risk rationale, extra actions, and technical information are closed native `<details>` on first render.
- Verify extension and local debug use shared `render_analysis.js` plus `analysis_components.css`.
- OpenAI success shows `OpenAI GPT-5.6 Sol`; DeepSeek fallback shows exactly `OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。`.
- Rule fallback shows exactly `远程模型结果未采用，本次使用安全规则结果。`; invalid engine metadata shows exactly `分析引擎信息未确认，请人工核查本次结果。`.
- Loading shows exactly `正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。`.
- Confirm the persistent disclosure before Analyze is exactly: `After you click Analyze, configured remote AI providers may receive locally deidentified current visible email text and selected current-message images or files after local screening. Media pixels or document content may contain identifying information and are not guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention guarantee is made.`

### Current-message attachment acquisition release gate

- Recreated legacy-control fixtures must prove one same-origin, redirect-failing, current-message-only in-memory fetch after Analyze and zero fetches for missing target, wrong path/origin, body/signature ownership, unsupported metadata, redirect, or stale context.
- Manual-picker fixtures must prove selection/change performs zero reads, Analyze performs one bounded read, stale revalidation makes zero backend calls, and every exit clears the input and releases arrays.
- Both routes must preserve 5 files, 10 MiB per file, and 25 MiB total; the manifest permissions remain exactly `activeTab` and `sidePanel`.
- Static guards must reject `chrome.downloads`, `showOpenFilePicker`, File System Access handles, `localStorage`, `sessionStorage`, `IndexedDB`, `chrome.storage`, and local path fields.
- Backend tests must prove request `finally` deletes request-local files on success and provider failure. The 24-hour mtime cleanup is crash recovery only; it is not normal retention and is not scheduled.
- Only `attachment_insights[].status == "parsed"` proves content parsing. Array length, metadata, acquisition, `metadata_only`, `unavailable`, and `failed` do not.
- The bounded smoke proved acquisition, parsing status, routing, and cleanup only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. No follow-up operation may navigate, scan, send, or output message content without fresh authorization; all providers remain disabled by default.

## 安全检查

- 前端没有 API key。
- `.env` 未被提交。
- 日志不包含真实邮件和密钥。
- 回复草稿不会自动发送。
- 用户未点击按钮时不会触发分析。
- Cleanup Agent 不自动删除文件、不修改 Prompt、不放宽约束。
- 生命周期清理只在请求处理和本地服务 start/restart 路径运行，不存在后台邮箱轮询器或常驻调度器。

## 质量要求

- 新增业务代码必须配套测试。
- 涉及 AI 输出解析和邮件清洗的逻辑必须覆盖异常输入。
- 非小型任务完成后，必须更新项目状态日志，再运行完整测试和维护扫描。
- 修改邮件分类、优先级、风险点或建议动作规则时，必须运行 `tests/test_golden_email_analysis.py`。

## Repeatable phase-two release checklist

在项目根目录按顺序运行：

```powershell
python scripts/generate_project_status.py --output docs/operations/project_status_log.md
python -m unittest discover -s tests
python -B scripts/maintenance_scan.py
node --check frontend/browser_extension/content/current_message_collector.js
node --check frontend/browser_extension/content/exmail_adapter.js
node --check frontend/browser_extension/shared/api_client.js
node --check frontend/browser_extension/shared/render_analysis.js
node --check frontend/browser_extension/popup.js
node --check frontend/browser_extension/background.js
node --check frontend/local_debug_page/app.js
python -c "import json, pathlib; json.loads(pathlib.Path('frontend/browser_extension/manifest.json').read_text(encoding='utf-8')); print('manifest json: OK')"
python -m unittest tests.test_browser_extension_manifest tests.test_architecture_constraints tests.test_static_linter_constraints
git diff --cached --check
git diff --cached --name-status
```

通过条件：完整 Python suite 无失败；maintenance scan 无 findings；全部 Node 和 manifest 检查退出 0；文档/front-matter guards 通过；staged snapshot 只包含本次生命周期、文档、状态和计划收尾范围，且不包含 `.env`、数据库、日志、真实邮件、密钥或 token。

## Validation status

- 自动化单元测试、约束检查、JavaScript 语法检查和合成附件/线程样例属于本仓库内可执行验证。
- 真实 Tencent Exmail 邮件 smoke test **未在本任务执行**。它仍是用户在单独授权、确认最小范围并准备测试邮件后的外部验证项；不得把自动化或合成结果描述为真实邮箱验证。

## Authorized private-analysis offline closeout

以下步骤分为“自动离线发布门”和“后续管理员现场操作”。自动测试只执行
第一部分；不得为了验证本仓库而连接真实邮箱、打开外置 vault、读取私有
`.pkeval`、调用 DeepSeek、探测 DPAPI/BitLocker 或输入真实密钥。

### Automated offline release gate

在项目根目录设置 `EMAIL_AGENT_LLM_PROVIDER=disabled` 后执行：

```powershell
python -B -m unittest tests.test_repository_leakage_scan tests.test_rollout_closeout_contracts tests.test_maintenance_scan tests.test_generate_project_status
python -B scripts/evaluate_deepseek_analysis.py
python -B -m unittest discover -s tests
python -B scripts/generate_project_status.py --output docs/operations/project_status_log.md
python -B scripts/maintenance_scan.py --fail-on-high
git diff --check
```

`scripts/maintenance_scan.py` 集成只读 `repository_leakage_scan`。其泄漏结果
只允许固定 code、粗粒度 scope 和 count；不得回显 matched text、真实标识、
密钥或具体文件路径，也不得自动删除或改写文件。范围只限 Git tracked 文件及
仓库内明确的日志、测试输出、公开 SQLite fixture 和生成状态日志；不得打开
项目外 vault 或私有 `.pkeval`。

### Separately authorized administrator runbook

以下命令只是现场顺序合同，不属于自动验证，也不能被定时任务调用。每次真实
操作前都需要本地书面授权、单一账号、外置 NTFS + BitLocker To Go 证据及独立
恢复介质：

邮箱扫描、私有评估和生产 DeepSeek API 启用需要 separate operator confirmations；
no credentials are supplied to Codex，且浏览器、正常后端和自动化流程保持 no
automatic mailbox scan。所有管理员入口只使用下列 `python -B -m ...` 模块命令。

1. `python -B -m scripts.manage_mailbox_vault init --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account --recovery-key $RecoveryKey`
   初始化外置分析快照与分离的恢复封装。
2. `python -B -m scripts.manage_mailbox_vault inventory --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account` 只生成 content-free
   清单和 fingerprint。
3. **STOP after inventory.** 人工核对 content-free 结果并另行确认相同 fingerprint
   后，才可运行 `python -B -m scripts.manage_mailbox_vault scan --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account
   --confirm-inventory-fingerprint $Fingerprint --sales-policy $SalesPolicy`
   读取固定 24 个月窗口的正文。`$SalesPolicy` 必须是完整 Project Container
   protected root、OneDrive、系统临时目录和 raw vault 之外、经本地负责人维护的
   绝对路径；其值不会进入公开输出。
4. `scan` 完成后立即运行第一次
   `python -B -m scripts.manage_mailbox_vault verify --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account`。只有完整性失败数为零，
   才能进入附件审批。
5. attachment approval 必须由业务与隐私双审清单明确选中，随后才可运行
   `python -B -m scripts.manage_mailbox_vault attachments --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account --manifest $AttachmentManifest`；
   总数不得超过 `50`，并继续执行 10 MiB 单文件和 25 MiB 单会话上限。
6. `attachments` 完成后再次运行
   `python -B -m scripts.manage_mailbox_vault verify --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account`。第二次完整性失败数也必须
   为零，否则立即 incident stop。
7. 只有另行审核的 `StageEvaluationSelectionV1` 已严格绑定 exactly 200 条、
   authorization `scope_fingerprint` 与双审清单 `inventory_fingerprint` 分别通过，
   且本地 staging/evaluation key 已准备由 hidden getpass 输入时，才可运行
   `python -B -m scripts.manage_mailbox_vault stage-evaluation --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account
   --selection-manifest $EvaluationSelection
   --staging-dataset $EvaluationStage`。`$EvaluationStage` 必须是完整 Project
   Container protected root、OneDrive、temp、raw vault 和其他 private store
   之外的 `.pkevalstage`；命令请求 no mailbox
   app password。测试必须证明 handoff 使用 evaluation-only source、在 plaintext
   释放前拒绝 inventory mismatch、保持 no evidence accumulation，并在下一条前释放
   raw-derived identifiers；成功只输出 `evaluation_stage_complete` 和 200/0 counts。
8. 按授权使用
   `python -B -m scripts.manage_mailbox_vault purge-expired --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account`、
   `python -B -m scripts.manage_mailbox_vault revoke --vault $VaultRoot
   --authorization-id $AuthorizationId --account $Account --confirm $RevokeConfirmation`
   或 crash-recoverable `python -B -m scripts.manage_mailbox_vault rewrap-recovery
   --vault $VaultRoot --authorization-id $AuthorizationId --account $Account
   --current-recovery-key $RecoveryKey --new-recovery-key $NewRecoveryKey
   --confirm $RewrapConfirmation`。
9. `python -B -m scripts.manage_private_knowledge import-candidate
   --authority-root $AuthorityRoot --authority-id $AuthorityId --batch-root $BatchRoot
   --batch-id $BatchId --candidate-id $CandidateId` 后按顺序完成业务、隐私及必要的
   责任人审批，再运行 `python -B -m scripts.manage_private_knowledge approve
   --authority-root $AuthorityRoot --authority-id $AuthorityId --card-id $CardId` 和
   `python -B -m scripts.manage_private_knowledge publish --authority-root $AuthorityRoot
   --authority-id $AuthorityId --snapshot $Snapshot --snapshot-id $SnapshotId`。拒绝、
   过期、deprecate 或 revoke 后重新发布；签名/密钥/文件无效时正常服务必须退回
   generic rule fallback。
10. 在 stage 完成后，以 same operator-supplied 32-byte hidden key 运行
   `python -B -m scripts.evaluate_private_deepseek build --staging $EvaluationStage
   --dataset $Dataset`。stage 与 final 必须位于独立外部目录；final 使用 fresh UUIDv4
   namespace 和 distinct final magic/purpose/nonce，create-only 且不自动删除 stage。
   Build revalidates exactly 200/full strata/current dual approval/at least 40 Pro，
   并创建 zero provider/judge/network/transcript。
11. `python -B -m scripts.evaluate_private_deepseek verify --dataset $Dataset` 只做本地
   预检。真实 `python -B -m scripts.evaluate_private_deepseek run --dataset $Dataset
   --report $AggregateReport --confirm-private-evaluation I_CONFIRM_200_FLASH_40_PRO
   --interactive-judge` 还要求 stdin/stdout 均为 real local TTY；缺少该 flag 时固定
   `human_judge_unavailable`。TTY 后必须先完成 fixed exact-y readiness；EOF/cancel/
   invalid readiness 在 key/client 前固定失败。adapter 只接收
   `UsefulnessJudgeView`、拒绝 ESC/C0/C1/bidi/format controls、每 case 一次 exact y/n；
   invalid/EOF/terminal failure 在下一次
   provider call 前固定为 `human_judge_failed`。程序 no transcript，但不能阻止外部
   terminal capture。只有 aggregate-only report 持久化；仍是 20 Flash + 180 Flash /
   40 Pro、zero retry 和 no automatic production model switch。

任一步出现授权范围变化、UIDVALIDITY/fingerprint 变化、flags 变化、残留身份、
vault/签名/密钥错误、schema/safety/grounding 违规、p95 超限、泄漏 finding 或
不可解释的计数时，立即 incident stop；保持 provider disabled，保全内容无关
错误码和计数，并由本地负责人决定恢复或撤销。


## Issue #91 production composition closure

1. Run `tests/test_r2_production_composition_reachability.py` and confirm all
   three executable roots import only their V2 entry.
2. Confirm the obsolete V1 lock and every test binder are unreachable from the
   production import graph.
3. Confirm default fixed verbs return content-free no-issuer dormancy and that
   the existing #88-#90 positive/negative tests still prove one authorized
   composition acquisition and zero unauthorized acquisitions.
