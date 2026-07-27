---
last_update: 2026-07-27
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# Project Container cutover contract security boundary

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
provides an approved command; Issues #55 through #59 remain separate.

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
- the exact journal and #53 contracts bridges as the only Issue #51 consumers,
  plus zero journal consumers in every other Python/JavaScript file under
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
