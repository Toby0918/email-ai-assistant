---
last_update: 2026-07-26
status: draft
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0009: Project container and repository boundaries

## Status

Accepted as a design on 2026-07-23. The Issue #30 compatibility seam, Issue #31
Standalone Verification route, Issue #32 Managed launcher, Issue #33 protected
private-store policy, Issue #34 pure manual audit contract, Issue #35 offline
migration-evidence package, Issue #36 temporary synthetic reparenting
rehearsal, Issue #37 synthetic Managed runtime activation rehearsal, and Issue
#51 locked Cutover Profile/authorization/receipt contracts are implemented. No
real evidence package, audit, host adapter, Project Container directory
migration, or operational cutover has occurred. While this ADR remains draft,
the current flat paths and the active security contracts in ADR 0006 through
ADR 0008 remain authoritative.

### Issue #30 compatibility seam

`backend.project_layout` now provides the pure `RepositoryPlacement` and
`OperationalLayout` interfaces. Managed placement requires the exact canonical
`email_ai_assistant\main` relationship. Standalone Verification Mode requires an
explicit separate synthetic or temporary state root. Both modes validate stable
non-reparse identity and expose a complete immutable protected-root tuple.

The layout value contains only the seven ordinary absolute locations. A separate
flat-layout transition adapter preserves current `.venv`, `outputs`, attachment
temporary, and `.worktrees` mappings without becoming a third placement mode.
This checkpoint creates or migrates no directory, routes no service, expands no
private-storage policy, performs no container audit, and does not implement Issue
#31 through #40.

### Issue #33 protected private stores

`ProtectedLocationPolicy` is a read-only standard-library value derived only from
freshly revalidated `RepositoryPlacement` evidence or the bounded flat-layout
compatibility path. Managed mode retains `(project_container,)` as its complete
protected-root tuple; that single root covers the container, `main`, all eight
sibling zones, and every descendant. A repository detected inside a Managed zone
but not at the exact `main` relationship fails closed instead of being treated as
an unrelated flat checkout.

The same policy accepts a freshly revalidated explicit Standalone
`RepositoryPlacement` and preserves both its Repository Root and separate state
root. This is a non-public validation context only; it does not enable mailbox,
private-knowledge, private-evaluation, raw-vault, or provider capability in
Standalone Verification Mode.

Private-knowledge authority/candidate/snapshot paths, private-evaluation stage
and final datasets, new and existing mailbox vaults, current and new recovery
locations, and the strict external sales-policy file now consume this policy
internally. Candidate policies check original and resolved views and preserve
their existing reparse, identity, store-separation, encryption, volume-evidence,
and fixed-error contracts. Public requests remove `protected_roots` and
`project_container`; no environment, config, frontend, normal-runtime, or CLI
surface may supply or narrow the protected roots. This checkpoint performs no
directory migration, container audit, ACL change, or real private-store access.

### Issue #32 Managed local service

`backend.email_agent.managed_runtime` derives the Project Container only from a
Repository Root already validated as the exact `email_ai_assistant\main` child.
Both lifecycle and direct launchers expose only `--managed-container`; no
arbitrary container, protected root, or operational path is accepted. Before
service startup, the adapter validates every pre-existing ordinary zone, the
Managed runtime executable, writable targets, and an optional descriptor-bound
`Config/settings.env`.

Config accepts exactly `EMAIL_AGENT_LOG_LEVEL` and
`EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS`. The injected `AppConfig` has remote/local
providers and private knowledge disabled and contains absolute `LocalData`
SQLite and `RuntimeTemp` attachment paths. Logs and PID use `Logs`; runtime,
artifact, worktree, and Config paths remain in their approved zones. Process cwd,
source/frontend discovery, Git, project status, maintenance, and leakage scans
remain rooted at `main`.

The complete lifecycle is verified only against a synthetic layout and
loopback server. This checkpoint does not create the real container, rebuild or
move a runtime, copy a database/artifact, relocate a worktree, perform an audit
or ACL change, read credentials, contact a mailbox/provider/private store, or
start Issues #34–#40.

