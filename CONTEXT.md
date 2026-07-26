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
