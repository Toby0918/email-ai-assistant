---
last_update: 2026-08-30
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# Project Container cutover contract security boundary

## Issue #110 Solo Maintainer Closure security boundary

The fixed no-argument verifier retains the Issue #102 trust chain: isolated
safe-path Python, exact current-script bytes, clean tracked and untracked state,
no assume-unchanged/skip-worktree entries, scrubbed Git environment and disabled
replacement refs, local/fresh fixed-URL `master` equality, independent raw
commit/tree/blob hash reconstruction, Win32 unsafe-path and alias rejection,
verified-tree materialization, and verified import origins before repository
imports. Callers cannot select a path, ref, receipt, endpoint, or command.

The new closure replaces, rather than layers on, the V1 global-gate/external-
signature model. It accepts exactly five newest successful `master` `push`
GitHub Actions checks from app id `15368`, fourteen content-free evidence
records, eight dependency-ordered gap proofs, one exact GitHub guardrail
snapshot, one manifest, and one Solo Maintainer Attestation. All facts bind one
commit/tree/source/runbook/workflow/V3 production binding; every finding, skip,
divergence, leakage, private-data, provider, host, cleanup, approval, execution,
and Issue #39 count is zero.

Local proof fingerprints cannot be supplied by a caller or synthesized from a
source label. They are constructed only after the exact GitHub snapshot from
canonical typed values, relevant frozen blob identities and same-SHA successful
job-step evidence, or fresh read-only generated-status, maintenance and leakage
observations. Hosted typed-test success is not a durable runtime receipt and
`quality_gate_review` is not an independent or human review.

The guardrail snapshot requires exactly one active master-targeted ruleset,
zero bypass actors expressed as explicit `bypass_actors=[]`, deletion and
non-fast-forward protection, strict app-bound
required checks for the five contexts, and the approved pull-request rule while
classic branch protection is absent. Missing, extra, layered, stale, or
mismatched protection fails closed. Hosted run/job metadata remains on the
fixed anonymous public HTTPS reader. Guardrail observation alone runs absolute
`C:\Program Files\GitHub CLI\gh.exe` with the existing active `Toby0918`
`github.com` keyring identity, validates auth before and after exactly three
fixed GETs, and passes only a sanitized allowlist environment with update checks
and telemetry disabled. Stdout/stderr are separately bounded, with only the
exact content-free classic 404 diagnostic allowed for HTTP 404 / exit 1. Python
never reads or prints the token. The unique pull-request rule accepts
`required_reviewers` only when absent or exactly `[]`.
`require_extra_approval_for_unattributed_changes` may be absent or exactly
`true` only when `required_approving_review_count` is the exact integer `0`.
Only those approved wire defaults are removed before exact comparison with the
unchanged 965-byte canonical configuration and fingerprint
`5f1c00727e4637c58abc7a8299f6c5846be0d8b6b3511d84bf3114e17422ca6e`.
The adapter has no custom endpoint, arbitrary URL, ruleset writer,
branch-protection writer or approval surface.

Ruleset `20601214` now exists as separately approved GitHub state. That fact is
not authorization to run live `prepare`, `confirm`, the protected verifier,
approve Issue #38 or execute Issue #39.

The protected verifier accepts only the exact manifest and attestation files in
the fixed Git common directory and explicitly rejects every legacy V1 external,
signature, compatibility, fallback, or alternate trust artifact. Its only
positive status is `ELIGIBLE_FOR_ISSUE38_FINAL_REVIEW`; the attestation records
one operator and zero independent, external, and hosted-human reviewers. These
values cannot approve Issue #38, authorize or execute Issue #39, mutate a host,
or access provider, mailbox, vault, credential, private data, cleanup, deletion,
or overwrite capability.

## Issue #100 frozen Git-object package and CI provenance

The CI source package is constructed from the candidate commit's Git object
database, never from mutable checkout bytes. It binds the exact final commit
and tree, every selected blob OID and byte digest, selected counts, the
generated runbook digest, and the workflow/action lock. A commit/tree change
during collection, a malformed blob frame, an omitted or duplicate entry, or a
historical package fails closed. Untracked and ignored content, including any
private dataset or local credential artifact, is neither enumerated nor read.

Every workflow action is pinned to a full commit hash and every runner uses a
fixed image label. Linux and Windows each have a complete 31-distribution wheel
lock; all installs use `--require-hashes`, and receipts bind installed metadata,
platform wheel hashes, and nine direct import-byte hashes. Portable discovers
the full test suite while excluding only registered Windows-native skips;
Windows-native and independent-Windows jobs run their closed suites. Every
remaining skip or failure is fatal, then repository leakage must be zero.
Reconciliation requires one receipt per kind, exact agreement
on final commit/tree, source package, workflow lock and runbook, and three
distinct runner fingerprints. Missing, mixed, stale, duplicate, self-replaced,
skipped, divergent, failed, or leaking evidence cannot become a bundle.

The package and receipts contain fingerprints and aggregate counts only. They
do not expose paths or bytes, issue authority, access a live host, call a
provider, read mailbox/vault/private data, perform cleanup, or authorize #38 or
#39. CI success remains synthetic/offline evidence for later human review.

## Issue #99 generated final R2 operator runbook

The executable vocabulary has one source:
`backend/r2_production_binding/catalog.py`. Six preflight verbs, one evidence
publication verb, and three transaction verbs cover the exact production
command enum. The generated catalog remains a structural reference, but Issue
#110 production dispatchers stop before acknowledgement, confirmation, Adapter,
or operation access. Unknown, umbrella, batch, cleanup, or historical R1
commands do not resolve.

The final runbook is generated from that catalog, its closed phase graph, the
fourteen Issue #38 decisions, and the four R1 blocker-class completion proofs.
Forward and reverse crash handling, LIFO rollback, #98 reconciliation, zero
deletion, and human-only final review are state-machine facts rather than a
second handwritten command system. Verification binds the current final
commit/tree, exact source-package and runbook hashes, package semantics, and
same-binding retention proof. The document and receipt never authorize an
operation. The historical standalone roots remain
`DORMANT_NO_ISSUE39_APPROVAL`; Issue #39 separately permits only its fixed
orchestrator graph, and real-host execution authority remains a fresh decision.

## Issue #98 object-level retention ledger

The retention ledger is computed only from the reviewed binding, linked
#94-#97 plans, and current unified journal. It separately accounts for every
original state, new state, partial-state preservation duty, failed Container,
forward/reverse commit evidence, journal genesis, and journal record. Entries
contain only roles, ordinals, counts, booleans, and fingerprints; no path,
object bytes, private payload, timer, or operator-selected artifact is accepted.

Every forward, recovery-required, rollback-pending, classified, resumed,
rollback-complete, and legacy-restored projection is reconciled against the
same journal head. The proof requires zero untracked artifacts and zero
deletion, overwrite, prune, automatic-expiry, destructive, or private-payload
capability. Static reachability scans independently require the complete
#93-#98 production graph to contain no such operation or normal-runtime entry.

## Issue #97 journal-derived rollback and legacy recovery

Rollback begins only from the exact same-binding durable forward COMMIT prefix.
The plan first preserves the failed Container and every partial/new object,
then reverses the committed #94-#96 transitions in strict LIFO order. Callers
cannot supply, omit, select, or reorder reverse boundaries. Every boundary has
a unique remaining-plan fingerprint and requires fresh single-use ROLLBACK
authority bound to that suffix and current journal head.

Exact PRE may create a fresh intent; exact POST may append a recovered commit
without repeating the effect; ambiguity incident-stops. No reverse evidence
permits deletion or cleanup. Only after all reverse commits and exact legacy
topology, service, ACL, identity, and Git/worktree audits may fresh recovery
authority append the sole successful reverse terminal,
`LEGACY_FLAT_LAYOUT_RESTORED`, with zero provider attempts, legacy analysis
writes, destructive operations, or terminal host mutations.

## Issue #96 two-start validation and final seal

`R2TwoStartValidationPlanV2` binds seven ordered lifecycle transitions after
all managed publication commits: Start A, one rules-only analysis and row,
Stop A, final database proof, independent stopped-layout audit, distinct Start
B, and independent final-running audit. Evidence binds one reviewed final
master, exact runs/nonces/actors, one analysis, one row, and
`provider_attempts=0` without process-local issuance state.

Both audit records have exact 300-second windows and distinct actors from the
service processes and each other. A final read-only observation performs
exactly two minimal freshness reads. Only fresh external RESUME authority may
then append exactly one durable CUTOVER_SUCCESS; the seal performs zero host
mutations, and a repeated or mixed-binding seal fails closed.

## Issue #95 managed-unit single-actions

