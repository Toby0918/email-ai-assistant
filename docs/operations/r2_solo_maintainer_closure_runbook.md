---
last_update: 2026-08-29
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Solo Maintainer Closure runbook

## Purpose

This runbook describes the implemented #110 repository contract. Ruleset
`20601214` now exists, but this runbook does not authorize ruleset mutation, a
live closure, the protected verifier, Issue #38 approval, or any Issue #39
action. The assurance model is always:

```text
assurance_model=SOLE_MAINTAINER_SELF_REVIEW
operator_count=1
independent_reviewer_count=0
external_signer_count=0
issue39_authority_count=0
```

## Frozen implementation baseline

```text
repository=Toby0918/email-ai-assistant
ref=refs/heads/master
commit=8f12b21a7597b7ffa51422bfef3e38047e20153a
tree=feefb8c29a832fcf2def11b95a8a5ef244d893c9
```

Implementation must stop if this baseline, Issue #110 authorization, GitHub
protection state, or required-check identities drift. Code and tests do not
create a ruleset or run a live confirmation.

## Interface

The only closure writer is `SoloMaintainerClosure`:

```python
candidate = closure.prepare()
receipt = closure.confirm(candidate.manifest_fingerprint, exact_acknowledgement)
```

`prepare()` is parameterless and read-only. `confirm()` accepts only the exact
manifest fingerprint and this literal acknowledgement:

```text
CONFIRM_SOLO_MAINTAINER_CLOSURE_V1_NOT_ISSUE39_AUTHORITY
```

Callers cannot select repository paths, Git refs, evidence, checks, rulesets,
fingerprints, storage, keys, credentials, or destinations. Test ports exist
only behind the same two-method interface.

## Candidate review

Ruleset presence is only a prerequisite. After live `prepare` is separately
authorized, an operator may run:

```powershell
& 'D:\Projects\email_ai_assistant\.venv\Scripts\python.exe' -I -B `
  scripts\close_r2_final_master.py prepare
```

The sole acceptable success status is:

```text
AWAITING_SOLO_MAINTAINER_CONFIRMATION
```

The candidate expires after exactly 300 seconds. It is review material only;
it is not portable authority input and does not write any artifact.

Review the embedded manifest for exactly:

- one frozen final commit/tree and one final-master binding;
- five current push/master GitHub Actions hosted checks from app `15368`;
- one exact active `master-solo-maintainer-closure-v1` ruleset snapshot;
- fourteen verified evidence records and eight ordered gap proofs;
- `ApprovedCutoverBindingV3` with no public-key/signature/envelope fields;
- all approval, execution, #39, finding, skip, divergence, leakage, private-data,
  provider, real-host, cleanup, deletion, overwrite and failure counts at zero.

Hosted evidence is provenance. It is never human approval.

Every local source entry includes its exact proof kind. `quality_gate_review`
binds the frozen workflow/guard tests and the same-SHA successful
`quality-gates` job steps; it does not claim a human or independent Standards
review. Each hosted step's job id must equal its hosted record, and every proof
accepts only its source-specific ordered subject names. Receipt- or proof-named
sources mean the corresponding frozen typed
contract was exercised by the bound hosted run, not that a durable runtime
receipt was created and retained. Generated status, leakage and maintenance
are freshly rerun against the verified checkout. Status equivalence normalizes
only platform line endings and the unique date/date/branch snapshot fields and
still binds the frozen status blob; every other byte is exact. Leakage must be
empty. Maintenance must produce twenty-four unique classifications exactly equal
to the fixed `(severity, category, path, doc)` registry; missing, duplicate, or
new paths block closure.

## Authenticated guardrail prerequisite

The separately approved GitHub-state change created ruleset `20601214`. Every
derivation must freshly prove exactly one active branch ruleset named
`master-solo-maintainer-closure-v1`, targeting only `refs/heads/master`, with no
bypass actors, classic branch protection absent, deletion and non-fast-forward
rules, pull-request thread resolution with zero required approvals, and these
five strict required checks from integration id `15368`:

```text
quality-gates
portable-provenance
windows-native-provenance
windows-independent-provenance
provenance-reconciliation
```

Do not add `cleanup-scan`, signed commits, deployments, merge queue, linear
history, branch lock, bypass, or classic-protection layering.

Hosted run/job metadata continues through the code-fixed anonymous public HTTPS
reader. Protection state alone uses the code-fixed absolute
`C:\Program Files\GitHub CLI\gh.exe`, the existing active `Toby0918`
`github.com` keyring identity, auth-status checks before and after exactly three
fixed GET requests, and a sanitized allowlist environment. Python never reads
or prints the token. Update checks and telemetry are disabled; stdout/stderr are
separately bounded, and only the exact content-free classic 404 diagnostic may
accompany that fixed endpoint's HTTP 404 / exit 1 absence result. Authenticated detail must explicitly expose
`bypass_actors=[]`. The unique pull-request rule accepts
`required_reviewers` only when absent or exactly `[]`.
`require_extra_approval_for_unattributed_changes` may be absent or exactly
`true` only when `required_approving_review_count` is the exact integer `0`.
Only those approved wire defaults are removed before equality with the
unchanged 965-byte canonical configuration and configuration fingerprint
`5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`.
Nonempty, false, wrong-type, nonzero-count, duplicate or otherwise drifted state
fails closed.

Neither ruleset existence nor a successful read-only local test authorizes the
commands in the following sections.

## Confirmation boundary

Live confirmation is separately approved and Windows-only:

```powershell
& 'D:\Projects\email_ai_assistant\.venv\Scripts\python.exe' -I -B `
  scripts\close_r2_final_master.py confirm
```

