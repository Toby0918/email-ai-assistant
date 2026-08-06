---
last_update: 2026-08-06
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 External Artifact Issuance Runbook

## Purpose and stop conditions

This runbook covers the public, final-master-bound artifact phase authorized by
Issue #105. It has two code-supported actions: prepare one unsigned public
package, then install the externally signed bodies. It does not create or use a
private key, sign a body, approve Issue #38, or authorize Issue #39.

Stop immediately if the repository is not a clean fresh remote `master`, if any
reviewed source belongs to another master or binding, if the human reviewer has
not confirmed the exact issuance-manifest fingerprint, or if all fourteen
detached signatures are not available. Do not run the protected final verifier
before all fifteen installed files exist.

## Fixed boundaries

- Run only `scripts/prepare_r2_external_artifacts.py` from this repository.
- The CLI accepts exactly one verb, `prepare` or `install`, and one bounded
  canonical public JSON object on stdin terminated by one newline.
- There is no repository, destination, filename, key-file, private-key,
  environment-key, signer, provider, mailbox, vault, or host-command option.
- The tool freezes `HEAD`, the tracked tree, `origin/master`, the fresh GitHub
  remote master, the workflow lock, and the current script bytes before acting.
  Install also repeats a fixed read-only `HEAD`/tree/tracking-ref/clean-state/
  fresh-remote check before staging and immediately before the commit rename.
- The installation destination is resolved internally as the fixed Git common
  directory child `r2-final-master-closure-v1`.
- Existing final state or retained staging state is an incident to inspect, not
  something this tool may overwrite, remove, clean, or retry around.

## Phase A: public preparation

Run preparation only after the Issue #105 implementation is merged and the
local clean `master` exactly equals a freshly fetched remote `master`. A merge
changes the final-master binding, so a package prepared against the
implementation branch or the pre-merge master is invalid.

The canonical request has exactly these top-level fields:

```json
{
  "request_type": "R2ExternalArtifactPreparationRequestV1",
  "authority_verification_public_keys": [],
  "reviewed_outputs": {}
}
```

`authority_verification_public_keys` contains exactly four entries in this
order:

1. `preflight_verification`
2. `evidence_verification`
3. `execution_verification`
4. `recovery_verification`

Each entry contains only `role` and a lowercase canonical 32-byte
`public_key_hex`. The four keys must be pairwise unique and disjoint from the
fourteen final-gate verification keys already bound by the final-master closure
registry. They are public verification material, never signing capability.

`reviewed_outputs` contains exactly:

- `closure_surface_review`
- `git_byte_receipt`
- `ci_provenance_bundle`
- `ci_provenance_receipts`
- `runbook_receipt`
- `crash_recovery_review`
- `retention_proof`
- `documentation_review`
- `mechanical_architecture_review`
- `leakage_review`
- `maintenance_review`

The six supplied `R2GateSourceReviewV1` mappings are closed records. Their
source names, assertions, zero-defect fields, binding, master, closure map,
classified maintenance findings, and domain-separated fingerprints must match
exactly, including JSON scalar types: booleans and floating-point values cannot
stand in for integer counts. The Windows-native review is derived internally
from, and retains complete canonical copies of, the ordered Windows-independent
and Windows-native CI receipts. The portable platform lock must differ from the
shared Windows platform lock. No request field may supply a final gate evidence
fingerprint or production-role fingerprint.

Invoke the pinned Python 3.12.13 interpreter with the `prepare` verb and send
the canonical request as the single stdin line. The only successful stdout
value is one canonical `R2UnsignedExternalArtifactPackageV1`. Failure is the
fixed content-free object:

```json
{"status":"R2_EXTERNAL_ARTIFACT_INVALID"}
```

## Human manifest review and external signing

The package contains:

- one canonical reviewed production binding;
- fourteen unsigned gate bodies in fixed registry order;
- fourteen public derivation-provenance records;
- one exact file/hash/provenance issuance manifest;
- `artifact_count=15`, `unsigned_gate_count=14`, and `signature_count=0`.

The human reviewer must review the exact canonical package and record its
`issuance_manifest_fingerprint`. Any byte, ordering, key, source, hash, master,
or binding change requires a new review; confirmation is not transferable.

The offline external signing process is outside this repository and outside
this runbook. This repository provides no signing command, private-key format,
private-key path, key generator, key import, or test production signature. The
only values returned for installation are fourteen public detached Ed25519
signatures over the exact unsigned body bytes.

The signature order is fixed:

1. `final_master_binding`
2. `closure_surface_completeness`
3. `production_composition`
4. `git_bytes`
5. `dependency_action_provenance`
6. `windows_native`
7. `portable_full_suite`
8. `runbook_semantics`
9. `crash_recovery`
10. `retention_no_deletion`
11. `documentation`
12. `mechanical_architecture`
13. `leakage`
14. `maintenance_scope`