`R2ManagedUnitPlanV2` extends a completely committed foundation plan with
exactly eight transitions: PREPARE then PUBLISH for Runtime, Database, CRX, and
Config. Every transition binds the reviewed final master, foundation plan,
fixed production owner, predecessor, and immutable pre/post state.

Accepted effects bind exact identity, bytes, ACL, and unit-specific semantic
conformance while retaining source, partial, and failed-unit evidence. The
destructive-operation count is fixed at zero. Recovery requires a separate
read-only proof that both ACL and unit semantics are exact; Database semantics
include SQLite integrity and sidecar state. PRE/POST/AMBIGUOUS then follow the
same fresh-authority, no-replay, and incident-stop rules as foundation work.

## Issue #94 foundation single-actions

`R2FoundationPlanV2` binds exactly seventeen foundation transitions to the
reviewed final master: service quiescence, legacy anchor rename, Container and
main publication, whole-tree ACL conformance, Repository Root relocation, and
eleven independently owned worktree reconstructions. The next transition is
derived from the committed journal prefix; callers cannot select, omit,
duplicate, or reorder an effect.

Each execution authority starts at most one transition and each accepted
completion records exactly one host mutation. After interruption, exact PRE
requires new resume authority before a new intent; exact POST requires new
resume authority and appends only a recovered commit. Ambiguity appends one
content-free recovery classification and incident-stops. All tests are pure
and synthetic; no foundation role owns a real host or issuer.

## Issue #93 unified transaction journal

`R2TransactionJournalV2` is the only append-only chain for all later R2
production transitions. Length-framed canonical records bind one reviewed
production binding, journal owner, monotonically increasing sequence, exact
predecessor head, transition instance, and the durable single-use authority
claim where required. Unknown records, replay, duplicate sequence, owner/head
drift, noncanonical bytes, or a torn frame tail fail closed during
fresh-process reconstruction.

The journal vocabulary is closed to authority claim, intent, effect
observation, commit, recovery classification, and terminal state. A pure
read-only tri-state inspection compares two identical content-free
observations against the pending intent and returns exactly effect absent,
effect present, or ambiguous. The receipt performs zero mutation and zero
journal append, is not authority, and cannot own a reader, path, process,
issuer, host adapter, or private payload.

## Issue #92 Git-byte state

`GitByteSnapshotV2` proves selected checkout bytes against exact Git blob-object
bytes and OIDs, clean stage-zero index entries, the Repository Root identity,
fourteen local refs, five closed stable-common-state roles, and both eleven
original and eleven deterministically reconstructed worktree records. Stable
Git common state is fingerprinted separately from worktree administrative state
that is intentionally reconstructed.

The contract is pure and receives bounded bytes from a later fixed adapter; it
owns no path, Git command, filesystem reader, process, or mutation capability.
It therefore cannot enumerate or read ignored or private content. Public JSON
contains only fixed types, counts, object IDs, and fingerprints. The final
`R2GitByteStateReceiptV1` is final-master-bound evidence, never authority.

## Issue #104 Adapter identity retained by Issue #110

The production graph retains exactly three nominal Adapter slots covering six
preflight, one evidence, and three transaction commands. Adapter identity binds
the exact command, authority domain, type module and qualified name, and the
complete owning-module source; it excludes mutable instance state. Registry
rebinding, descriptor/code drift, target replacement, command/domain mismatch,
or source change fails immediate reverification before an invocation.

The latent order remains V3 and execution-confirmation validation, Adapter
reverification, underlying invocation, underlying outcome validation,
completion construction, and completion validation. Issue #110 keeps the
production roots dormant before the first step, so this ordering can be tested
only with synthetic capability-free values. Candidate construction accepts the
Solo Maintainer final-master binding and closed V3 structural facts only; it
accepts no key, signature, envelope, arbitrary identity, path, environment,
credential, signer, issuer, host, provider, vault, private data, or artifact.

## Issue #110 production binding and execution confirmation

`ApprovedCutoverBindingV3` replaces V2 without aliases, compatibility exports,
dual parsers, or fallback. It pins the exact final-master binding, four domains,
ten commands, eighteen production roles, Adapter identities, and assurance
counts `1/0/0`. It owns no filesystem, process, network, clock source, random
source, key, signature, issuer, provider, mailbox, vault, private data, or host
capability.

An execution-confirmation candidate, receipt, and
`ExecutionConfirmationClaimV1` bind the closure manifest and
Solo Maintainer Attestation, exact command/action, journal predecessor and next
sequence, transition instance, remaining plan, applicable reverse plan, stable
same-real-TTY facts, one exact acknowledgement, nonce, and a wall/monotonic
half-open 300-second validity window. The durable claim is appended create-only
before an Adapter attempt; the attempt consumes it even on failure. Wrong,
stale, mixed, replayed, noncanonical, or fingerprint-drifted facts fail before
an effect. Process-local claimed sets cannot substitute for journal state.

The existing `JournalRecordTypeV2.AUTHORITY_CLAIM` wire enum is retained
because its vocabulary file is outside the approved amendment; it identifies
the existing frame position only. The record payload, public fields, append
method, validator, and reconstruction accept only the new
execution-confirmation claim and expose no V2 authority object or parser.

## Issue #110 dormant process roots

The preflight, evidence, and transaction packages remain physically isolated.
Each `__main__.py` imports only local `production_v2.main`; removed
`entry.py`, operator `envelope.py`, `dormant_context.py`, callable-role,
signature, issuer, and synthetic-unlock surfaces are recursively absent.

Every valid fixed verb returns `DORMANT_NO_ISSUE39_APPROVAL` before TTY access,
candidate construction, acknowledgement parsing, confirmation validation,
Adapter lookup/reverification/invocation, journal append, callback, or host
operation. No argument, environment value, file, artifact, acknowledgement,
bootstrap mapping, or synthetic marker can unlock the state. Issue #39 leaves
these roots dormant and permits execution-confirmation reachability only in its
fixed orchestrator graph; real-host execution remains separately authorized.

## Issue #110 closure publication boundary

`prepare` is read-only and noninteractive. Windows-only `confirm` proves
stable real stdin/stdout/stderr console handles, displays and reads the exact
manifest fingerprint and acknowledgement once, rejects extra whitespace and
control characters, and fresh-rederives all repository/hosted/ruleset facts
after input. It does not use or block the clipboard and cannot prevent OS or
terminal capture.

Publication is restricted to the exact manifest and attestation filenames under
the fixed Git common directory. Staging and finalization are create-only,
no-replace, and all-or-nothing. Collision or failure retains stage state for
incident review; there is no overwrite, delete, cleanup, repair, migration, or
retry surface. The legacy external-artifact package, preparation CLI, signed
gate files, and active issuance runbook are deleted, and the old task brief is
kept only as a superseded audit record.

Green tests, CI, hosted checks, closure files, and solo attestation are evidence
only. They do not approve Issue #38, create or approve a ruleset, authorize or
execute Issue #39, push, merge, mutate a real host, access provider/mailbox/
vault/private data, or clean retained failure state.

## Scope

Issue #51 adds the internal Python package `backend.cutover_contracts`. Issue
#52 adds the first approved consumer, the exact
`backend.cutover_journal.contracts_bridge`, inside the pathless synthetic-only
`backend.cutover_journal` state proof. Issue #53 adds the physically separate
`backend.real_host_preflight` read-only composition root and its three exact
bridges: `contracts_bridge.py`, `baseline_bridge.py`, and `audit_bridge.py`.
Issue #54 defines profile-bound evidence review, a physically separate
create-only publication composition, and a separate-process read-only
verification boundary.
The #51/#52 packages remain content-free and add no CLI, HTTP route, default
host adapter, host reader, authorization issuer, or executable real-host
cutover command. The #53 package adds no executable operator command and may
exercise Windows host observation only in a test-owned temporary sandbox.

This contract layer must not inspect or mutate a real Runtime, SQLite database,
ACL, repository, worktree, browser profile, artifact, Config directory,
mailbox, provider, vault, credential, private store, or private data. Real
operator preflight, evidence publication, migration, real cutover, real resume,
real rollback, incident recovery, and cleanup remain outside Issues #51
through #53. Issues #54 through #59 remain separate.

## Locked Cutover Profile

`CutoverProfileV1` accepts one exact closed mapping and freezes the normalized
value. Its canonical identity binds:

- the governing master commit and operator fingerprint;
- exact role, evidence-role, reviewed-Git, and rollback-role fingerprint maps;
- exactly eleven ordered worktree selections: eight embedded and three
  external;
- pinned Python 3.12.13, SQLite 3.50.4, runtime, wheelhouse, and dependency-lock
  inputs, with network and legacy-runtime reuse disabled;