The process performs a fresh prepare, displays the candidate and fingerprint,
then visibly reads the exact fingerprint once and the exact acknowledgement
once. `stdin`, `stdout`, and `stderr` must each remain the same real console
handle with valid `GetConsoleMode` state. Only one terminal CRLF is removed;
case, whitespace, extra lines, NUL, ESC, C0/C1, bidi and format controls fail.
The code does not call a clipboard API and cannot claim to detect or prevent an
operating-system or terminal paste.

Both wall time and monotonic time use the half-open interval `[0, 300 seconds)`.
Clock rollback, console drift, manifest drift or the exact 300-second boundary
fails closed. After both inputs and before publication, the process rechecks
Git bytes, remote master, all hosted metadata, ruleset state, local evidence,
TTY identity and both clocks.

## Create-only publication

The fixed Git common-directory target is:

```text
r2-solo-maintainer-closure-v1/
  solo-maintainer-closure-manifest-v1.json
  solo-maintainer-attestation-receipt-v1.json
```

The fixed stage is
`.r2-solo-maintainer-closure-v1.stage-<manifest_fingerprint>`. Target or stage
collision stops. Files and directory publication are create-only/no-replace;
canonical bytes, file set, handles, identities, link count, reparse/ADS state,
DACL, oplock and durable flush are checked before the no-replace directory
rename. A failure leaves the partial stage untouched for incident review. Code
never overwrites, deletes, prunes, repairs, migrates or cleans a stage, target,
legacy `r2-final-master-closure-v1`, or V1 external artifact.

The linearization point is the final stable parent/child/DACL/oplock observation,
immediately followed by the exact-target no-replace rename. An arbitrary legacy
or other-stage sibling created strictly after that linearization is a subsequent
incident rejected by the verifier. This boundary provides
no atomic arbitrary-sibling exclusion against an uncooperative writer and grants no authority to
mutate the Git-common directory DACL, install a kernel filter, or take a volume
lock.

The sole success status is:

```text
SOLO_MAINTAINER_ATTESTATION_RECORDED
```

The receipt still has approval, execution authority and Issue #39 authority at
zero.

## Historical evidence rollover after master drift

If the active directory is internally valid but binds a strict ancestor of a
new clean exact master, do not overwrite, delete, copy, repair or manually move
it. After a separate exact authorization, run the fixed command only from the
verified new-master worktree:

```powershell
& 'D:\Projects\email_ai_assistant\.venv\Scripts\python.exe' -I -B `
  scripts\rollover_r2_solo_maintainer_closure.py run