## Phase B: verification and installation

The canonical installation request has exactly these fields:

```json
{
  "request_type": "R2ExternalArtifactInstallationRequestV1",
  "unsigned_package": {},
  "confirmed_manifest_fingerprint": "64-lowercase-hex-characters",
  "detached_signatures": []
}
```

`unsigned_package` is the unchanged Phase A output.
`confirmed_manifest_fingerprint` is the exact human-reviewed manifest
fingerprint. `detached_signatures` contains exactly fourteen lowercase
canonical 64-byte signature hex strings in the order above.

Invoke the same pinned interpreter with the `install` verb and send the
canonical request as the single stdin line. Before any artifact staging or
publication filesystem mutation, the tool reparses the package, rebuilds the
production binding, verifies the exact manifest and provenance schemas,
rederives all fourteen evidence values, and verifies all fourteen signed
records through the protected public-key parser and global-gate coordinator.

After the first fresh-master recheck, the tool writes a deterministic sibling
staging directory with exclusive file creation and durable reread. On Windows it
opens every exact child by volume file ID with
`FILE_FLAG_OPEN_REQUIRING_OPLOCK` and `FILE_FLAG_OPEN_REPARSE_POINT`, then
immediately requests its RWH `FSCTL_REQUEST_OPLOCK` before any other filesystem
operation on that opened object. It retains the pending input, output,
`OVERLAPPED`, event, and handle while validating the file ID, exact
`FileStandardInfo` single-link state, sole default `::$DATA` stream, and bytes.
It likewise preopens the exact
staging-directory path with read, delete, and DACL rights while denying delete
sharing, then immediately requests its Read oplock. It binds that handle's
`FileIdInfo` volume/file ID to the path identity before and after open, and
applies one protected read/execute-only DACL through all sixteen already-guarded
handles. Bounded `FileStreamInfo` queries reject any child or directory
alternate data stream; same-handle enumeration binds every exact name to its
file ID without reopening child paths. With those guards held and initially
quiet, the tool repeats the same fresh-master check, performs a final exact
same-handle validation, and requires all guards to remain quiet at commit. An
operation admitted before lockdown must be detected by validation or a broken
guard; an operation attempted after lockdown is denied. The
calling thread synchronously performs the native no-replace parent rename
through the same preauthorized directory handle while all sixteen bound guards
remain held, then rechecks the exact target identity, inventory, and bytes. The
protected DACL persists on the final directory, so a late write, replacement,
unlink, or insertion cannot poison the release boundary. There is no controller,
background commit, or sequential release; bounded `CancelIoEx` applies only to
a same-handle read, and every pending oplock request is cancelled and
synchronously reaped before its storage or handles are released. Linux uses
`renameat2(RENAME_NOREPLACE)`. A failed
commit leaves the stage intact and exposes no final directory. Success reports
only:

```json
{
  "status": "R2_EXTERNAL_ARTIFACTS_INSTALLED",
  "artifact_count": 15,
  "signed_gate_count": 14,
  "signature_count": 14,
  "overwrite_count": 0,
  "deletion_count": 0
}
```

The installed directory contains only
`reviewed-production-binding-v2.json` and the fixed files
`01-final_master_binding.json` through `14-maintenance_scope.json`.

The operator account is trusted throughout installation. Do not change owner,
DACL, privileges, or open a separate write-capable handle against the staging or
final directory. The read/execute-only DACL blocks ordinary fresh mutation
opens; it cannot make an object immutable against its owner or an administrator.
Any object-security change, privileged mutation, or deliberately pre-positioned
foreign write handle invalidates the installation evidence: stop as an incident
and do not interpret a prior aggregate success line as verifier eligibility.

## Protected final verification

Only after successful installation, remain on the same clean fresh remote
`master` and run the unchanged no-argument verifier with isolated mode:

```powershell
D:\Projects\email_ai_assistant\.venv\Scripts\python.exe -I -B scripts\verify_r2_final_master_closure.py
```

The sole acceptable result for this phase is
`AWAITING_SINGLE_HUMAN_FINAL_REVIEW`. Any `BLOCKED_*`, missing/invalid count,
nonzero eligibility deviation, changed master, dirty tree, or other output
keeps Issue #105 open and requires incident review; do not delete or overwrite
the installed or retained stage state.

After that exact result, assemble the immutable `R2-D38-01` through
`R2-D38-14` human-review package using the order and meanings owned by the
existing Issue #38 decision registry and `r2_final_operator_runbook.md`. Do not
duplicate or reinterpret that registry here.

Issue #105 may close only after the exact protected-verifier result and complete
immutable review package exist. Issue #38 remains a separate single-human final
review and must not be approved or closed by this tool. Issue #39 remains
unstarted and receives no authority from preparation, signatures, installation,
tests, or verifier eligibility.