- create-only SQLite and reviewed browser-extension inputs;
- deterministic non-secret Config with both providers disabled and no ambient
  environment read;
- the fixed ACL policy, repeated/fresh preflight requirements, maintenance
  window, and `cleanup_authorized=false`.

The public profile contains no `Path`, drive, directory, SID, SDDL, Git ref or
branch name, command, exception, database row, message, arbitrary detail, or
free text. Unknown fields, wrong types, duplicate or non-canonical JSON,
incorrect enum values, hostile Python mapping keys/values, lone-surrogate
strings, and fingerprint drift fail closed without invoking user comparison
methods. The profile
fingerprint is SHA-256 over the canonical body; it is an integrity identity, not
a signature or an authorization.

## Real-host authorization isolation

Real-host authorization has four distinct nominal types:

- `RealPreflightAuthorizationV1`;
- `EvidencePublicationAuthorizationV1`;
- `CutoverExecutionAuthorizationV1`;
- `RecoveryAuthorizationV1`.

Each type accepts only an externally supplied canonical value and binds an
exact operation, operation fingerprint, profile fingerprint, governing master,
operator fingerprint, phase, and bounded issued/not-before/expiry interval.
The package has no real-authorization `create`, `issue`, `mint`, `generate`,
`sign`, random, secret, or clock function.

`validate_real_host_authorization(...)` uses exact concrete types. A mapping,
duck-typed object, receipt, or `TestSandboxAuthorizationV1` therefore cannot
become real-host authority. Missing, malformed, wrong-type, wrong-profile,
wrong-master, wrong-operation, wrong-operator, wrong-phase, not-yet-valid, and
expired inputs fail closed. Before returning `AUTHORIZED`, the validator
reconstructs both the exact Profile and exact authorization through their
closed public parsers; altered slots, fingerprints, validity, or nested Profile
state therefore return `BLOCKED_AUTHORIZATION_INVALID`. No unchecked
class-level body constructor exists. Malformed canonical input raises only the
fixed contract error; validation mismatches return only closed status values
with one accepted/rejected aggregate pair.

The authorization fingerprint is SHA-256 over the external canonical body. It
detects canonical-value drift but is not a signature, issuer, secret, or proof
that a human approved a host operation. Issue #51 adds no trusted issuer and no
consumer capable of acting on a validated authorization.

## Canonical content-free receipts

`ReceiptEnvelopeV1` uses bounded strict UTF-8 canonical JSON with sorted keys,
compact separators, `allow_nan=false`, duplicate-key rejection, exact fields,
and a verified SHA-256 receipt fingerprint. Its closed type matrix binds the
operation, authorization/profile/master fingerprints, producer, subject role,
ordered input roles and fingerprints, observation fingerprint, bounded
integer counts, bounded validity, status, and fixed detail enums.

The twelve receipt families are preflight, evidence, ACL, repository, worktree,
Runtime, database, artifact, Config, activation, rollback, and incident stop.
No receipt field accepts a path, raw observation, exception, command, host
identifier, database content, message, or arbitrary diagnostic detail.
Non-string or otherwise incompatible receipt types, including JSON arrays and
objects, fail with the same fixed receipt-contract error at every public parser.

A receipt records a canonical content-free claim only. Its parser,
fingerprint, status, or presence does not authorize any operation, prove that
an adapter ran, or establish that a real host observation is true. Receipts and
receipt-like values are rejected by the real-host authorization validator.

## Default-locked operator seam

`default_operator_entry()` has zero parameters. It accepts no path, adapter,
callback, command, environment value, or authorization and always returns
`BLOCKED_NO_APPROVED_COMMAND` with `blocked=1` and `executed=0`. Adding any
executable operator entry or executable real-host operation requires a separate
approved Issue. Issue #53 composes only the locked read-only boundary, and Issue
#54 keeps its real review, publication, and verification entries locked. Neither
provides an approved command; Issues #57 through #59 remain separate.

## Issue #53 Windows read-only observation boundary

The Windows observer opens every controlled component without following
reparse points and derives identity from opened handles rather than path text
alone. Internal observations bind volume identity, 128-bit file ID, exact
object type, parent identity, normalized-name fingerprint, file attributes,
and reparse metadata. Raw paths, file IDs, volume labels, SIDs, SDDL, account
names, Git names/refs, native error values, and callback exceptions are not
receipt or log fields.

No production operator scope exists in Issue #53. The Windows observer and
scope are not package exports. Native Windows behavior may run only below a
caller-owned `TemporaryDirectory` whose exact child marker, root identity, and
marker identity are captured in a package-private, atomically single-use
permit with an exact in-memory `TestSandboxAuthorizationV1`. Absolute paths,
parent-relative escape, scope/authorization mismatch, marker replacement,
permit replay, hard-link alias or reparse components, unexpected
volume/filesystem type, unreadable/incomplete evidence, normalized-name
change, object replacement, and identity drift fail closed. Controlled files
must report exactly one link through read-only opened-handle metadata.
The test authorization remains invalid at the exact real-host validator and
cannot enter the operator seam.

Linux executes the portable immutable contracts and injected composition only.
A Linux test may prove canonical validation, drift handling, fixed output, and
capability separation; it cannot claim NTFS, Windows file-ID, Windows ACL, or
real-host observation evidence.

## Current topology and pre-mutation freshness

`CurrentTopologyPreflight` obtains two complete observations. An accepted
`CurrentTopologyPreflightReceiptV1` requires the second source, target parent,
target absence, controlled-component reparse state, Git, ACL, and volume
evidence to be exactly identical to the first complete pass. A partial second
read, incomplete evidence, content observation, callback exception, or any
drift produces only a fixed rejected result.
Each portable callback value is reconstructed through its closed factory.
Source, projects-parent, finance-project, and target-absence normalized-name
fingerprints must project to the exact corresponding Profile role selections;
a missing decoy cannot stand in for the approved target.

`PreMutationGate` re-observes the exact source, target parent, target absence,
reparse, Git, ACL, and volume evidence. Its receipt binds the accepted topology
fingerprint, one exact operation, a fresh UUIDv4 nonce, a short half-open
validity interval, and one consumed attempt. Stale, replayed, retargeted,
different-nonce, target-appearance, replacement, or drift cases fail closed.
The gate is readiness evidence for a future separately approved operation; it
does not authorize or perform that operation.
The topology receipt is atomically claimed by at most one gate. Receipt and
gate trusted state is module-owned, so caller attribute mutation, copy,
serialization, direct allocation, or a separately constructed canonical
envelope cannot mint or reset the capability.

Both named receipts are closed views over the existing preflight receipt
family. The existing exact `profile`, `authorization`, and `policy` input roles
and receipt schemas are not widened. Prior topology, nonce, and repeated
evidence are bound into canonical observation fingerprints rather than raw
receipt fields.

## HostBaseline and final-audit composition

`RealHostBaselineCollector` obtains source-root, projects-parent,
finance-project, volume, operator-SID, and role-specific ACL evidence through
separate narrow callbacks. Parent and finance observations cannot substitute
for each other. Only opaque fingerprints, exact bounded counts, completeness,
and `content_observed=false` enter a deterministic aggregate projection through
`backend.real_host_preflight.baseline_bridge` to the existing repr-redacted
`HostBaseline`. The bridge cannot review, create, publish, verify, open, or
delete a migration-evidence package.

`backend.real_host_preflight.audit_bridge` binds exactly the existing seven
read-only callbacks to the unchanged final nine-zone `ContainerAudit`. The
audit core gains no Windows, filesystem, ACL, Git, SQLite, or composition
import. `FinalAuditCompositionReadyReceiptV1` proves only that the exact policy
and callbacks can be composed. It must not invoke the audit against the current
pre-cutover layout, return an audit-pass result, or claim that the final layout
exists or passed. Callback bindings are revalidated at prepare and readiness,
and the seven composed adapters must remain identical to their captured
readers.

The third bridge, `contracts_bridge.py`, has an exact imported-symbol allowlist
and may only validate the locked Profile/authorization values, construct the
closed preflight receipt family, and reuse fixed operator result values. It
does not create, issue, mint, sign, renew, or store real-host authorization.

## Read-only capability denial

The Issue #53 composition has no service-control, ACL-apply, rename, move,
replace, delete, repository/worktree mutation, Git network/mutation,
Runtime-build, database-copy/checkpoint, artifact, Config, browser, HTTP,
provider, mailbox, vault, credential, private-store/private-data, evidence
publication, migration, cutover, resume, rollback, recovery, cleanup, or
scheduler capability. It reads no file/database/private content and exposes no
arbitrary command, path, callback, adapter, environment, or error-detail
surface through the operator entry.