### Issue #34 manual content-free audit

`backend.container_audit` now provides one keyword-only
`run_container_audit(policy=..., adapters=...)` function. The policy carries
only independent opaque expected identities/fingerprints, the approved
worktree roster, clean-state requirement, and SQLite phase. Code fixes all
names, versions, bounds, roles, relationship rules, public statuses, and counts.
Seven injected callbacks provide strict frozen repr-redacted filesystem, ACL,
volume, Git, worktree, runtime, and SQLite metadata; there is no path or reader
capability in the contract.

The audit validates two complete equal snapshots and fails closed on malformed,
unknown, incomplete, unreadable, aliased, reparse-bearing, mismatched, or
drifting evidence. Adapter and validator exceptions are neither logged nor
formatted. Public results contain only `container_audit_passed` or
`container_audit_failed` plus one accepted/rejected aggregate result.

This checkpoint adds no CLI, default or real adapter, composition root, runtime
consumer, cleanup/leakage integration, browser route, workflow, scheduler,
repair, mutation, mailbox/provider/vault/private-store access, or host probe.
Its reviewed consumers are Issue #36's synthetic audit bridge and Issue #53's
exact read-only audit bridge. The latter binds seven caller-owned callbacks
without changing the nine-zone policy, validation order, or pass/fail semantics.
Automated verification remains synthetic or confined to a test-owned temporary
sandbox; no real preflight or post-cutover audit was executed.

### Issue #35 no-clobber migration evidence package

`backend.migration_evidence` provides three explicit manual Python seams:
`prepare_migration_evidence_review`, `create_migration_evidence_package`, and
`verify_migration_evidence_package`. Preparation discovers current Git status,
local `refs/heads/*`, selected attached worktrees, branch/HEAD/upstream and
ahead/behind state without contacting a remote. Remote configuration is
local-only and hashed; Git subprocesses receive a sanitized environment with
global/system config and fsmonitor disabled. Windows subprocesses cannot run
until their prepared kill-on-close Job Object assignment succeeds; POSIX
process groups are closed while the unreaped leader still reserves group
identity.

The package is one external create-only ZIP. Its canonical manifest identity
binds the exact review fingerprint, independently verified Git bundle, complete
content-free selection and Git/ACL/volume evidence, snapshot index, and every
payload SHA-256. Approved dirty tracked files preserve separate index and
worktree bytes; staged/unstaged deletion is explicit and rename recovery does
not rely on rename heuristics. Only exact approved source/tests/docs may be
opened. Credentials, signing material, SQLite and sidecars, logs/PID,
environments, IDE/cache/private data, and outputs are mechanically vetoed.

Existing targets, repository-internal targets, reparse ancestors, unsupported
Git/index types, hidden index flags, source drift, publication races, partial
writes, or semantic verification drift fail closed. Create and verify receipts
contain fixed status and aggregate counts only. The module has no CLI, default
target, runtime/browser/workflow consumer, network/mailbox/provider/vault/
private-store capability, service lifecycle action, repository relocation, ACL
mutation, or cleanup behavior.

Issue #36's exact evidence bridge may call the review/create/verify seams only
inside its self-created temporary repository. Issue #53's exact baseline bridge
may import only the content-free `HostBaseline` value and cannot call those
seams.

Issue #35 tests use only temporary synthetic repositories and destinations and
prove independent refs/objects, dirty index/worktree state, and linked-worktree
branch/HEAD recovery. No real checkout package was created. A future real
capture must first expose the exact external target, content-free
inclusion/exclusion manifest, reviewed refs, and worktree selection, then stop
for fresh operator confirmation. Issues #37 through #40 remain separate.

### Issue #36 synthetic reparenting rehearsal

