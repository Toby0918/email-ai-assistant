---
last_update: 2026-07-23
status: draft
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0009: Project container and repository boundaries

## Status

Accepted as a design on 2026-07-23. The Issue #30 compatibility seam and Issue
#33 protected private-store policy are implemented, but no Project Container
directory migration or operational cutover has occurred. While this ADR remains
draft, the current flat paths and the active security contracts in ADR 0006
through ADR 0008 remain authoritative.

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