Public receipts, fixed results, `repr`, stdout, stderr, and logs remain
content-free. They may contain only closed status/detail values, opaque
fingerprints, bounded validity, and allowlisted aggregate counts. Raw path,
SID, SDDL, account, Git name/ref, file ID, command, content, and native/callback
exception values must be rejected or discarded before the public boundary.

## Issue #54 reviewed evidence publication and verification

Review consumes only the exact `CutoverProfileV1` dirty-source, local-ref,
worktree, package-target, Git, and `RealHostBaseline` selections. It accepts no
arbitrary replacement path, ref, object, worktree, target, callback, or host
value. `MigrationEvidenceReviewReceiptV1` binds the operation, Profile,
governing master, review, selection, Git, host, and allowlisted counts through
closed content-free fingerprints. The complete `MigrationEvidenceReview`
remains in memory and must not be serialized or persisted as alternate
authority. The test-only synthetic binder links the fixed sandbox marker into
the package-target parent and requires the two names to retain one
regular-file identity. Removing or replacing the parent destroys that anchor,
so recycled directory identity cannot satisfy the later selection claim.

Create runs only in the physically separate create-only publication
composition. It requires an exact `EvidencePublicationAuthorizationV1`, the
same operation, Profile and governing master, the exact review receipt and
in-memory review, and the exact confirmed review fingerprint. Before
publication it repeats complete live discovery, including a fresh
`HostBaseline`. Profile, selection, dirty-source, ref, worktree, Git, host,
target, review, receipt, authorization, or confirmation drift fails closed.
`MigrationEvidenceCreatedReceiptV1` binds review, package, manifest, package
identity, and aggregate-count fingerprints. Publication remains absent-target,
no-clobber, and create-only.

Verification runs in a separate read-only process. It reads the published
package once through a bounded descriptor, calls the independent verifier on
those exact bytes, then requires an identical target reread and independently
recomputes the package and manifest hashes. The creator may use shared pure
package-format validation but cannot import, construct, or call the independent verifier
process or capability. The verifier cannot import publication or create-only
capabilities and cannot write, replace, rename, remove, unlink, or otherwise
modify a package.

`MigrationEvidenceReviewReceiptV1`, `MigrationEvidenceCreatedReceiptV1`, and
the verified receipt must agree on the same operation, Profile, governing
master, review fingerprint, applicable package and manifest hashes, package
identity, and allowlisted counts before forming
`MigrationEvidenceReceiptSetV1`. The receipt set is evidence for a later
pre-mutation gate. It does not authorize preflight, publication, migration,
mutation, cutover, rollback, or recovery.

Before Issue #39, all real Issue #54 entries reject missing, wrong-phase, and
`TestSandboxAuthorizationV1` inputs and remain fixed locked even when a
structurally valid real authorization is supplied. Package creation and
verification tests run only below test-owned temporary synthetic sandboxes.
Receipts, results, `repr`, stdout, stderr, and logs may expose only closed
statuses, opaque SHA-256 fingerprints, and bounded counts, never paths, ref
names, object IDs, worktree names, commands, content, native errors, or
exception text.

No real package, host preflight, service stop, repository/worktree move, ACL
apply, Runtime build, database copy, provider call, mailbox access, vault
access, private-store access, or private-data read is authorized by Issue #54.
A Migration Evidence Package is evidence, not a backup, Runtime artifact,
private-data container, or authorization to migrate.

## Synthetic crash-safe journal boundary

`JournalOperationBindingV1` reparses the exact Profile and validates one
externally supplied execute authorization plus the exact rollback-phase
`RecoveryAuthorizationV1` before mutation. It binds master, operation, profile,
operator, both authorization fingerprints, and one opaque exclusive owner.
Each ownership claim receives a distinct in-memory lease so a stale store
cannot act for or release a recovered owner. Neither package creates or renews
real-host authority.

`JournalRecordV1` is bounded strict canonical UTF-8 JSON. Exact sequence,
previous-record hash, record hash, fixed synthetic step/direction/event, all
operation bindings, before/expected/observed fingerprints, and outcome are
verified before append. Candidate transition validation occurs before pending
write. Forward and reverse actions use durable `INTENT`, exact
`EFFECT_OBSERVED`, and `COMMITTED`; reverse steps are derived LIFO only from
verified `COMMITTED/APPLIED` forward records. The store round-trip-validates the
record immediately before any write and issues a non-copyable/non-serializable
permit backed by one shared single-use issuance for the current owner lease,
exact active durable intent, and exact durable journal head. The synthetic
effect must consume it through one atomic store-private token claim; the
synthetic medium operation gate serializes append, restart, permit mint/claim,
and effect mutation. Before a new record or permit can advance from a
namespace-published head, the exact current head receives its missing stable
reread and the full snapshot is reverified. A head advance, pending record, or
durable observed fact invalidates an older permit.

`SyntheticJournalMediumV1` is an exact in-memory model. Windows and Linux values
record pending-file, published-file and namespace barrier codes plus stable
reread, but no filesystem API exists. Pending, truncated, corrupt, or
unbarriered state returns no action authority. A create-only exact lost-ack retry
cannot duplicate or replace a record. Lost acknowledgement after namespace
publication of `INTENT`, `RESUME_BOUND`, `EFFECT_OBSERVED`, or `COMMITTED`
therefore completes that exact head's stable reread before any continuation.

`inspect_restart(...)` accepts immutable snapshots rather than a medium/store.
It claims no owner, appends nothing, and never invokes forward/reverse effect.
An explicit resume independently revalidates an unexpired exact phase-`resume`
authorization and fresh observation. Exact pre-action may run once; exact
expected-post may only complete facts. A durable observed fact is authoritative
and cannot be replayed or have `NOT_APPLIED` changed to `APPLIED`; a newly valid
resume authority appends a fresh `RESUME_BOUND` without discarding prior facts.
Pending direction, exact Profile/master/operator binding, identity mapping,
fixed transition mapping, and post-effect re-observation are checked before
journal completion. Explicit rollback independently
revalidates the exact pre-bound recovery authority, reconciles exact partial
facts, and invokes only derived reverse steps. Unknown state, broken identity,
corruption, replacement/expired authority, or ambiguity is `INCIDENT_STOP`.

