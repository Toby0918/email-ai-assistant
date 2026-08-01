---
last_update: 2026-07-29
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

## Issue #71 fixed preflight process and authorization ingress

Issue #71 adds one dedicated `backend.r2_preflight_process` executable root.
Its argv is exactly one of six code-fixed read-only preflight verbs. It accepts
no path, Profile, authorization, journal, recovery, force, vararg, or free-form
command value, and it is physically separate from evidence publication and the
transaction process. Normal runtime, frontend, scripts, cleanup, schedulers,
and workflows cannot import this root.

Before any acknowledgement or hidden read, the production terminal adapter
requires stdin, stdout, and stderr to be Windows TTYs. The acknowledgement is
exact and the following base64 value is read once without echo under a 65,536
character ceiling. Redirected standard streams, extra argv, and wrong
acknowledgement fail closed. The executable does not inspect environment
variables or authorization files and has no alternate pipe ingress.

`backend.r2_operator_process` is verification-only. It canonicalizes one
domain-tagged envelope, verifies an external Ed25519 signature with a public
key, reconstructs the nominal real preflight authorization, and binds its
type, domain, phase, Profile, governing master, operator, operation, lifetime,
and single-use nonce before the preflight lock is invoked. It contains no
private key, signing function, issuer, target reader, or mutation capability.
Wrong and cross-domain values are rejected before any reader acquisition.

The real preflight process remains dormant before separately approved Issue
#39. Even a valid real authorization reaches only
`BLOCKED_NO_APPROVED_COMMAND`, with one accepted authorization, zero rejected
authorizations, and zero host operations. Public results expose only fixed
status values and the allowlisted aggregate counts `accepted`, `rejected`, and
`host_operations`; prompts are fixed text. Synthetic authorization tests use
test-owned keys and state, and the Windows integration test uses one fresh
hidden local console owned by a detached test host. Neither proof authorizes or
observes the real cutover host.

## Issue #72 fixed evidence-publication process

Issue #72 adds `backend.r2_evidence_process` as a second, physically separate
operator executable. It accepts only the exact `publish` verb and cannot import
or select preflight, transaction, recovery, or the independent evidence
verifier. No target, source, path, Profile, review, authorization, journal,
recovery, force, vararg, or free-form value appears in argv.

All three standard streams must be real Windows TTYs before the exact evidence
acknowledgement and one hidden bounded base64 envelope read. Evidence envelopes
use the distinct evidence Ed25519 public-key domain and nominal
`EvidencePublicationAuthorizationV1`. Wrong-domain, missing, malformed,
expired, replayed, Profile/master/operator/operation drift, or a review that is
not exactly the preconfirmed opaque review fingerprint fails before the
publication capability is acquired.

The synthetic process binder supplies one narrow create-only callback in a
fresh test-owned directory. An accepted invocation calls it exactly once and
returns `EVIDENCE_PUBLISHED` with only `accepted`, `rejected`, and `published`
counts. Collision, callback failure, non-unit completion, or a repeated
invocation cannot claim success. Evidence verification remains owned by the
existing physically independent read-only verifier and is never called by this
process.

The real evidence entry remains dormant before #39. A valid real authorization
still returns `BLOCKED_NO_APPROVED_COMMAND` and acquires no publication
capability. Tests use only synthetic package bytes and test-owned Ed25519 keys;
they do not access a real evidence package, Repository Root, provider, mailbox,
vault, credential, private store, or private content.

## Issue #73 fixed transaction process

Issue #73 adds the third and final operator executable root,
`backend.r2_transaction_process`. It accepts only `execute`, `resume`, or
`rollback`; it cannot import or select the preflight or evidence roots and has
no umbrella, path, Profile, journal-path, recovery-target, force, shell,
PowerShell, Git-command, vararg, or free-form surface.

Every signed transaction envelope includes an exact
`R2TransactionAuthorizationContextV1`: the approved binding fingerprint,
journal owner, current durable journal head, remaining reverse-plan
fingerprint, boundary epoch, and a separately single-use crash nonce. Execute
and resume require `CutoverExecutionAuthorizationV1` under the execution key;
rollback requires `RecoveryAuthorizationV1` under the recovery key. Domain,
type, operation, phase, Profile/master/operator, head, plan, clock, expiry,
envelope nonce, and crash nonce are verified before an action callback exists.

One invocation acquires at most one exact action callback and reports only
fixed status plus `accepted`, `rejected`, and `mutations` counts. Synthetic
tests can execute one injected action with no host capability. The real entry
remains `BLOCKED_NO_APPROVED_COMMAND` with zero mutations before #39.

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