`backend.reparenting_rehearsal` exposes one content-free Python seam with no
filesystem path input. It creates a unique marker-bound temporary sandbox and a
non-trivial synthetic repository topology, then captures branch, HEAD, all local
refs, local-only remote fingerprint, ahead/behind, index/status, approved file
hashes, linked-worktree state and Git common-directory identity.
The marker's filesystem identity is captured with a fixed sibling hard-link
identity anchor and both paths are rechecked before publication. Holding the
original inode through the anchor means same-content replacement cannot pass by
inode reuse; alias/reparse drift and non-local remote state also fail closed.

Before rename, the rehearsal uses the exact Issue #35 public contract to create
and independently verify one synthetic evidence package outside every worktree.
It renames the complete synthetic source to a sibling legacy source, publishes
the clean nine-zone Container at the canonical replacement name, and moves the
existing `.git`, tracked source and reviewed untracked source to `main` by
checked no-clobber rename. Ignored credential, signing, runtime, output,
IDE/cache, SQLite, log and private canaries remain in the legacy source and are
never source-reader inputs.

Each of two fixed linked worktrees receives one injected reviewed `repair` or
`recreate` choice. Repair preserves the moved directory identity and repairs
both Git pointers. Recreate preserves the old physical worktree and
administrative record before adding a clean worktree from the same common
directory; neither route clones, prunes, deletes or overwrites. Post-verification
requires the original Git/source baseline, exact Managed relationship, clean
linked status, common identity and an actual pass through the synthetic
ContainerAudit. Main/worktree/audit failure injections move the complete
Container by no-clobber rename to the one sibling rollback path, repair only the
reviewed relocated linked paths, and repeat independent evidence and topology
checks. The public operation leaves all synthetic topology intact; only the
test's caller-owned parent is removed after assertions.

Failure injection follows the six fixed publication boundaries: verified
evidence, legacy rename, Container publication, main publication, worktree
publication and ContainerAudit. Every injected failure proves either the
original source or legacy/container/main plus the independently verified
evidence package before the test-owned temporary directory is disposed. The
module has no CLI, default/real adapter, normal-runtime/browser/script/workflow
consumer, ACL/runtime/database action, mailbox/provider/vault/private-store
access or authority for real cutover.

### Issue #37 synthetic Managed runtime activation rehearsal

`backend.runtime_activation_rehearsal` exposes one keyword-only Python seam
whose only argument is an exact five-field injected adapter bundle. The module
accepts no path, repository, source, destination, environment, reader factory,
failure selector, CLI input, or default host adapter. Its fixed public result
contains only completed/failed status and aggregate counts.

The rehearsal validates a complete synthetic Managed layout, exact Python
3.12.13 and SQLite 3.50.4 evidence, stable dependency-lock identity and digest,
offline Windows venv rebuild evidence, and an untouched legacy venv. Lifecycle
stop output and an independent stopped probe must echo `pre_publication` before
the database adapter can run. SQLite publication is create-only and requires
distinct stable identities, equal pre-activation SHA-256/size/counts, successful
integrity/schema checks, and no WAL/SHM/journal sidecar. The source is observed
again after publication and after service activation.

A reviewed synthetic browser-extension identity and SHA-256 must match the
source before create-only artifact publication; filesystem and probe destination
observations must agree. No signing-material capability exists. The synthetic
service start binds the rebuilt venv executable plus attachment temp, log, PID
and non-secret Config resources to their approved Managed zones, fixes both
providers disabled, and binds one fresh activation nonce to the initial gate；
that nonce is echoed through literal-loopback health and one user-confirmed
persisted `rule_fallback` analysis. The
`post_activation` final proof binds that token and the same service, rejects
stale evidence, uses a fresh stop token, and precedes post-analysis checks.

Tests own all mutable state beneath `issue37-synthetic-*` temporary parents and
independently inspect source, legacy and competitor preservation before teardown.
Race, reparse, existing-target, dependency, integrity and health failures return
the same fixed failure and never authorize overwrite or source cleanup. The
production package imports no filesystem, SQLite, subprocess, network, mailbox,
provider, vault, private-store, credential, ContainerAudit or migration-evidence
capability and has no host consumer. No real runtime, database, extension
artifact, evidence package or Project Container activation occurred.

### Issue #51 locked cutover contracts

