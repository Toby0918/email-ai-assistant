---
last_update: 2026-07-26
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: security_policy
---

# Project Container cutover contract security boundary

## Scope

Issue #51 adds only the internal Python package
`backend.cutover_contracts`. It defines immutable, pathless, content-free
values for a future Project Container cutover. It does not add a CLI, HTTP
route, composition root, default adapter, host reader, lifecycle action,
authorization issuer, or executable cutover command.

This contract layer must not inspect or mutate a real Runtime, SQLite database,
ACL, repository, worktree, browser profile, artifact, Config directory,
mailbox, provider, vault, credential, private store, or private data. Real
preflight, evidence publication, migration, cutover, resume, rollback, incident
recovery, and cleanup remain outside Issue #51.

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
incorrect enum values, and fingerprint drift fail closed. The profile
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
Issue; Issue #51 does not implement Issues #52 through #59.

## Executable capability guards

`tests/test_cutover_contract_architecture.py` pins all of the following:

- the exact package files and exact public `__all__` surface;
- absolute imports limited to exact pure standard-library modules and exact
  imported symbols, with relative imports limited to exact sibling package
  modules; parent-relative and dotted-module imports fail;
- absence of filesystem, process, SQLite, network, environment, dynamic-import,
  clock, random, host, and ambient-authority calls;
- absence of real-authorization issuer or mint functions;
- zero consumers in every other Python/JavaScript file under `backend/`,
  `scripts/`, and `frontend/`, using AST checks for equivalent Python import
  forms and fixed token checks for JavaScript;
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
