"""Fixed two-phase public adapter for R2 external artifact issuance."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import sys
import tempfile

from backend.r2_ci_provenance_v2 import (
    CiProvenanceKindV2,
    CiProvenanceStatusV2,
    R2CiProvenanceBundleV2,
    R2CiProvenanceReceiptV2,
    R2GitObjectEntryV2,
    R2GitObjectSourcePackageV2,
)
from backend.r2_ci_provenance_v2._canonical import sha256
from backend.r2_final_master_closure import ClosureGate
from backend.r2_final_master_closure._canonical import (
    canonical_json,
    fingerprint,
    strict_json_object,
)
from backend.r2_final_master_closure.frozen_master import _allocate as _allocate_frozen
from backend.r2_operator_runbook_v2.receipt import (
    R2OperatorRunbookReceiptV2,
    RunbookVerificationStatusV2,
)
from backend.r2_production_binding import PublicKeyRoleV2
from backend.r2_production_composition import build_production_binding_candidate_v1
from backend.r2_repository_manifest.git_byte_receipt_v2 import (
    R2GitByteStateReceiptV1,
)
from backend.r2_retention_ledger_v2 import R2RetentionProofV2
from backend.r2_external_artifacts_v1 import (
    R2ExternalArtifactError,
    R2ExternalArtifactReviewInputsV1,
    R2GateSourceReviewV1,
    R2UnsignedExternalArtifactPackageV1,
    install_signed_external_artifacts_v1,
    prepare_unsigned_external_artifacts_v1,
)
from scripts import verify_r2_final_master_closure as _fixed
from scripts.r2_ci_provenance_support import _workflow_lock


_MAX_REQUEST_BYTES = 512 * 1024
_RUNBOOK = "docs/operations/r2_final_operator_runbook.md"
_SCRIPT = PurePosixPath("scripts/prepare_r2_external_artifacts.py")
_PREPARE_FIELDS = {
    "request_type", "authority_verification_public_keys", "reviewed_outputs"
}
_OUTPUT_FIELDS = set(R2ExternalArtifactReviewInputsV1.__dataclass_fields__) - {
    "production_binding"
}


def main() -> int:
    try:
        if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "install"}:
            raise R2ExternalArtifactError()
        payload = _read_request()
        frozen = _freeze_current_master_v1()
        response = _run_request_v1(sys.argv[1], payload, frozen)
    except BaseException:
        sys.stdout.buffer.write(b'{"status":"R2_EXTERNAL_ARTIFACT_INVALID"}\n')
        sys.stdout.buffer.flush()
        return 2
    sys.stdout.buffer.write(response + b"\n")
    sys.stdout.buffer.flush()
    return 0


def _run_request_v1(command, payload, frozen):
    try:
        request = strict_json_object(payload)
        if payload != canonical_json(request):
            raise R2ExternalArtifactError()
        if command == "prepare":
            return _prepare(request, frozen).to_canonical_json()
        if command == "install":
            result = _install(request, frozen)
            return canonical_json({
                "status": result.status,
                "artifact_count": result.artifact_count,
                "signed_gate_count": result.signed_gate_count,
                "signature_count": result.signature_count,
                "overwrite_count": result.overwrite_count,
                "deletion_count": result.deletion_count,
            })
        raise R2ExternalArtifactError()
    except R2ExternalArtifactError:
        raise
    except Exception:
        raise R2ExternalArtifactError() from None


def _prepare(request, frozen):
    if set(request) != _PREPARE_FIELDS or request["request_type"] != (
        "R2ExternalArtifactPreparationRequestV1"
    ):
        raise R2ExternalArtifactError()
    keys = _public_keys(request["authority_verification_public_keys"])
    candidate = build_production_binding_candidate_v1(
        final_master_binding=frozen.binding,
        verification_public_keys=keys,
    )
    inputs = _review_inputs(request["reviewed_outputs"], frozen.binding, candidate)
    return prepare_unsigned_external_artifacts_v1(
        frozen_master=frozen,
        authority_verification_public_keys=keys,
        review_inputs=inputs,
    )


def _install(request, frozen):
    expected = {
        "request_type", "unsigned_package", "confirmed_manifest_fingerprint",
        "detached_signatures",
    }
    if set(request) != expected or request["request_type"] != (
        "R2ExternalArtifactInstallationRequestV1"
    ):
        raise R2ExternalArtifactError()
    package = R2UnsignedExternalArtifactPackageV1.from_json(
        canonical_json(request["unsigned_package"]), frozen_master=frozen
    )
    raw_signatures = request["detached_signatures"]
    if type(raw_signatures) is not list or len(raw_signatures) != len(ClosureGate):
        raise R2ExternalArtifactError()
    signatures = tuple(_signature_bytes(item) for item in raw_signatures)
    return install_signed_external_artifacts_v1(
        unsigned_package=package,
        detached_signatures=signatures,
        confirmed_manifest_fingerprint=request["confirmed_manifest_fingerprint"],
    )


def _public_keys(value):
    if type(value) is not list or len(value) != len(PublicKeyRoleV2):
        raise R2ExternalArtifactError()
    result = {}
    for role, entry in zip(PublicKeyRoleV2, value, strict=True):
        if (
            type(entry) is not dict
            or set(entry) != {"role", "public_key_hex"}
            or entry["role"] != role.value
        ):
            raise R2ExternalArtifactError()
        key = _hex_bytes(entry["public_key_hex"], 32)
        result[role] = key
    return result


def _review_inputs(value, final_master, candidate):
    if type(value) is not dict or set(value) != _OUTPUT_FIELDS:
        raise R2ExternalArtifactError()
    reviews = {
        "closure_surface_review": ClosureGate.CLOSURE_SURFACE_COMPLETENESS,
        "crash_recovery_review": ClosureGate.CRASH_RECOVERY,
        "documentation_review": ClosureGate.DOCUMENTATION,
        "mechanical_architecture_review": ClosureGate.MECHANICAL_ARCHITECTURE,
        "leakage_review": ClosureGate.LEAKAGE,
        "maintenance_review": ClosureGate.MAINTENANCE_SCOPE,
    }
    parsed_reviews = {
        name: _source_review(value[name], gate, final_master)
        for name, gate in reviews.items()
    }
    receipts = value["ci_provenance_receipts"]
    if type(receipts) is not list or len(receipts) != len(CiProvenanceKindV2):
        raise R2ExternalArtifactError()
    return R2ExternalArtifactReviewInputsV1.create(
        production_binding=candidate,
        git_byte_receipt=_nominal(R2GitByteStateReceiptV1, value["git_byte_receipt"]),
        ci_provenance_bundle=_nominal(
            R2CiProvenanceBundleV2,
            value["ci_provenance_bundle"],
            {"status": CiProvenanceStatusV2},
        ),
        ci_provenance_receipts=tuple(
            _nominal(
                R2CiProvenanceReceiptV2,
                item,
                {
                    "status": CiProvenanceStatusV2,
                    "provenance_kind": CiProvenanceKindV2,
                },
            )
            for item in receipts
        ),
        runbook_receipt=_nominal(
            R2OperatorRunbookReceiptV2,
            value["runbook_receipt"],
            {"status": RunbookVerificationStatusV2},
        ),
        retention_proof=_nominal(
            R2RetentionProofV2, value["retention_proof"]
        ),
        **parsed_reviews,
    )


def _source_review(mapping, gate, final_master):
    if type(mapping) is not dict:
        raise R2ExternalArtifactError()
    entries = mapping.get("source_fingerprints")
    findings = mapping.get("classified_nonblocking_finding_fingerprints")
    if type(entries) is not list or type(findings) is not list:
        raise R2ExternalArtifactError()
    sources = {
        entry["source"]: entry["fingerprint"]
        for entry in entries
        if type(entry) is dict and set(entry) == {"source", "fingerprint"}
    }
    result = R2GateSourceReviewV1.create(
        gate=gate,
        final_master_binding=final_master,
        source_fingerprints=sources,
        classified_nonblocking_finding_fingerprints=tuple(findings),
    )
    if canonical_json(result.to_mapping()) != canonical_json(mapping):
        raise R2ExternalArtifactError()
    return result


def _nominal(kind, mapping, enum_fields=None):
    if type(mapping) is not dict or set(mapping) != set(kind.__dataclass_fields__):
        raise R2ExternalArtifactError()
    result = object.__new__(kind)
    enum_fields = enum_fields or {}
    for name in kind.__dataclass_fields__:
        item = mapping[name]
        enum_type = enum_fields.get(name)
        object.__setattr__(result, name, enum_type(item) if enum_type else item)
    if result.to_mapping() != mapping:
        raise R2ExternalArtifactError()
    return result


def _freeze_current_master_v1():
    head = _fixed._git("rev-parse", "HEAD^{commit}")
    remote = _fixed._git("rev-parse", "refs/remotes/origin/master^{commit}")
    if head != remote:
        raise R2ExternalArtifactError()
    with tempfile.TemporaryDirectory(prefix="r2-external-artifact-verified-") as raw:
        tree, descriptors = _fixed._materialize_head(head, Path(raw))
        _fixed._require_current_script_bytes(descriptors)
        _require_current_adapter_bytes(descriptors)
        _fixed._require_clean_index_and_worktree(descriptors)
        if remote != _fixed._fresh_remote_master():
            raise R2ExternalArtifactError()
        frozen = _frozen_from_descriptors(head, tree, remote, descriptors)
    if (
        head != _fixed._git("rev-parse", "HEAD^{commit}")
        or remote
        != _fixed._git("rev-parse", "refs/remotes/origin/master^{commit}")
    ):
        raise R2ExternalArtifactError()
    _fixed._require_current_script_bytes(descriptors)
    _require_current_adapter_bytes(descriptors)
    _fixed._require_clean_index_and_worktree(descriptors)
    return frozen


def _frozen_from_descriptors(head, tree, remote, descriptors):
    raw = {path.as_posix(): content for path, _mode, _oid, content in descriptors}
    if _RUNBOOK not in raw:
        raise R2ExternalArtifactError()
    lock = _workflow_lock(raw)
    entries = tuple(
        R2GitObjectEntryV2.create(
            relative_path=path.as_posix(), mode=mode,
            blob_oid=oid, content_bytes=content,
        )
        for path, mode, oid, content in descriptors
    )
    package = R2GitObjectSourcePackageV2.create(
        final_commit_oid=head, final_tree_oid=tree,
        observed_commit_oid=head, observed_tree_oid=tree,
        entries=entries, workflow_lock=lock,
        runbook_fingerprint=sha256(
            b"r2-operator-runbook-document-v2\0" + raw[_RUNBOOK]
        ),
    )
    binding = _binding_from_package(package, lock)
    return _allocate_frozen(binding, {
        "observation_type": "R2FrozenRemoteMasterV1",
        "status": "FROZEN_REMOTE_MASTER_VERIFIED",
        "binding_fingerprint": binding.binding_fingerprint,
        "remote_ref_fingerprint": fingerprint("r2-frozen-remote-ref-v1", {
            "remote_url": _fixed._REMOTE_URL, "ref": _fixed._REMOTE_REF,
            "commit": remote,
        }),
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "workflow_fingerprint": binding.workflow_fingerprint,
        "exact_match": 1, "historical_master_count": 0, "dirty_path_count": 0,
    })


def _binding_from_package(package, lock):
    from backend.r2_final_master_closure import FinalMasterBindingV1
    return FinalMasterBindingV1.create(
        final_commit_oid=package.final_commit_oid,
        final_tree_oid=package.final_tree_oid,
        source_package_fingerprint=package.source_package_fingerprint,
        runbook_fingerprint=package.runbook_fingerprint,
        workflow_fingerprint=lock.lock_fingerprint,
    )


def _require_current_adapter_bytes(descriptors):
    matches = [item for item in descriptors if item[0] == _SCRIPT]
    expected = _fixed.ROOT.joinpath(*_SCRIPT.parts)
    if (
        len(matches) != 1
        or os.path.normcase(os.path.abspath(__file__))
        != os.path.normcase(os.path.abspath(expected))
    ):
        raise R2ExternalArtifactError()
    _fixed._read_exact_tracked_file(_fixed.ROOT, _SCRIPT, matches[0][3])


def _read_request():
    payload = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
    if (
        len(payload) > _MAX_REQUEST_BYTES
        or not payload.endswith(b"\n")
        or b"\n" in payload[:-1]
    ):
        raise R2ExternalArtifactError()
    return payload[:-1]


def _signature_bytes(value):
    return _hex_bytes(value, 64)


def _hex_bytes(value, size):
    try:
        result = bytes.fromhex(value)
    except (TypeError, ValueError):
        raise R2ExternalArtifactError() from None
    if type(value) is not str or result.hex() != value or len(result) != size:
        raise R2ExternalArtifactError()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