```

The command prints one canonical 300-second candidate to stderr, fresh-rechecks
the same Git/artifact/identity/DACL state, and consumes only that candidate. The
only success status is:

```text
HISTORICAL_CLOSURE_EVIDENCE_RETAINED
```

The deterministic retained name is
`r2-solo-maintainer-closure-v1.historical-<commit-16>-<manifest-16>` under the
same Git common directory. Success is one same-parent, same-volume, no-replace
directory rename preserving the two original files and their identities. Any
failure or ambiguous post-commit state stops for a separate incident
disposition; never rename back, delete, overwrite or clean up by pathname.

Rollover is not closure confirmation, protected-verifier eligibility, Issue #38
approval, Execution Confirmation, or Issue #39 authority. After success, create
and confirm a fresh active closure against the new master, then run the protected
verifier and obtain a new fourteen-item #38 final review.

## Read-only eligibility verification

The protected verifier is no-argument and isolated:

```powershell
& 'D:\Projects\email_ai_assistant\.venv\Scripts\python.exe' -I -B `
  scripts\verify_r2_final_master_closure.py
```

It re-materializes and validates the current frozen Git tree before importing
repository code, requires a clean exact master, rereads public hosted checks
and the current GitHub guardrail snapshot, accepts only the two new canonical
files, and rejects all legacy V1 external/signature artifacts without fallback.
On Windows it compares path/open-handle identity using device, file index, size,
and file type while ignoring only CPython-synthesized permission-bit differences;
reparse/link paths, non-regular objects, byte drift and Git tree-mode drift still
fail closed. Non-Windows identity continues to compare the complete mode.
The sole success status is:

```text
ELIGIBLE_FOR_ISSUE38_FINAL_REVIEW
```

Eligibility is not Issue #38 approval. All fourteen R2-D38 review items must be
freshly reviewed against the later merged master.

## Dormant Execution Confirmation

#110 also implements a pure `ExecutionConfirmationV1` contract bound to one
V3 production binding, closure manifest/attestation, command/action, operation,
current journal head, next sequence, transition and remaining reverse plan. Its
future exact acknowledgement is:

```text
CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION
```

The same real-console and 300-second rules apply. A future claim must be
create-only appended to the durable journal before the Adapter attempt and is
consumed by that attempt even when the attempt fails. It cannot replay or
substitute for closure attestation, Issue #38 approval, or Issue #39 enablement.

In this implementation every preflight, evidence and transaction production
root returns `DORMANT_NO_ISSUE39_APPROVAL` before reading argv, TTY, clock,
candidate, artifact or Adapter. No environment, file, argument, acknowledgement
or artifact unlock exists. Wiring requires future separate #38 approval and a
new #39 exact code Add/Modify/Delete decision.

## Fixed failure output

Failure is one canonical line with a fixed status and exit code `2`. No path,
commit, run id, exception, input, environment or progress is emitted. Codes are:

```text
R2_SOLO_MAINTAINER_CLOSURE_INVALID
R2_SOLO_MAINTAINER_CLOSURE_TTY_REQUIRED
R2_SOLO_MAINTAINER_CLOSURE_FINGERPRINT_REJECTED
R2_SOLO_MAINTAINER_CLOSURE_ACKNOWLEDGEMENT_REJECTED
R2_SOLO_MAINTAINER_CLOSURE_STALE
R2_SOLO_MAINTAINER_CLOSURE_MASTER_DRIFT
R2_SOLO_MAINTAINER_CLOSURE_HOSTED_EVIDENCE_REJECTED
R2_SOLO_MAINTAINER_CLOSURE_GITHUB_GUARDRAIL_REJECTED
R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED
R2_SOLO_MAINTAINER_CLOSURE_ALREADY_EXISTS
R2_SOLO_MAINTAINER_CLOSURE_PUBLICATION_REJECTED
```

## Issue disposition

- #105 remains open until a separate post-merge decision. Its original external
  signature contract never passed and may only later close as not planned /
  superseded by #110.
- #38 remains open. Solo Maintainer Attestation creates review eligibility only.
- #39 remains blocked. Closure evidence can never authorize execution.
- The old R1 SHA, 2026-08-08 window, evidence, receipt and acknowledgement are
  historical and cannot be reused.

## Validation

Use the pinned Python at `D:\Projects\email_ai_assistant\.venv\Scripts\python.exe`.
Run the exact focused, affected, architecture, mechanical, documentation,
maintenance, leakage, compile, diff and full-suite matrix in the #110 proposal.
After status generation, rerun documentation/status, maintenance, leakage and
the complete suite. The exact A/M/D name-status set and both Standards/Spec
reviews must finish CLEAN/PASS before a local implementation commit.
