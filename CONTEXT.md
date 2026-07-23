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
recovery material on a different security domain.
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
