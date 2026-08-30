---
last_update: 2026-08-20
status: active
owner: "@tobyWang"
review_cycle: quarterly
source_type: decision_record
---

# ADR 0010: Solo-maintainer closure and execution confirmation

## Status

Accepted for repository implementation under Issue #110. Ruleset `20601214`
now exists as separately approved GitHub state. Its presence does not authorize
live closure, Issue #105 disposition, Issue #38 review or Issue #39 execution;
those remain separate decisions.

## Context

The project has one maintainer and no approved external R2 authority,
independent reviewer or offline gate-signing party. The private keys assumed by
the former fourteen-signature model are unavailable. Multiplying keys or role
names controlled by one person would not create separation of duties, while
retaining the old model would leave final review and later command confirmation
behind an impossible gate.

GitHub-hosted checks can prove commit and workflow provenance, but they are not
a second human approval. A closure receipt can make a frozen master eligible
for review, but it cannot approve Issue #38 or authorize Issue #39.

## Decision

Replace the V1 external-signature closure and V2 authority envelope completely.
One deep `SoloMaintainerClosure` derives a canonical frozen-master manifest and
accepts one fresh exact confirmation through only `prepare()` and `confirm()`.
It records the actual assurance model:

```text
SOLE_MAINTAINER_SELF_REVIEW
operator_count=1
independent_reviewer_count=0
external_signer_count=0
issue39_authority_count=0
```

The manifest binds five current push/master GitHub Actions checks, one exact
active master ruleset snapshot, fourteen local evidence gates, eight ordered
gap proofs and one `ApprovedCutoverBindingV3`. Hosted evidence has zero human
approval. Candidate and receipt JSON are strict canonical ASCII objects with
domain-separated SHA-256 identities.

Hosted run/job metadata remains a fixed anonymous HTTPS read. Guardrail state
uses a separate package-private authenticated adapter described by ADR 0011:
the code-fixed absolute Windows GitHub CLI, the existing `Toby0918` keyring
identity for `github.com`, identity checks before and after exactly three fixed
GETs, a sanitized allowlist environment with update checks and telemetry
disabled, separately bounded stdout/stderr, and no Python token read or print.
Only the exact content-free classic 404 diagnostic may accompany HTTP 404 /
exit 1 for that fixed absence check.
Authenticated `bypass_actors` must be explicitly `[]`. The only wire response
compatibilities accept `pull_request.parameters.required_reviewers` when absent
or exactly `[]` and accept
`pull_request.parameters.require_extra_approval_for_unattributed_changes` when
absent or exactly `true` only if `required_approving_review_count` is the exact
integer `0`. Only those approved wire defaults are removed before exact
comparison. The canonical configuration remains 965 bytes with fingerprint
`5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`.

Local gate inputs use private `LocalSourceProofV1` values. Each proof binds the
same final commit/tree/source package and ordered exact canonical, frozen-blob,
hosted-record/job-step, or fresh read-only observation subjects. The model uses
`quality_gate_review` instead of fabricating a `standards_review`. A successful
hosted typed-contract test is not evidence that a durable runtime receipt
instance was created or retained.

Confirmation is a one-use Windows real-console ceremony with two visible exact
inputs, stable stdin/stdout/stderr console handles, and both wall and monotonic
time inside a half-open 300-second window. The implementation cannot claim to
distinguish typing from operating-system paste. Publication is fixed,
create-only/no-replace and never cleans a failed stage.

Publication linearizes at the final stable parent/child/DACL/oplock observation,
immediately followed by the exact-target no-replace rename. An arbitrary legacy
or other-stage sibling created strictly after that linearization is a subsequent
incident rejected by the verifier. This contract makes
no atomic arbitrary-sibling exclusion claim against an uncooperative writer and authorizes no
Git-common DACL mutation, kernel filter, or volume lock.

The no-argument verifier remains independently hardened around raw Git objects,
safe path materialization and current public GitHub state. It accepts only the
new manifest and attestation receipt and may return only
`ELIGIBLE_FOR_ISSUE38_FINAL_REVIEW`; this is evidence, not approval.

Later command authority uses one fresh `ExecutionConfirmationV1` bound to the
V3 binding, closure artifacts, one command/action and the exact durable-journal
position. A confirmed claim must be appended before an Adapter attempt, becomes
consumed by the attempt and cannot replay. In Issue #110 the primitive is
production-unreachable: all roots return `DORMANT_NO_ISSUE39_APPROVAL` before
any input or Adapter. Future wiring requires separate #38 and #39 decisions and
a new exact code allowlist.

## Considered options

### Preserve the external-signature model

Rejected because the required independent keys and actors do not exist. A
compatibility parser would preserve the deadlock and create two trust models.

### Generate replacement keys in the repository

Rejected because repository code and Codex must never manufacture, custody or
use private R2 signing authority. Same-owner keys would not add independence.

### Treat CI or GitHub Actions as approval

Rejected because hosted execution proves provenance, not human review. Every
hosted record therefore carries zero human approvals.

### Let closure acknowledgement unlock execution

Rejected because closure review and real-host execution have different timing,
scope and risk. Their acknowledgements, schemas, validity windows and decisions
remain deliberately disjoint.

## Consequences

- The historical #105 external-signature contract remains recorded as never
  passed and superseded; its artifacts are not compatible inputs.
- Ruleset `20601214` satisfies the separately created GitHub-state prerequisite
  only when a fresh authenticated observation exactly matches the canonical
  guardrail contract. This ADR still does not authorize live `prepare`,
  `confirm`, the protected verifier or any follow-on disposition.
- A new master invalidates old R1 review/window evidence. #38 requires a fresh
  fourteen-item review after merge.
- #39 stays blocked until separate approval and a fresh action-specific
  Execution Confirmation.
- Partial create-only stages and legacy artifacts are never automatically
  migrated, overwritten or deleted.
- A separately authorized historical-evidence rollover may retain one valid
  stale active closure only after master advances. It is a 300-second,
  single-use compare-and-swap followed by a same-parent, same-volume,
  identity- and DACL-preserving no-replace rename to a deterministic historical
  name. It performs no copy, deletion, overwrite, cleanup, repair or pathname
  rollback and creates no current approval or execution authority.
- A parent without `FILE_DELETE_CHILD` is bridged only while a candidate-bound
  parent namespace guard is pending: the exact protected source DACL briefly
  grants standard `DELETE` to its object owner through a held control handle.
  The rename handle is obtained, the exact original DACL is restored and
  rechecked, and the temporary handles close before normal commit rechecks. The
  Git-common parent DACL is never changed and the retained historical evidence
  keeps the original DACL.
- The protected verifier continues to accept only the fixed active directory;
  historical closure evidence is audit evidence and cannot satisfy #38 or #39.
- Existing Adapter identity, preflight, rollback/recovery, retention/no-deletion,
  provider-disabled, mailbox, vault and private-data boundaries remain intact.
