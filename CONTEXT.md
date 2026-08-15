# Email AI Assistant

This context separates the versioned product repository from local operational
resources and from independently protected private data.

## Language

**Project Container**:
The local umbrella for one project's repository, linked worktrees, operational
resources, and separately controlled operator-private area. It is an
organizational boundary, not an automatic confidentiality boundary.
_Avoid_: Project root, safe folder

**Repository Root**:
The single version-controlled development surface that owns the complete Git
identity and common directory, source, tests, documentation, and project-local
tooling policy. It is the normal human Codex and IDE workspace; explicitly
assigned linked worktrees are the only planned automation exception.
_Avoid_: Core-code folder, public folder

**Local Operational Zone**:
Non-versioned, locally managed runtime, ordinary analysis data, temporary state,
logs, and artifacts that support the product without becoming repository content.
_Avoid_: Repository data, private vault

**Automation Worktree Zone**:
Linked Git working trees under the Project Container. Each checkout remains bound
to the Repository Root's Git common directory and may expose only its assigned
working tree to an approved automation.
_Avoid_: Local Operational Zone, standalone repository

**Operator Private Zone**:
An inactive-by-default confidential area whose contents require a separate
operator identity, explicit ACLs, encryption evidence, and fail-closed access.
_Avoid_: Hidden folder, ignored secrets folder

**External Vault Zone**:
Physically separate encrypted storage for raw mailbox material, paired with
recovery material on a different security domain. Project-external policy treats
the complete Project Container, every named zone, and every descendant as
protected; being outside the Repository Root alone is never sufficient.
_Avoid_: LocalData, Operator Private Zone

**Managed Container Mode**:
The operator-controlled local mode that routes normal runtime state to approved
container locations while keeping credentials and private stores outside the
repository.
_Avoid_: Production mode, local default

**Standalone Verification Mode**:
A portable repository-only mode limited to synthetic data, temporary state, and
disabled providers for CI and offline development checks.
_Avoid_: Managed mode, live mode

**Flat Layout Transition Adapter**:
A temporary compatibility mapping for the current repository-local `.venv`,
`outputs`, and `.worktrees` locations. It is not a third placement mode and must
not survive the completed cutover.
_Avoid_: Legacy mode, standalone mode

**Container Audit**:
A manual, read-only, content-free, fail-closed comparison of an independent
trusted policy with injected filesystem, ACL, volume, Git, worktree, runtime,
and SQLite metadata. It returns only a fixed overall status and aggregate
counts; it is separate from repository leakage and maintenance scanning and
does not repair or probe a host by itself.
_Avoid_: Repository scan, cleanup scan, migration repair

**Migration Evidence Package**:
A single create-only external archive that binds reviewed local Git refs and
objects, approved dirty index/worktree source layers, selected worktree
identity, and content-free host baselines with one canonical SHA-256 manifest.
It is prepared and verified offline before cutover; it is not a repository
backup, runtime artifact, private-data container, or authorization to migrate.
_Avoid_: Build artifact, cleanup archive, live cutover package

**Reviewed Migration Evidence Workflow**:
The Issue #54 profile-bound sequence of content-free review, separately
authorized create-only publication, and separate-process read-only
verification. Review accepts only the exact `CutoverProfileV1` dirty-source,
local-ref, worktree, package-target, Git, and `RealHostBaseline` selections.
Create requires the exact `EvidencePublicationAuthorizationV1` and confirmed
review fingerprint, then repeats complete discovery and rejects any Profile,
selection, Git, host, target, or review drift. Its test-only synthetic binder
uses an independent marker hard-link in the target parent so inode reuse cannot
mask same-path replacement. The creator cannot call the
independent verifier, and the verifier cannot publish or modify the package.
Before Issue #39, real entries remain locked and reject missing, wrong-phase,
and test authorization; all executable proof stays in test-owned temporary
synthetic sandboxes with content-free output.
_Avoid_: Persisted review authority, combined creator-verifier, real package run

**Fixed-Role Host Mutation Primitive**:
The Issue #55 internal Windows capability set. ACL capture is role-bound;
parent and finance can only be captured and compared. The sole ACL update is a
direct DACL-only apply to one journal-proven newly created empty Container.
An atomic protected construction guard denies child insertion while
root/marker/parent/target handles remain held through the final DACL
linearization point, followed by exact eight-zone inheritance verification.
Create-only directory effects use parent-handle-relative `NtCreateFile`;
publication effects hold and revalidate opened source/parent handles, reject
reparse and cross-volume state, set no-replace, and prove the same 128-bit file
ID at the new role. Public values contain only fingerprints, fixed status, and counts.
The real constructor stays locked before Issue #39.
_Avoid_: Arbitrary path mutator, recursive ACL normalizer, ACL command transcript