Public inspection exposes only fixed status, phase, receipt fingerprint, and
allowlisted counts. It never returns record bytes, observation values, path,
command, exception, host identity, or free text. `SAFE_ABORT`,
`ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and `CUTOVER_SUCCEEDED` are distinct.
There is no real filesystem/service/ACL/Git/worktree/Runtime/SQLite/provider/
mailbox/vault/private-data capability or production consumer.

## Issue #55 fixed-role ACL and no-clobber guard

`backend.cutover_host_mutation` publicly exports only closed portable
contracts. Its internal Windows adapter has exactly four operations: fixed-role
capture, exact compare, new-Container policy apply, and fixed-zone inheritance
verification. Source compatibility rejects protected or unexpected existing
descriptors without applying an ACL. Parent and finance never own apply
capability.

Container creation atomically installs a code-fixed protected construction
DACL with one non-inheritable operator ACE. It grants list/read-control/
write-DAC/synchronize only and grants no add-file, add-subdirectory, or
delete-child right. The claim holds root, marker, parent, and target handles
until the journaled final ACL effect. ACL application consumes that one guarded
claim, proves the Container empty, and replaces the guard through the held
target handle. The update information is exactly DACL plus protected DACL;
owner, group, and SACL pointers are null. The current operator SID exists only
in module-owned memory and is public only as a fingerprint. No ACL command,
shell, PowerShell, `icacls`, or replayable transcript can be generated.

Create-only directory, file publication, and same-identity move effects require
an exact durable journal INTENT permit. Directory creation uses `NtCreateFile`
relative to the approved parent handle with `FILE_CREATE`. Opened handles bind
root, marker, source, target parent, fixed NTFS volume, 128-bit file ID,
normalized target, and reparse-free state. Publication sets no-replace and verifies source absence, target
presence, and identical file ID after the effect. Existing targets and drift
fail without repair, deletion, replacement, or alternate selection.

All native effects run only in caller-owned temporary NTFS sandboxes under
exact `TestSandboxAuthorizationV1`. The real constructor rejects that test
authorization and remains `BLOCKED_NO_APPROVED_COMMAND` even for a valid
`CutoverExecutionAuthorizationV1` before Issue #39. No production consumer,
CLI, workflow, service, repository/worktree, Runtime, SQLite, provider,
mailbox, vault, private-store, or private-data capability exists.

## Executable capability guards

`tests/test_cutover_contract_architecture.py` pins all of the following:

- the exact package files and exact public `__all__` surface;
- absolute imports limited to exact pure standard-library modules and exact
  imported symbols, with relative imports limited to exact sibling package
  modules; parent-relative and dotted-module imports fail;
- absence of filesystem, process, SQLite, network, environment, dynamic-import,
  clock, random, host, and ambient-authority calls;
- recursive rejection of nested/non-source package payloads, forbidden builtin
  loads/aliases including `breakpoint`/`delattr`/`setattr`, dotted modules, and
  parent-relative imports;
- package-wide absence of real-authorization issuer or mint functions;
- the exact reviewed #52/#53/#54/#55/#56/#57 consumers as the only Issue #51
  consumers, plus only the exact #55 and #56 journal-effect bridges as journal
  consumers; every other Python/JavaScript file under
  `backend/`, `scripts/`, and `frontend/`, using AST checks for equivalent
  Python import forms,
  direct/attribute/imported/rebound dynamic-import call aliases, and fixed token
  checks for JavaScript;
- the Issue #54 creator/verifier dependency wall, separate verifier process,
  create-only versus read-only capabilities, and fixed content-free process
  response;
- the Issue #54 locked entries' rejection of missing, wrong-phase, and test
  authorization;
- the zero-argument, always-blocked default operator entry;
- the existing 300-line file and 50-line function bounds.

The exact guards must fail if a real/default adapter, issuer, composition root,
consumer, or additional package capability is introduced. Synthetic tests use
only fixed enums and opaque content-free fingerprints; they do not read or
invoke a real host.

## Issue #56 reversible mixed-topology transaction guard

Issue #56 composes only caller-owned synthetic Windows sandboxes. A bound scope
contains one marker identity, exact Profile/test authorization, opened Git
executable identity/version/content binding, original Repository
Root/common-directory identities, and
exactly eleven clean reviewed worktrees: eight embedded and three external.
No public API accepts a path, ref, object ID, administrative name, Git command,
or host adapter.

Original physical worktrees and their opaque Git administrative entries move
no-replace to same-volume preservation before any counterpart creation. The
original Repository Root becomes `main` only through identity-preserving
relocation. Container/zones/targets are create-only. Administrative bytes are
bounded-fingerprinted and relocated as opaque objects; the transaction never
edits them. Fixed Git recreation must reproduce the reviewed ref/commit/common
relationship, preserve the reserved target identity, add exactly one fresh
admin entry, and remain clean.
The fixed runner denies executable write sharing during every operation,
revalidates its exact executable identity and bounded full-content digest plus
sandbox identities before and after use, owns a bounded process tree,
suppresses repository hooks, rejects unsafe local configuration at scope
bind/rebind, and rejects any extra administrative namespace child.

Every mutation is preceded by a durably published content-free INTENT and
followed by the actual #55 or Git OBSERVED fact. COMMITTED is allowed only
after an independent reread matches OBSERVED exactly; filesystem rereads hold
the target against write/delete sharing, administrative rereads also bind
opaque content, and Git rereads repeat the exact reviewed state.
Explicit reverse appends
`ABORTED/NOT_APPLIED` only after exact before-effect observation, or appends
only missing OBSERVED/COMMITTED facts after exact after-effect observation;
it never replays the effect. Reverse accepts every complete forward boundary
and safely classified forward crash gap, preserves any published new failed
evidence, then restores all original identities. The actual Container-create
identity is journaled and must equal both the unchanged ContainerAudit trusted
policy selection and the forward/failed Container object. An explicitly
repeated reverse call derives the committed-stage plan, validates complete
journal-bound failed evidence before any resumed mutation, validates a safely
classified reverse checkpoint, and executes only the remaining fixed
mutations. Final Git verification rejects non-intentional reviewed local-ref or
remote-configuration drift. Final forward verification
reuses unchanged ContainerAudit filesystem/Git/embedded-worktree validators
without claiming a full host audit; external worktrees remain separately exact
Git-verified. Journal or state ambiguity stops as `INCIDENT_STOP`; no blind
replay, repair, cleanup, overwrite, background resume, or ambiguous resume
exists. The real
constructor remains locked
without an exact external execution authorization and, even with one, has no
approved command before Issue #39.

## Issue #57 managed publication guard

Issue #57 publishes only into one exact caller-owned synthetic Windows
sandbox. The scope snapshots immutable paths and binds held root/marker/
target-parent identities, exact Profile/test authorization, fixed roles,
reviewed inputs, and absent targets. Target creation is parent-handle-relative
`NtCreateFile(FILE_CREATE)`; target handles prevent replacement and file
writers through final verification. The phase can call only Runtime, database,
artifact, and Config adapters; it cannot stop or start a service, mutate a
repository/worktree or ACL, access a browser profile, or reach mailbox/
provider/credential/vault/private-data capabilities.

Runtime publication accepts only one approved Python 3.12.13 source, one
canonical lock enumerating the complete installed closure, and the exact
hash-locked offline wheelhouse. It captures each reviewed wheel through a
write/delete-blocking handle, after the harness materializes the approved
Python distribution inside the sandbox and scope rejects external source
paths. A canonical manifest binds every CPython source-tree entry, total
bytes, executable hash, and tree fingerprint. Publication rechecks reparse/
ADS state, holds every source entry against write/delete sharing, and watches
the source recursively from before execution through verification. Held-handle
size and remaining-aggregate gates precede source/wheel/lock reads. It installs
captured bytes rather than raced paths,
rejects interpreter startup hooks, and has the new Runtime verify itself under
fixed `-X frozen_modules=on -I -B -S`. The approved CPython distribution is streamed from held handles
into the empty create-only Runtime root and never executed from the mutable
source namespace. That baseline and every wheel/lock addition are held as one
exact tree: children are created by held-parent handles, reparse points and
alternate data streams are forbidden, and any extra/missing/changed entry
fails. The complete approved `Lib/encodings` package is streamed from held
source handles into bounded deterministic ZIP_STORED `managed-startup.zip`.
Code-fixed create-only `python312._pth` and `python._pth` sentinels put that
immutable archive before `Lib` and `DLLs`, omit `import site`, and remain held
before target execution, so transient pre-script encoding children and later
startup namespace entries cannot execute. Archive and
Runtime resource use has fixed member/count/size/ratio/
depth ceilings; central-directory gates precede `ZipFile`, enumeration gates
precede sorting, and extraction/hash are bounded and streaming. The new Runtime
verifier imports only built-in `sys`, `nt`, `_sha2`, and `_imp`, proves
`_imp.is_frozen("codecs")`, and blocks every later import. Thus transient
`Lib/codecs/__init__.py` cannot run before the hook. It hashes exact Python,
SQLite, startup-ZIP, lock, and import files and parses only
bounded expected distribution metadata; SQLite hashes are bound to the held
approved source entries and installed code never executes. A recursive child-change
guard watches the Runtime parent from sealing through receipt construction,
so transient child/root-stream mutation cannot execute installed code or
yield a receipt. Runtime stdout is consumed incrementally and overflow
terminates the child at the fixed cap. The fingerprinted receipt set
revalidates all four complete
typed mappings and their common chain. Database
publication requires the exact stopped-service receipt,
denies source write/delete sharing throughout, checks WAL/SHM/rollback journal
absence before copy and again after final target verification, and never
checkpoints, removes a sidecar, mutates the source, or inspects application
rows. CRX publication keeps both source and target held through receipt
construction and a final exact reread. It is exact copy-only; Config is
deterministic, non-secret, and closed-schema. Unsafe Windows target components,
including alternate-stream syntax and superscript `COM¹/²/³` or `LPT¹/²/³`
reserved-device aliases, fail before native creation. All targets are
create-only, failures retain partial state, and all public evidence is
content-free.

Missing or test authorization is rejected by every real constructor. Exact
real execution authorization still yields `BLOCKED_NO_APPROVED_COMMAND`
before Issue #39. Synthetic success is evidence only and grants no real-host,
Issues #58/#59, #38/#39, merge, or parent-Spec authority.

## Issue #58 provider-disabled lifecycle guard

Issue #58 composes only exact injected new-service and legacy-service role
adapters inside a caller-owned synthetic sandbox. A new-service start accepts
the verified Issue #57 managed Runtime and deterministic Config receipts,
sets both providers to `disabled`, rejects legacy-environment inheritance, and
binds a fresh UUIDv4 nonce. Health must match the exact PID, start time,
executable, port owner, Profile, `LocalData` role, nonce, and provider-disabled
state. Activation submits one code-fixed synthetic request, accepts only a
deterministic-rules result with zero provider attempts, and proves exactly one
matching synthetic row in the new `LocalData`.

Known pre-mutation start rejection returns `SAFE_ABORT` without containment or
rollback. Known post-mutation validation failures return `ROLLBACK_REQUIRED`. Identity,
journal, reparse, provider-boundary, or safety ambiguity returns
`INCIDENT_STOP` after exact containment. Rollback accepts only an explicit
test sandbox authorization and a complete committed-journal binding, executes
the fixed reverse stages, retains the failed Container, new external
worktrees, and Git administrative evidence, and proves exact restoration of
the original main plus all eleven reviewed worktrees. Legacy recovery uses
one dedicated injected provider-disabled Config and a distinct fresh UUIDv4
nonce, never reads an environment file, and never writes a synthetic analysis
to the legacy database. Any legacy recovery failure is the fixed
`INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED`; no alternate launcher,
configuration, retry, cleanup, or repair exists.

All public results, receipts, journal bindings, stdout, stderr, and errors are
content-free. Real lifecycle construction remains locked without both exact
`CutoverExecutionAuthorizationV1` and `RecoveryAuthorizationV1` values and
still returns `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. Synthetic
success grants no real service, repository/worktree, ACL, Runtime, SQLite,
browser, mailbox, provider, credential, vault, private-data, Issue #59,
Issue #38/#39, merge, or parent-Spec authority.