`backend.cutover_contracts` is a pure, cross-platform, content-free contract
layer. `CutoverProfileV1` is immutable and closed-schema. It binds the governing
master commit; operator, fixed-role, evidence-role and reviewed-Git
fingerprints; exactly eleven worktree roles with eight embedded and three
external placements; pinned Runtime inputs; create-only SQLite and reviewed CRX
inputs; deterministic non-secret provider-disabled Config; fixed-role ACL
policy; two-observation/fresh-gate/no-cleanup maintenance rules; and complete
rollback roles. It accepts no arbitrary host path, drive, directory, SID, SDDL,
Git name/ref, command, exception, database content or free-form message.

Real-host authorization contracts are physically distinct nominal types:
`RealPreflightAuthorizationV1`,
`EvidencePublicationAuthorizationV1`,
`CutoverExecutionAuthorizationV1`, and `RecoveryAuthorizationV1`. Each external
canonical value is bound to one fixed operation, an allowlisted phase, the
profile, governing master, operator, operation fingerprint and bounded validity.
The package contains no issue or mint seam, secret, signing, time or random
source for real authorization. Exact-type validation returns fixed allowlisted
statuses for missing, invalid, not-yet-valid, expired and binding mismatches;
receipts, mappings, duck types and in-memory `TestSandboxAuthorizationV1` values
cannot pass as real-host authorization.

`ReceiptEnvelopeV1` is deterministic canonical JSON with a verified SHA-256
fingerprint. Twelve closed receipt types cover preflight, evidence, ACL,
repository, worktree, Runtime, database, artifact, Config, activation, rollback
and incident stop. The envelope binds type/status, operation, profile, master,
authorization, producer, subject role, input and observation fingerprints,
allowlisted counts, validity and closed per-type details. Duplicate keys,
unknown fields or values, non-canonical bytes, raw paths, SID/SDDL, Git names,
commands, exceptions, database content and free-form messages fail closed.
Receipts remain evidence only and cannot authorize execution.

`default_operator_entry()` accepts no argument and always returns
`BLOCKED_NO_APPROVED_COMMAND` with one blocked and zero executed operations.
This slice adds no host adapter, composition root, CLI, production consumer or
authority to execute preflight, evidence publication, ACL, repository/worktree,
Runtime, SQLite, CRX, Config, activation, rollback or incident operations.
Its approved consumers are the exact Issue #52 journal contracts bridge and
Issue #53 real-host-preflight contracts bridge.

### Issue #52 crash-safe journal and recovery classification

`backend.cutover_journal` is a pathless synthetic-only state proof. One
`JournalOperationBindingV1` revalidates and pre-binds the exact Issue #51
Profile, execute authorization, recovery authorization, governing master,
operation, and exclusive opaque owner before the first record. It does not mint
or broaden authority.

`JournalRecordV1` is strict canonical UTF-8 JSON with exact sequence,
previous-record hash, record hash, fixed synthetic step/direction/event,
operation/profile/authorization/owner bindings, opaque before/expected/observed
fingerprints, and fixed outcome. Each forward and reverse action follows durable
`INTENT`, exact `EFFECT_OBSERVED`, and `COMMITTED`. Reverse intent is derived
only from verified `COMMITTED/APPLIED` forward history in LIFO order and swaps
the forward before/after observations.

The exact in-memory durability medium records pending-file, no-replace final,
published-file, namespace, and stable-reread barriers under closed Windows and
Linux trace codes. Only a fully namespace-barriered intent may precede a
synthetic effect. Pending, truncated, corrupt, or unbarriered state never grants
an action permit. Each owner claim uses a new in-memory lease; a synthetic
effect must consume a non-copyable/non-serializable store permit backed by one
shared single-use issuance for that lease, the exact round-trip-validated
active durable intent, and current durable/stable journal head. One synthetic
medium operation gate serializes append, restart, permit mint/atomic claim, and
effect mutation. A namespace-published current head missing stable reread is
exactly re-read and the full snapshot reverified before any successor append or
permit. Any head advance, pending record, or durable observed fact invalidates
an older permit. This contract proof is not real NTFS/Linux/power-loss evidence
and exposes no filesystem adapter.