**Migration Evidence Receipt Set**:
The content-free agreement among `MigrationEvidenceReviewReceiptV1`, the
create-only `MigrationEvidenceCreatedReceiptV1`, and the separate-process
verification receipt. All three bind the same operation, Profile, governing
master, review fingerprint, applicable package and manifest hashes, and
aggregate counts.
`MigrationEvidenceReceiptSetV1` is evidence for a later pre-mutation gate; it
does not authorize host preflight, migration, mutation, or cutover.
_Avoid_: Authorization token, package transcript, migration approval

**Reparenting Rehearsal**:
A self-contained temporary synthetic proof of the approved legacy-source
rename, existing Git common-directory move, reviewed linked-worktree recovery,
ContainerAudit, and rollback sequence. It accepts no repository path and grants
no authority to operate on a real workspace.
_Avoid_: Dry run on the real repository, migration command, cutover

**Managed Runtime Activation Rehearsal**:
A pathless, injected-adapter proof using only caller-owned temporary synthetic
sources and destinations. It validates create-only pinned runtime and SQLite
publication, reviewed browser-extension publication, exact Managed writable
roles, provider-disabled loopback health, one persisted rule-fallback analysis,
final service stop, and unchanged sources. It grants no real-host activation or
cutover authority.
_Avoid_: Runtime installer, migration command, real LocalData activation

**Cutover Profile**:
The immutable, pathless `CutoverProfileV1` contract that binds one governing
master commit to fixed role, evidence, reviewed Git, eleven-worktree, Runtime,
SQLite, CRX, Config, ACL, maintenance, and rollback selections using only
closed content-free values. It cannot be redirected with a command-time host
path or selection.
_Avoid_: Path configuration, command manifest, mutable runbook

**Cutover Authorization**:
One externally supplied nominal value of exactly
`RealPreflightAuthorizationV1`, `EvidencePublicationAuthorizationV1`,
`CutoverExecutionAuthorizationV1`, or `RecoveryAuthorizationV1`, bound to one
operation, phase, profile, master, operator, and bounded validity interval. The
pure contract layer validates but cannot issue or execute it; synthetic
authorization and receipts are never real-host authority.
_Avoid_: Receipt, test permission, build authorization

**Canonical Cutover Receipt**:
The deterministic, content-free `ReceiptEnvelopeV1` evidence envelope. Its
closed type/status schema and SHA-256 identity bind an observation to the
operation, profile, master, authorization, producer, subject, inputs, counts,
validity, and type-specific details without raw paths, identities, commands,
exceptions, database content, or free-form messages. It never authorizes a
later operation.
_Avoid_: Execution token, host log, command transcript

**Default-Locked Operator Entry**:
The pre-Issue-#39 no-argument seam that always returns
`BLOCKED_NO_APPROVED_COMMAND` with zero executions. It has no adapter,
composition root, command, or real-host capability.
_Avoid_: Cutover command, preflight launcher, migration CLI

**Crash-Safe Cutover Journal**:
The pathless Issue #52 synthetic state proof. Canonical create-only records bind
one operation and owner through durable `INTENT`, exact observed effect, and
`COMMITTED`; reverse records use the same model and are derived LIFO from
committed applied forward records. Pending or unbarriered records are never
action authority; a non-copyable/non-serializable store permit backed by one
shared single-use issuance binds each effect to the current owner lease, active
durable intent, exact durable journal head, and hash-bound stable reread; one
store-private atomic token claim selects the sole consumer, and one synthetic
medium operation gate serializes append/restart/mint/claim/effect. A
namespace-published current head must complete stable reread before any
successor append or permit. A head advance or durable observed fact invalidates
it. Durable observed facts, pending direction, exact
Profile/master/operator binding, and the fixed synthetic transition mapping are
authoritative. Restart inspection is read-only.
_Avoid_: Host journal, migration log, executable recovery command