## Issue #59 three-root composition guard

Issue #59 adds only four pure/operator packages:
`backend.cutover_composition_contracts`,
`backend.real_host_preflight_composition`,
`backend.migration_evidence_publication_composition`, and
`backend.cutover_transaction_composition`. The three operator roots are
physically separate and mutually non-importing. Their exact frozen role bundles
are bound to one `CompositionBindingV1`; normal runtime, browser, scripts,
cleanup, scheduler, workflow, mailbox, provider, vault, private-data, and
unrelated adapter packages cannot import them.

Every public real constructor and command entry validates the exact nominal
phase authorization. Synthetic/test authorization is always rejected. Exact
real authorization still returns `BLOCKED_NO_APPROVED_COMMAND`, with zero
executions and no constructed role bundle, until Issue #39 supplies a
separately reviewed command. Backend packages expose no executable test
binder. Test-only assembly requires the complete synthetic authorization
sequence and an internally created temporary scope with no caller-selected
root. That scope owns each component `TemporaryDirectory`, and every role and
journal callback rechecks scope liveness before calling the component; it has
no route into a real entry.

`ProjectContainerReceiptChainV1` accepts only the exact ordered stage set and
same operation/Profile/governing-master/operator/authorization-sequence
binding. It also binds review, package verification, ACL baseline, expiring
pre-mutation receipt, one journal owner, linked prior/current heads, terminal
receipt, activation, final audit, failed
Container preservation, rollback restoration, legacy health, and terminal
recovery state. Each stage rejects a wrong predecessor, binding, role, owner,
head link, freshness interval, count, or unapproved dynamic field. Every
partial chain is an exact approved prefix, and the chain fingerprint commits
its ordered stages and recursively linked terminal receipt. Execute, resume,
and rollback are single-action; the journal owner also atomically claims the
fresh gate across composition instances and supplies the clock used to
revalidate authorization before every role boundary. Resume accepts only an
exact journal-derived continuation, and recovery can branch only after
activation or final audit.

Receipts, chains, fixed errors, stdout, stderr, and logs expose only closed
statuses, fingerprints, timestamps, and allowlisted counts. They reject raw
paths, SID/SDDL, Git names/IDs, worktree/admin names, commands, exceptions,
credentials, mailbox/provider/vault/private content, database rows, and
dynamic fields.

The Windows E2E test composes the existing #53-#58 implementations only in
caller-owned temporary sandboxes. Its ACL-through-activation forward path
passes through the transaction root, the fixed final audit rejects the known
failed activation, and rollback consumes only the reconstructed committed
journal prefix. The #55 ACL policy receipt is carried into the #56 Profile,
the actual #56 forward receipt supplies journal state, and #58 consumes the
exact #57 four-receipt set and database-receipt data role without a substitute
publication receipt. It proves recovery while all providers remain disabled; it
does not run a real preflight,
evidence package, ACL change, repository/worktree move, Runtime build,
database/CRX/Config publication, service operation, activation, or rollback.
Linux and portable tests make no NTFS, Windows ACL, native durability, or
service-control claim.

Issue #38 remains open and R1 remains `NOT EXECUTABLE`; Issue #39 remains
unstarted. The final master produced by merging Issue #59 will invalidate the
old R1 SHA. All fourteen #38 approval items must be re-reviewed against that
exact final master and a new R2 published before any #39 authorization can be
considered.

## Issue #70 additive R2 contract vocabulary

Issue #70 adds only canonical, pathless values beside the Issue #59 contracts.
`ApprovedCutoverBindingV1` is derived from one exact `CutoverProfileV1` and one
exact `AuthorizationSequenceV1`; it binds the operation, Profile, governing
master, operator, authorization sequence and expiry, legacy-source-anchor and
managed-main identities, policy-derived inherited-DACL projection, repository
manifest, eleven-worktree topology, and the four managed units by opaque
fingerprints. It has no caller-selected path, discovery, override, or fallback
surface. Canonical JSON parsing rejects duplicate or unknown fields and any
value that differs from the reviewed Profile-derived body.

`AuthorizationDomain` keeps preflight, evidence, execution, and recovery
nominally distinct and maps only the fixed approved phases. A receipt, mapping,
test value, or unknown phase cannot become authorization. The R2 journal
vocabulary names quiescence, anchor/main/whole-tree ACL and repository
boundaries; independent Runtime, database, CRX, and Config PREPARE/PUBLISH
boundaries; the two-start lifecycle and independent audits; exact pending-effect
tri-state; preservation and reverse boundaries; and the only final success,
legacy-restoration, or incident outcomes. There is no batched
managed-publication stage.

`R2CutoverReceiptV1` is immutable, content-free evidence bound to the approved
binding and exactly one journal boundary/fact. Its canonical mapping contains
only enums, opaque fingerprints, and allowlisted counts. Pending classification
accepts only `EFFECT_ABSENT_EXACT`, `EFFECT_PRESENT_EXACT`, or
`EFFECT_AMBIGUOUS`; terminal outcomes are accepted only at their exact terminal
boundary. The receipt has no inheritance or conversion path to any authorization
type. Issue #70 adds no executable behavior: all Issue #59 entries and
constructors retain their existing pre-#39 `BLOCKED_NO_APPROVED_COMMAND` result.

## Issues #71-#73 dormant process security disposition

The six preflight, one evidence, and three transaction verbs remain closed
catalog values in three physically separate packages. No root accepts an option
parser, umbrella selector, arbitrary process/Git command, caller path, Profile,
journal path, recovery target, force switch, environment authorization, file
authorization, key, signature, envelope, issuer, or free-form payload.

Issue #110 replaces the historical R2 authorization ingress with pure V3 and
execution-confirmation contracts and keeps those primitives outside the
production graph. Each production root returns
`DORMANT_NO_ISSUE39_APPROVAL` before console inspection, acknowledgement,
candidate, confirmation, Adapter, journal, callback, or host access. Redirected
or real consoles cannot alter that ordering; synthetic tests cannot unlock it.

The process packages import no provider, mailbox, vault, credential, private
store/data, cleanup, deletion, overwrite, repair, or cross-root capability.
Windows tests may prove fresh-console dormancy and pure TTY fact validation but
make no authorization, publication, transaction, journal-mutation, or real-host
claim. Issue #39 does not allow these roots to consume an execution
confirmation; only the fixed orchestrator graph may do so, and its real-host
execution authority remains a separate fresh decision.

## Issue #39 governed code allowlist

The approved Issue #39 code allowlist permits only the fixed `backend.r2_issue39_orchestrator` composition root, `scripts/execute_project_container_cutover.py`, and its package-owned retained restart runner.

The fixed code path is reviewable and mergeable without becoming execution
authority. The retained historical roots remain dormant, and the orchestrator
must still pass exact closure/master/Issue 38/input/roster readiness plus fresh
real-console, incident, action, recovery, and terminal confirmations before any
corresponding effect. Tests, CI, merge, and closure evidence cannot substitute
for the later explicit real-host authorization.

The initial process is accepted only from the code-fixed registered launcher
worktree. Its script root and current directory must be the same plain
original/resolved directory, and the script must be an ordinary single-link
non-reparse file; the legacy root, alternate worktrees, copied scripts and
aliases stop before orchestrator import. This initial launcher transfers to the
separately protected evidence runner before the first catalog effect.

Incident disposition recognizes only the exact retained leaf
`.r2-solo-maintainer-closure-v1.incident-794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721`
under the fixed Git-common source parent or fixed incident-archive parent. The
obsolete `.stage-794aea72...` name is rejected rather than retained as an
alternate binding. Artifact lengths/hashes, protected DACL, fixed-volume,
reparse rejection, destination absence, no-replace move, and zero deletion
remain mandatory.