Restart inspection accepts immutable snapshots and cannot claim ownership,
append, resume, rollback, start a service, or change even synthetic effect state.
Explicit resume requires fresh exact phase-`resume` authorization and exact
pre-action or expected-post observation; expected-post only completes journal
facts. Durable observed facts remain authoritative across renewed
`RESUME_BOUND` records. Pending direction, Profile/master/operator binding,
identity mapping, fixed transition mapping, and the exact post-effect
observation fail closed. Explicit rollback uses the exact pre-bound, freshly valid
`RecoveryAuthorizationV1`, reconciles exact partial facts, and invokes only
journal-derived reverse steps. Unknown observation, identity drift, corrupt
chain, or unsafe authority becomes `INCIDENT_STOP`.

Public inspection output is limited to fixed status, phase, receipt fingerprint,
and allowlisted counts. `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and
`CUTOVER_SUCCEEDED` are distinct. The package has no path, callback, default
adapter, CLI, HTTP route, real filesystem/service/ACL/Git/worktree/Runtime/
SQLite/provider/mailbox/vault/private-data capability, or production consumer.
No real operation was executed.

### Issue #53 content-free Windows real-host preflight

`backend.real_host_preflight` is an internal read-only composition boundary.
Windows object observations use opened handles and bind volume identity,
128-bit file ID, object type, parent identity, normalized-name fingerprint, and
reparse metadata. Every controlled component is opened without following
reparse points; aliases, unexpected volume/filesystem state, unreadable
objects, replacement, and identity drift fail closed.

`CurrentTopologyPreflight` accepts only two complete identical observations.
`PreMutationGate` is short-lived, nonce-bound, one-operation, single-use, and
repeats exact source, target-parent, target-absence, reparse, Git, ACL, and
volume checks. `RealHostBaselineCollector` keeps source-root, parent, finance,
volume, operator-SID, and ACL evidence separate while projecting only the
canonical content-free `HostBaseline` value.

The exact audit bridge binds seven caller-owned read-only callbacks to the
unchanged nine-zone `ContainerAudit`.
`FinalAuditCompositionReadyReceiptV1` proves only that this composition is
available; it never claims that a pre-cutover final layout passed. The native
Windows observer is exercised only beneath a test-owned temporary sandbox, and
Linux tests validate portable contracts without claiming NTFS, Windows file-ID,
or Windows ACL evidence.

The zero-argument operator entry remains
`BLOCKED_NO_APPROVED_COMMAND` and rejects test authorization. The package owns no
service-control, ACL-apply, rename, worktree-mutation, Runtime-build,
database-copy, artifact, Config, provider, mailbox, vault, or private-data
capability. No real host target was accessed or changed. Issues #54 through #59
remain separate; Issues #38/#39 and parent Spec #50 are unchanged.

## Context

The local checkout currently mixes the complete Git repository with a venv,
runtime outputs, local configuration, linked worktrees, build artifacts, and
path references to separately managed data. Related top-level directories also
make `D:\Projects` appear to contain more than the two intended projects.

Keeping everything in one Git root is simple but increases accidental publication
risk. Moving every private asset under a parent directory is visually tidy but
does not create access control, encryption, identity separation, or recovery
separation. Re-cloning into a new layout would also endanger uncommitted work,
local refs, and linked-worktree metadata.

## Decision

`D:\Projects\email_ai_assistant` will become the Project Container.
`D:\Projects\email_ai_assistant\main` will become the sole Repository Root and
Git common directory, and the only normal human Codex and IDE workspace.
Explicitly assigned linked worktrees under `Worktrees` are the sole planned
automation exception.

The first-stage container layout is:

```text
D:\Projects\email_ai_assistant\
├── main\
├── Runtimes\
├── LocalData\
├── RuntimeTemp\
├── Logs\
├── Artifacts\
├── Worktrees\
├── Config\
└── OperatorPrivate\
```

`main` owns the complete existing Git identity, tracked project files, approved
untracked source and test files, and project-local Codex policy. The repository
will be re-parented with its existing `.git`; a fresh clone will not replace it.
Dirty paths, refs, remote configuration, linked worktrees, and allowlisted
rollback evidence must be independently verified.

All sibling directories sit outside the Repository Root, but they do not form
one undifferentiated non-versioned zone. `Runtimes`, `LocalData`, `RuntimeTemp`,
`Logs`, `Artifacts`, and `Config` form the Local Operational Zone. `Worktrees`
is the Automation Worktree Zone and contains versioned linked checkouts whose
Git common directory remains `main\.git`. `OperatorPrivate` is the separately
controlled Operator Private Zone. `Config` accepts only non-secret settings.

`OperatorPrivate` is inactive by default. It may be enabled only after explicit
ACLs, a separate operator identity, encryption evidence, indexing and sync
exclusions, path-policy updates, and guard tests are in place. The sole planned
early use is an ACL-restricted holding area for the existing ignored `.env` and
browser-extension signing PEM; no runtime may read that holding area.

Raw mailbox vault and recovery material remain in the External Vault Zone.
The vault still requires an independent removable NTFS BitLocker To Go volume,
and recovery material still requires a different offline volume. No such media
is currently provisioned, so raw-vault capability remains disabled.

Managed Container Mode routes local runtime state to approved sibling
directories. Standalone Verification Mode preserves portable clone and CI
behavior but permits only synthetic data, temporary state, and disabled
providers.

The removed Codex `weekly-cleanup-agent` will not be restored or rebound. The
repository still contains a separate scheduled GitHub Actions cleanup workflow;
this ADR does not remove or disable it, and a separately approved change must
decide its disposition. A future weekly code-review automation must be a separate
design that works only in an assigned `codex/weekly-review-*` branch and linked
worktree, never traverses the parent container or sibling zones, never mutates a
dirty main worktree, and never automatically pushes, creates a PR, merges, or
deletes a branch. Any proposed edit must pass the required tests and wait for
operator review and manual integration.

## Considered options

### Keep the flat repository

Rejected because runtime, configuration, local data, worktree, and artifact
ownership remain ambiguous and the parent project list remains cluttered.

### Put all data and secrets beside `main`

Rejected as a complete solution because directory placement is not a security
boundary. Raw vault, recovery material, interactive secrets, and decrypted
private content retain stronger physical, identity, and lifecycle constraints.

### Re-clone the repository into `main`

Rejected because a clone does not preserve the current dirty working tree,
ignored local state, reflog-equivalent local history, and linked-worktree
identity without additional error-prone reconstruction.

## Consequences

- The migration is a security and repository-boundary change, not a file cleanup.
- Current code that infers a project root from `__file__`, current working
  directory, or repository-relative `outputs` requires explicit review and tests.
- Human Codex and IDE sessions must be reopened at `main`; an approved automation
  may open only its assigned linked worktree and may not open the Project
  Container.
- Parent ACLs must be tightened without changing `D:\Projects` or the finance
  project.
- Repository leakage scanning remains scoped to `main`; a separate content-free
  container audit must cover metadata and ACL drift without reading private
  content. It is a mandatory manual gate before migration, after migration, and
  during maintenance, never an automation or background task. Drift or unreadable
  state fails closed with fixed codes; public output contains only a fixed status
  and aggregate counts, without sensitive path details.
- The migration waits for a stable reviewed Git checkpoint and a separately
  approved implementation Issue.
- Old directories, venvs, databases, credentials, and artifacts remain available
  until verification succeeds and the operator separately approves recoverable
  cleanup.

## Supersession boundary

This draft ADR does not currently supersede ADR 0006, ADR 0007, or ADR 0008.
Issue #33 redefines only project-external location checks to consume the complete
Project Container protected-root contract. It does not weaken raw-vault volume
requirements, recovery separation, provider-disabled defaults, mailbox
isolation, or private-data handling.
