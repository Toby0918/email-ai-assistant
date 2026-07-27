---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# Project Container cutover contract security boundary

## Scope

Issue #51 adds the internal Python package `backend.cutover_contracts`. Issue
#52 adds its sole approved consumer, the exact
`backend.cutover_journal.contracts_bridge`, inside the pathless synthetic-only
`backend.cutover_journal` state proof. Both packages remain content-free and add
no CLI, HTTP route, composition root, default host adapter, host reader,
authorization issuer, or executable real-host cutover command.

This contract layer must not inspect or mutate a real Runtime, SQLite database,
ACL, repository, worktree, browser profile, artifact, Config directory,
mailbox, provider, vault, credential, private store, or private data. Real
preflight, evidence publication, migration, real cutover, real resume, real
rollback, incident recovery, and cleanup remain outside Issues #51/#52.

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
executable operator entry or real-host composition requires a separate approved
Issue; Issues #51/#52 do not implement Issues #53 through #59.

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
- the exact journal bridge as the only Issue #51 consumer, plus zero journal
  consumers in every other Python/JavaScript file under `backend/`, `scripts/`,
  and `frontend/`, using AST checks for equivalent Python import forms,
  direct/attribute/imported/rebound dynamic-import call aliases, and fixed token
  checks for JavaScript;
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
- [ ] No production consumer or real-host operation has been added.
- [ ] Pending/unbarriered records never authorize a synthetic effect.
- [ ] Restart inspection is read-only and expected-post is never blindly retried.
- [ ] Reverse steps are pre-bound-authority, journal-derived, and LIFO.