The fixed incident archive parent is exactly
`D:\IncidentArchives\email_ai_assistant\issue38`. Zero-readiness binds its
`PROVISIONABLE`, `READY`, or `BLOCKED` state, component presence, and opened
identities into the separate incident confirmation. After confirmation,
disposition must reproduce the exact fingerprint before create and keep the
validated/created chain held and placement-revalidated through rename and
artifact reread. The parameterless provisioner creates only the three exact
missing components relative to held parents with native `FILE_CREATE`, no replace, fixed-drive NTFS,
non-reparse exact placement, and an at-create protected DACL. That DACL contains
exactly inheritable Full Control ACEs for the current token SID, LocalSystem,
and built-in Administrators. Existing drift, post-confirmation competition,
parent replacement, and collisions fail before the source move; partial state
is retained without repair or cleanup, and the `D:\` DACL is never changed. No
public or caller-selected path, component, policy, or alternate archive root
exists.

Every Issue 39 V3 confirmation is preceded by one strict content-free
`ISSUE39_CONFIRMATION_CONTEXT_V1` line derived only from closed bound values.
It exposes no path or caller text and is informational, never authority. The
operator enters only the following candidate fingerprint and fixed
acknowledgement; any context/display failure stops before input or effect.

Issue 39 repository preparation binds the raw relocation bytes independently
from the regular stage-zero index blob identity. Raw byte size and SHA-256 are
preserved in the manifest; the index OID is accepted only by direct raw blob
equality or one code-owned CRLF-to-LF projection with at least one CRLF, no NUL,
no remaining bare CR, and exact projected OID equality. Projection requires an
include-free exact true repository/worktree mode, or the fixed Git system true
mode when no override exists. Filter-free HEAD-tree/
index equality, ordinary index flags, the empty untracked set, the complete
index payload, and include-free config/source-absence evidence are observed
before and after review. Tracked `.gitattributes`, fixed
`.git/info/attributes`, and effective repository/system `core.attributesFile`
are rejected; `check-attr`, arbitrary filter execution, encoding, attribute-file
reads, caller normalization/path selection, hidden index flags, true content
drift, and non-clean or unstable state fail closed before evidence publication.

## Issue #74 create-only main and whole-tree DACL proof

The representative R2 tracer renames the fixed synthetic flat root to
`LegacySourceAnchorV1`, creates `ManagedMainRootV1` without replacement under
the already protected Container, and moves only the fixed selected directory,
descendant/file hierarchy, standalone file, and repository-like hierarchy by
same-volume handle-relative rename. A double-identical pre-move observation is
valid for at most 20 synthetic seconds and is consumed exactly once. It is
readiness evidence only and can never provide the post-move expected values.

`ExpectedInheritedDaclProjectionV1` is derived from create-only objects that
actually inherit the approved Container DACL. A scan immediately after the
same-volume moves must detect their preserved old descriptors. The tracer then
sets only the projection-bound DACL on every main-tree object and performs a
new authoritative reparse-free scan. Native object identity, Owner, and Group
must remain byte-derived fingerprint equal; the native call exposes no
system-audit ACL mutation flag or pointer.

Only after every root and selected descendant matches the projection can a
closed, content-free `PostMoveMainAclConformanceReceiptV1` be bound to the
current journal head and committed as `MAIN_PUBLISHED`. Intent, effect, scan,
observation, and commit gaps are independently injected at every fixed
boundary. Exact recognized partials require rollback; ambiguity stops as an
incident. Rollback uses only fixed no-replace moves and DACL restoration,
preserves the failed main, and restores the original anchor and every selected
identity/security observation without copy, overwrite, delete, cleanup, or
reparse traversal.

## Issue #75 complete repository manifest and worktree topology

`RepositoryContentManifestV1` is a closed content-free review of `.git`,
tracked content, and individually approved untracked content. It cannot select
ignored data or any private, Runtime, database, log, cache, reparse, linked-
worktree, or opaque-admin residue. Every selected leaf and whole directory has
a stable native identity and path fingerprint; every residue leaf is separately
identity-bound under `LegacySourceAnchorV1`. A whole directory is eligible only
when its complete subtree is selected and ACL-compatible. Otherwise the new
main receives only a create-only skeleton plus exact leaf moves.

Before repository relocation, exactly eleven original linked-worktree physical
identities and their opaque administrative identities/content fingerprints are
moved into fixed preservation roles. The fresh protected Container and main
receive only the manifest; all excluded residue remains under the original
legacy anchor. Exactly eight reconstructed worktrees are siblings under
Container `Worktrees` and three use reviewed external targets; all eleven are
outside Repository Root and bind the reviewed refs and commits through the
fixed #56 runner.

Rollback never invokes a removal command. It first preserves the failed
Container, new admin directories, and external worktrees, then reverses fixed
manifest moves, restores the original anchor, reattaches all original physical
and admin identities, restores their DACL observations, and independently
verifies the twelve-entry Git worktree relationship. Its only success status is
`LEGACY_FLAT_LAYOUT_RESTORED`; collision or ambiguous identity cannot be
overwritten or cleaned.

## Issue #76 quiescence and leased database publication

The database slice accepts three distinct content-free prerequisites for the
completed preflight, evidence publication, and fresh pre-mutation gate. It
durably records quiescence intent before the synthetic service-controller role
performs the first mutation. Only that module-owned role can issue an accepted
`StoppedServiceReceiptV1`; the receipt has no public constructor, parser, or
factory and is checked against the in-process issuer registry.

`LegacyDatabaseCopyLeaseV1` is likewise module-owned and single-use. Its
Windows `CreateFileW` handle requests only read sharing, thereby denying write
and delete sharing, and that same handle supplies both the copy bytes and the
post-publish verification bytes. `POST_STOP_BASELINE`, `PRE_COPY_LEASE`,
`COPY_POSTVERIFY`, and `FINAL_OR_RECOVERY_VERIFY` all reject any fixed SQLite
sidecar without checkpointing, truncating, deleting, cleaning, or otherwise
mutating the source.

Database prepare and publish are separate create-only durable journal
boundaries with intent, effect-observed, stable-verified, and committed facts.
Collision, source drift, crash, and partial staging remain in the caller-owned
synthetic sandbox. Recovery classifies them without cleanup, restores an exact
published target back to its retained staging role when safe, and returns
`INCIDENT_STOP` for ambiguity.

## Issue #77 independent Runtime unit

Runtime publication starts only after the quiescence receipt fingerprint. Its
fixed staging identity is `managed-runtime.prepare` beside the fixed final
`managed-runtime`; one durable PREPARE intent precedes create-only staging and
one durable PUBLISH intent precedes the no-replace same-volume rename. Both
boundaries record effect, stable verification, and commit facts separately.

The existing canonical dependency lock remains the sole dependency authority.
It proves Python 3.12.13, SQLite 3.50.4, the complete fixed dependency closure,
wheel hashes, import-file hashes, and exact isolated startup archive. The new
Runtime performs the existing isolated self-verifier, which imports only frozen
Python helpers and reads package metadata/import bytes; it never imports or
executes installed package code. No stale R1 `pip check` statement is an
authority source.

Input capture, construction, and verification are offline and create-only.
Network, package indexes, caches, system Python, user site, legacy environment,
live resolution, replacement, retry, cleanup, and second-generation staging
are unavailable. Exact or partial staging is retained after crashes, collision,
drift, reparse, or verification failure; recovery classifies it content-free
and never deletes it.

## Issue #78 independent reviewed-CRX unit

The fixed reviewed CRX source is bound by native identity, CRX2/CRX3 format,
size, and SHA-256 before a transaction exists. A read-only-sharing source
handle denies write and delete sharing from pre-PREPARE review through the
final target verification. PREPARE creates and flushes only the fixed
`.crx.prepare` stage; PUBLISH performs only a same-parent no-replace rename,
then opens the final target with the same write/delete denial through repeated
identity, bytes, size, format, and hash verification.

CRX PREPARE and PUBLISH each carry separate durable intent, effect-observed,
stable-verified, and committed facts. Collision, target race, blocked source
replacement, reparse target, hash/size drift, partial staging, crash, and
blocked final-verification write remain retained and content-free. Recovery
uses only `EFFECT_ABSENT_EXACT`, `EFFECT_PRESENT_EXACT`, or
`EFFECT_AMBIGUOUS`; it can move an exact target back to retained staging but
cannot overwrite or clean an ambiguous object.

The unit has no CRX build, signing, installation, extension loading, browser
profile, signing-material, alternate-source, overwrite, deletion, or cleanup
capability. Any pending staging blocks a fresh generation. Tests use only
synthetic CRX bytes in a fresh test-owned NTFS sandbox.

## Issue #79 independent loader-compatible Config unit

`ManagedConfigSelectionV1` accepts exactly the two approved non-secret keys:
sorted unique internal domains and a fixed log-level enum. It rejects string or
canonical-JSON input, pair lists (including duplicate-key representations),
unknown keys, provider/secret/private fields, and malformed values. Its only
document is deterministic UTF-8 without BOM, with the two keys in fixed order,
one `=` per line, LF endings, and a final LF.

Config PREPARE and PUBLISH each record durable intent, effect observation,
stable verification, and commit. The fixed `.prepare` file is create-only and
flushed; PUBLISH is a same-parent no-replace rename. A read-only-sharing final
target handle remains live while the existing Managed loader reads the exact
bytes and `build_managed_container_config` independently reconstructs the
expected provider-disabled configuration. Hostile ambient provider/private
environment values have no effect.

Collision, partial stage, blocked target replacement, BOM/encoding drift, CRLF
drift, loader mismatch, crash, and pending staging retain their objects and
fail closed. Recovery is tri-state and may reverse only an exact target to
fixed staging. There is no overwrite, deletion, cleanup, retry, hidden input,
legacy Config, registry, clipboard, credential store, or second generation.
Receipts contain only fingerprints, status, counts, and booleans, never Config
values.

## Issue #80 independent stopped-layout and final-running audits

The stopped-layout and final-running-health audits are two distinct fresh
OS-process invocations, separate from the mutation process and from each other.
Each receives exactly one pre-bound `IndependentAuditAttestationSinkV1`; the
sink is exact-type, single-use, non-resettable, and can append only one fixed,
content-free journal attestation. It has no path selection or filesystem,
journal-selection, replacement, deletion, cleanup, provider, mailbox, vault,
or private-data capability.

Each sink is bound to one operation, approved binding, current journal head,
approved identity set, applicable health evidence, audit kind, process
identity, and observation epoch. Success independently rechecks all bindings
and appends within the fixed 300-second window. Deterministic head, identity,
or health mismatch returns `ROLLBACK_REQUIRED`; ambiguity, kind/sink swap,
append failure, or replay returns `INCIDENT_STOP`; expiry consumes the sink and
requires a completely fresh process and sink. The two nominal receipt types
cannot be directly constructed or serialized and expose only redacted,
content-free evidence.

## Issue #81 two-start provider-disabled validation lifecycle

The approved validation slice exact-types and binds the published evidence,
repository topology, Runtime, CRX, Config, and database results before any
service callback is available. Start A and Start B use distinct UUIDv4 nonces,
process identity and start time while matching the exact Runtime, Config,
Profile, port, database role, and disabled primary/fallback provider identities.

Start A proves health, performs exactly one fixed public synthetic analysis
whose `analysis_engine.source` is `rule_fallback`, records zero provider
attempts, binds one operator confirmation to that exact result, and observes
exactly one matching database row from one write. It then stops the exact Start
A process and requires `FINAL_OR_RECOVERY_VERIFY` with zero sidecars before the
independent stopped-layout audit. Start B proves health without analysis or
write and is followed by the independent final-running audit. Each audit
completion binds the applicable service nonce/process, journal head, approved
identities, health evidence, fresh 300-second window, and a distinct audit PID.

Every boundary has closed crash, deterministic-failure, and ambiguous-failure
classification. Crash and deterministic mismatch require rollback; ambiguous
types, process reuse, stale attestations, and adapter exceptions incident-stop.
The slice is single-use, dormant, synthetic-only, and adds no real entry.

## Issue #82 cross-stage recovery and final success seal

Restart inspection performs exactly two independent content-free observations
for every pending or committed boundary state. Only two identical ABSENT reads
produce `EFFECT_ABSENT_EXACT`; only two identical PRESENT reads produce
`EFFECT_PRESENT_EXACT`; drift or explicit ambiguity produces
`EFFECT_AMBIGUOUS`. Inspection is read-only and cannot call reverse authority,
repeat an effect, or append a success record. Durable committed facts must
agree with PRESENT host observation before recovery.

Recovery first preserves the failed Container, retains all new/partial objects,
then restores the Repository Root, Git, eleven worktrees, ACL, database, and
legacy service in one fixed order. Every non-observed reverse effect requires a
fresh exact authority binding the current journal head, current remaining-plan
fingerprint, boundary, unexpired interval, and never-reused crash nonce. An
already observed exact reverse effect is skipped, never blindly repeated.
There is no cleanup. The only completed reverse status is
`LEGACY_FLAT_LAYOUT_RESTORED`; ambiguity, head drift, receipt-chain drift, stale
authority, replay, or failed legacy recovery incident-stops.

Final seal requires no pending intent or remaining reverse step. It binds the
validated #81 result, both independent audit completions, current head, nonce
B, approved identity set, audit-specific identity bindings, distinct audit
processes, and exact 300-second windows. One minimal freshness observation is
followed only by one `CUTOVER_SUCCESS` journal append. No host mutation or
second invocation is permitted.

## Issue #83 full R2 synthetic verification and obsolete-path contraction

The only R2 verification entry is the fixed, no-argument
`scripts/verify_r2_synthetic_topology.py`. It owns one fresh physical NTFS
sandbox and reports only fixed status, deterministic fingerprints, and
allowlisted aggregate counts. It cannot accept a root, path, Profile, journal,
target, command, force, retry, cleanup, provider, mailbox, vault, private-data,
or real authorization input.

The Windows run proves the complete preflight-through-final-seal topology in
that one sandbox: three distinct TTY process types, four distinct authorization
domains, nine Project Container zones, one repository with exactly eleven
reviewed worktrees, four independent managed units, Start A with one
`rule_fallback` result and one row, stopped audit, Start B with no analysis or
write, final-running audit, and one terminal `CUTOVER_SUCCESS`. The fixed
seven-semantics by two-directions by five-gaps matrix executes 70 distinct
fresh subscopes. Portable tests validate only contracts and fingerprints and
make no NTFS, ACL, TTY, or process-isolation claim.

Architecture guards make obsolete batched managed publication, stale R1
verification, an in-process operator substitute, self-certified audit, and a
legacy R2 success path unreachable. The accepted prototype fingerprint remains
non-authorizing feasibility prior art only. Fresh criteria, matrix, script,
bundle, complete R2 surface, and package fingerprints are required for this
evidence and authorize neither Issue #39 nor any real-host operation.

## Security review checklist

- [ ] Values remain pathless, immutable, repr-redacted, and content-free.
- [ ] Profile, authorization, and receipt schemas remain exact and closed.
- [ ] Real authorization is externally supplied and exact-type validated.
- [ ] Receipt parsing or status cannot satisfy authorization validation.
- [ ] The package has no issuer, clock, secret, adapter, I/O, or mutation
  capability.
- [ ] `default_operator_entry()` remains fixed blocked.
- [ ] The #53 operator entry remains zero-capability, fixed blocked, and cannot
  accept test authorization.
- [ ] Windows behavior is limited to an exact test-owned temporary sandbox;
  Linux evidence remains portable-contract-only.
- [ ] Current topology uses two complete identical observations, and the
  pre-mutation gate is fresh, nonce-bound, operation-bound, short-lived, and
  single-use.
- [ ] Source, parent, finance, volume, operator-SID, and ACL evidence remain
  separate and content-free before canonical `HostBaseline` projection.
- [ ] Final-audit readiness binds the unchanged nine-zone policy and exact seven
  callbacks without invoking the audit or claiming a final-layout pass.
- [ ] Evidence review consumes only exact Profile-bound selections and keeps
  the complete review in memory.
- [ ] Evidence create requires the exact publication authorization and confirmed
  review fingerprint, then repeats complete discovery and host collection.
- [ ] Creator and verifier capabilities remain isolated; verification is a
  separate read-only process with no publication or mutation capability.
- [ ] Review, created, and verified receipts agree on exact bindings, hashes,
  identity, and counts without becoming authorization.
- [ ] Issue #54 real entries remain locked before Issue #39, and package tests
  remain temporary, synthetic, and content-free.
- [ ] No production operator command or real-host operation has been added.
- [ ] No forbidden mutation, service, runtime/data publication, provider,
  mailbox, vault, private-data, or cleanup capability has been added.
- [ ] Pending/unbarriered records never authorize a synthetic effect.
- [ ] Restart inspection is read-only and expected-post is never blindly retried.
- [ ] Reverse steps are pre-bound-authority, journal-derived, and LIFO.
