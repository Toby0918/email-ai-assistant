---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0012: Issue 39 Project Container cutover orchestration

## Status

Accepted for governed code enablement and synthetic verification. The exact
production-consumer allowlist is limited to the fixed Issue 39 orchestrator,
its sole script, and its package-owned retained restart runner. This decision
does not authorize the real incident-stage disposition, closure confirmation,
protected verifier, or Project Container cutover. A later explicit execution
authorization is still required.

## Context

The earlier cutover modules deliberately proved individual contracts in
synthetic sandboxes and kept production composition dormant. Issue 39 needs one
operator command that composes those reviewed boundaries without exposing an
arbitrary path, command, adapter, recovery, or cleanup surface.

The historical transaction rehearsals bind a fixed eight-embedded plus
three-external roster. The live repository has a different number of linked
worktrees and that number can legitimately change before the authorized
cutover. Treating either number as an implicit production constant would omit
worktrees or force unrelated rehearsal contracts to change.

The operation also spans irreversible-looking intermediate states: an incident
stage is archived, a repository and Git administration are reparented, managed
units are published create-only, and services are started and stopped. A crash
must not cause an ambiguous action to be repeated or a retained failure state
to be cleaned automatically.

## Decision

Add one versioned `backend.r2_issue39_orchestrator` composition root and one
fixed script, `scripts/execute_project_container_cutover.py`. The script accepts
only the `run` verb and owns no caller-selected paths or adapters.
Its initial invocation is restricted to the code-fixed registered worktree
`D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement`.
The wrapper rejects the legacy root, alternate worktrees, copied scripts and
reparse aliases before importing the orchestrator. Before any catalog effect,
the process still transfers to the independently verified external retained
runner; the initial launcher and restart anchor are separate roles.

The command order is a security boundary:

1. Perform zero-mutation local and fixed GitHub GET readiness, including the
   closure artifacts, eligible master, Issue 38 closed state, fixed inputs,
   complete worktree roster, and incident-stage state.
2. Require the same directly connected visible Windows console for stdin,
   stdout, and stderr.
3. If required, obtain a separate fresh incident-disposition confirmation and
   archive only the fixed reviewed stage with a same-volume no-replace move.
4. Rebuild the full preparation after disposition and reject every observed
   drift before binding production capabilities.
5. Obtain a fresh, action-specific Execution Confirmation before every catalog
   action and before either terminal success or legacy-restoration sealing.
   Every Issue 39 confirmation adapter first displays a strict content-free
   phase/operation/command/direction/state/sequence context line. Only the
   following candidate and acknowledgement are entered.

The fixed reviewed incident source and archive share the single leaf
`.r2-solo-maintainer-closure-v1.incident-794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721`.
The source parent and archive parent remain separately code-fixed. No obsolete
`.stage-...` alias, caller path, discovery fallback, or alternate leaf is
accepted.

The archive parent is also a fixed production boundary. Zero-mutation readiness
binds whether the exact hierarchy
`D:\IncidentArchives\email_ai_assistant\issue38` is already exact, safely
provisionable, or blocked, together with component presence and opened
identities. After the separate incident confirmation, disposition must
reproduce that exact fingerprint before any create. A missing hierarchy may be
created only as the three code-fixed components relative to held parent handles,
and the full chain remains held and placement-revalidated through rename and
artifact reread, with native create-only/no-replace semantics, fixed-drive NTFS
and non-reparse validation, and one protected three-principal DACL. That
DACL grants inheritable Full Control only to the current token SID, LocalSystem,
and built-in Administrators. Existing mismatches, post-confirmation competition,
parent replacement, and create collisions fail before the source move; partial
create-only state is retained and never cleaned automatically. The drive root
is read-only validated and its security is never changed.

Issue 39 discovers all linked worktrees during every fresh prepare, with a
bounded maximum. It binds the root/common/admin identities and every checkout's
placement, physical identity, administrative identity, branch, commit, common
directory, and clean status. Any addition, removal, dirtiness, or identity
change stops before the next host effect. This Dynamic Cutover Roster is
additive; the fixed eleven-worktree contracts remain historical rehearsal
contracts and are not weakened.

The production action catalog is closed and catalog-owned. The portable
six-worktree synthetic baseline contains 27 actions, of which 24 have host
effects. A 2026-08-29 read-only live observation found 14 linked worktrees,
which would derive 35 actions and 32 host effects if unchanged; production
never treats either count as fixed and recomputes the bounded complete roster.
Dispatch is determined by the action phase plus its exact catalog-owned name,
not by a caller registry or a string-prefix fallback.

Claims, intents, observations, recovery classifications, commits, and terminal
records are appended to a create-only durable ledger before later effects.
Restart uses the fixed runner copied into the retained evidence package. Two
stable observations classify a pending effect; ambiguity stops, an already
present effect is never repeated, and rollback follows only the committed
catalog prefix in reverse with fresh confirmations. No recovery path deletes,
replaces, fetches, prunes, or cleans retained state. The sole exception to the
general repair prohibition is the catalog-owned, journaled, exact bound
`git worktree repair` required to relocate or recover a reviewed worktree
administrative link; no caller-selected or manual repair surface exists.

Runtime publication consumes only the fixed Python 3.12.13 source and the
create-only hash-locked Windows wheelhouse. Database publication requires the
legacy service stopped, absent SQLite sidecars, a stable held source identity,
and a create-only target. If a fresh prepare proves there is no historical
database source, only the separately defined first-start create-only
initialization may be used. CRX and Config are likewise fixed and create-only.

Terminal success is sealed only after two fresh complete reads bind the final
layout, roster, Git identities, ACLs, managed units, service identity,
provider-disabled health, and database proof. Recovered legacy state is sealed
only after two fresh reads prove the restored source, worktrees, Git
administration, ACLs, services, and retained failed container. Public success
is exactly `PROJECT_CONTAINER_CUTOVER_SUCCEEDED`.

## Considered options

### Keep production composition dormant

Rejected because it cannot execute Issue 39 and leaves the operator to compose
security-sensitive steps manually.

### Accept paths, manifests, or action plugins from the command line

Rejected because caller-selected capability would bypass the reviewed fixed
roles and make confirmation scope ambiguous.

### Reuse the fixed eleven-worktree rehearsal roster

Rejected because it is neither a complete observation of the live linked
worktree set nor stable across prepares. The historical contract remains useful
for the rehearsed topology and stays unchanged.

### Use one umbrella confirmation

Rejected because incident disposition, forward effects, resume, rollback, and
terminal sealing have different durable journal heads and different risks.

### Automatically clean partial state

Rejected because cleanup destroys the evidence needed for deterministic crash
classification and operator-directed incident handling.

## Consequences

- Operators receive one fixed command but still perform visible, fresh,
  per-action confirmations.
- Any readiness or roster drift fails closed before the next host effect.
- A real run can be resumed only from its retained evidence runner and durable
  journal; copying an old confirmation or rerunning an ambiguous effect fails.
- Production modules become reviewed consumers of the earlier narrow cutover
  primitives. Normal runtime, frontend, mailbox, provider, vault, and private
  data surfaces remain unable to reach them.
- Windows synthetic tests are slower because they exercise real fixed handlers,
  service identities, forward publication, and complete reverse restoration.
- Green tests, a merged PR, and this ADR are implementation evidence only and
  never authorize the real command.
- The three historical standalone preflight, evidence, and transaction roots
  remain unconditionally dormant and are not an alternate operator surface.