**Recovery Classification**:
The content-free restart decision over one verified synthetic journal snapshot
and exact observation. `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and
`CUTOVER_SUCCEEDED` are distinct; `RESUME_ALLOWED` only identifies a separately
authorized explicit resume seam and is not itself a capability.
_Avoid_: Automatic recovery, guessed retry, host status probe

**Content-Free Windows Object Observation**:
The Issue #53 opened-handle identity value. It binds volume identity, 128-bit
file ID, object type, parent identity, normalized-name fingerprint, and reparse
metadata without exposing a raw path, SID, SDDL, Git name, or native exception.
The concrete Windows reader is package-private and confined to a test-owned
temporary sandbox through a root/marker identity-bound single-use permit;
controlled files require exactly one link. Every observer operation reopens
and validates the exact root and marker and holds those handle chains through
the target observation.
_Avoid_: Path-only identity, production host mutation

**Current Topology Preflight**:
The read-only Issue #53 proof that two complete observations of the current
source, target parent, absent target, Git, ACL, reparse, and volume state are
identical. Its content-free receipt records the observation; it does not approve
a mutation or claim that the final layout exists. Every callback value is
factory-reconstructed, and an independent canonical Profile snapshot is
captured before any host callback. Each source/parent/finance/target normalized
name is bound to that snapshot's exact role selection.
_Avoid_: One-pass probe, topology migration

**Pre-Mutation Gate**:
The short-lived, nonce-bound, one-operation, single-use Issue #53 recheck of the
exact preflight state immediately before a future separately authorized action.
Freshness or equality failure stops without granting any mutation capability.
The prior topology receipt is atomically claimed by at most one gate, and
trusted gate/receipt state is not caller-resettable. Every nominal receipt
class is also bound to its exact module-owned observation kind.
_Avoid_: Reusable token, mutation authorization

**Final Audit Composition Readiness**:
The proof that the unchanged nine-zone `ContainerAudit` policy can receive all
seven exact caller-bound read-only callbacks. It proves composition availability
only and is never a pre-cutover final-audit pass or cutover approval. Prepare
captures a detached canonical policy snapshot; run snapshots it again and
rebuilds adapters from the seven captured readers before any callback.
_Avoid_: Final layout pass, executable cutover command

**Project Container Composition Binding**:
The Issue #59 immutable, content-free agreement on one operation, Profile,
governing master, operator, and complete ordered authorization sequence. Every
operator role bundle and receipt chain must match it exactly.
_Avoid_: Runtime configuration, host target selection, authorization

**Real Host Preflight Composition Root**:
The physically separate Issue #59 root containing only fixed current-topology,
HostBaseline, evidence review/verification, final-audit readiness, and recovery
inspection roles. Its real constructor remains non-executable before Issue
#39.
_Avoid_: Cutover launcher, mutation adapter

**Migration Evidence Publication Composition Root**:
The physically separate Issue #59 create-only root that can publish only from
one exact confirmed review fingerprint through one binding-bound role.
_Avoid_: Evidence browser, verifier process, migration command

**Cutover Transaction Composition Root**:
The physically separate Issue #59 single-owner execute, resume, and rollback
state machine. It accepts only fixed binding-bound roles and one journal owner;
the owner atomically claims the pre-mutation gate and supplies the clock
rechecked before every role and after final audit before success. Backend
packages expose no executable test binder. Test-only roles and journal
callbacks cannot outlive the internally owned temporary scope, and the root
has no arbitrary host, path, selection, or command surface.
_Avoid_: General orchestrator, shell runner, automatic recovery

**Project Container Receipt Chain**:
The exact Issue #59 sequence binding review, package verification, ACL
baseline, pre-mutation freshness, linked prior/current journal heads, terminal
receipt, managed publication, activation, final audit, failed-state
preservation, rollback restoration, and legacy health to one composition
binding. Every partial value is an approved prefix and the chain fingerprint
commits its ordered terminal receipt. It is evidence, never authorization.
_Avoid_: Cutover token, command transcript, mutable run state

**Issue 38 R2 Re-Approval**:
The mandatory human re-review of all fourteen Issue #38 approval items against
the exact final master after Issue #59 merges. The old R1 remains
`NOT EXECUTABLE`; Issue #39 cannot be considered until a new R2 is published.
_Avoid_: Automatic approval rollover, stale-SHA authorization

**Solo Maintainer Closure**:
One canonical, reproducible closure-evidence package followed by an explicit
review and confirmation by the same sole maintainer. It does not claim
separation of duties or independent review.
_Avoid_: Independent approval, external authority

**Hosted Evidence**:
GitHub-hosted commit identity, check-run, workflow, and optional attestation
evidence. It supports provenance and auditability but is not a second human
approval.
_Avoid_: Human approval, independent reviewer

**Solo Maintainer Attestation**:
The maintainer's exact confirmation of one frozen-master-bound manifest
fingerprint. It is not an external signature and is not Issue #39 execution
authority.
_Avoid_: External signature, execution approval

**Execution Confirmation**:
A separate fresh confirmation immediately before any future real-host Issue
#39 operation. Closure evidence cannot substitute for it.
_Avoid_: Closure attestation, reusable authority

**Dynamic Cutover Roster**:
The Issue #39 fresh, bounded discovery of every currently linked worktree. It
binds each checkout's placement, Git identity, physical identity,
administrative identity, branch, commit, common directory, and clean state;
any addition, removal, dirtiness, or identity drift before the next host effect
stops the cutover. It is an additive Issue #39 execution contract and does not
rewrite the historical fixed eleven-worktree rehearsal contracts.
_Avoid_: Expected worktree count, partial worktree sample, mutable worktree list
