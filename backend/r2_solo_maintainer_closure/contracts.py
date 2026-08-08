"""Canonical closure binding, manifest, candidate, receipt, and errors."""

from __future__ import annotations

from enum import Enum

from ._canonical import (
    CanonicalDataError,
    CanonicalValue,
    allocate_value,
    canonical_json,
    fingerprint,
    is_fingerprint,
    is_git_oid,
    is_nonnegative_int,
    strict_object,
)

ASSURANCE_MODEL = "SOLE_MAINTAINER_SELF_REVIEW"
CONFIRMATION_ACKNOWLEDGEMENT = (
    "CONFIRM_SOLO_MAINTAINER_CLOSURE_V1_NOT_ISSUE39_AUTHORITY"
)
CONFIRMATION_WINDOW_SECONDS = 300

class ClosureErrorCode(str, Enum):
    INVALID = "R2_SOLO_MAINTAINER_CLOSURE_INVALID"
    TTY_REQUIRED = "R2_SOLO_MAINTAINER_CLOSURE_TTY_REQUIRED"
    FINGERPRINT_REJECTED = "R2_SOLO_MAINTAINER_CLOSURE_FINGERPRINT_REJECTED"
    ACKNOWLEDGEMENT_REJECTED = "R2_SOLO_MAINTAINER_CLOSURE_ACKNOWLEDGEMENT_REJECTED"
    STALE = "R2_SOLO_MAINTAINER_CLOSURE_STALE"
    MASTER_DRIFT = "R2_SOLO_MAINTAINER_CLOSURE_MASTER_DRIFT"
    HOSTED_EVIDENCE_REJECTED = "R2_SOLO_MAINTAINER_CLOSURE_HOSTED_EVIDENCE_REJECTED"
    GITHUB_GUARDRAIL_REJECTED = "R2_SOLO_MAINTAINER_CLOSURE_GITHUB_GUARDRAIL_REJECTED"
    EVIDENCE_REJECTED = "R2_SOLO_MAINTAINER_CLOSURE_EVIDENCE_REJECTED"
    ALREADY_EXISTS = "R2_SOLO_MAINTAINER_CLOSURE_ALREADY_EXISTS"
    PUBLICATION_REJECTED = "R2_SOLO_MAINTAINER_CLOSURE_PUBLICATION_REJECTED"

class SoloMaintainerClosureError(ValueError):
    """Fixed content-free Issue #110 failure."""

    def __init__(self, code: ClosureErrorCode = ClosureErrorCode.INVALID) -> None:
        if type(code) is not ClosureErrorCode:
            code = ClosureErrorCode.INVALID
        self.code = code
        super().__init__(code.value)

_BINDING_BODY = (
    "binding_type", "final_commit_oid", "final_tree_oid",
    "closure_map_fingerprint", "source_package_fingerprint",
    "runbook_fingerprint", "workflow_fingerprint",
)

class FinalMasterBindingV1(CanonicalValue):
    @classmethod
    def create(cls, *, final_commit_oid: object, final_tree_oid: object,
               source_package_fingerprint: object, runbook_fingerprint: object,
               workflow_fingerprint: object) -> FinalMasterBindingV1:
        body = {
            "binding_type": "FinalMasterBindingV1",
            "final_commit_oid": final_commit_oid,
            "final_tree_oid": final_tree_oid,
            "closure_map_fingerprint": _closure_map_fingerprint(),
            "source_package_fingerprint": source_package_fingerprint,
            "runbook_fingerprint": runbook_fingerprint,
            "workflow_fingerprint": workflow_fingerprint,
        }
        _validate_binding_body(body)
        return _with_fingerprint(cls, body, "binding_fingerprint", "r2-final-master-binding-v1")

    @classmethod
    def from_json(cls, payload: object) -> FinalMasterBindingV1:
        return _parse_value(cls, payload, _BINDING_BODY, "binding_fingerprint",
                            "r2-final-master-binding-v1", _validate_binding_body)

    @classmethod
    def from_mapping(cls, source: object) -> FinalMasterBindingV1:
        return cls.from_json(canonical_json(source))

_MANIFEST_FIELDS = (
    "manifest_type", "final_master_binding", "final_master_binding_fingerprint",
    "final_commit_oid", "final_tree_oid", "closure_map_fingerprint",
    "source_package_fingerprint", "runbook_fingerprint", "workflow_fingerprint",
    "production_binding", "production_binding_fingerprint", "github_guardrail_snapshot",
    "github_guardrail_snapshot_fingerprint", "hosted_evidence", "hosted_evidence_count",
    "hosted_evidence_set_fingerprint", "evidence_records", "evidence_record_count",
    "evidence_set_fingerprint", "gap_proofs", "gap_proof_count",
    "gap_proof_set_fingerprint", "assurance_model", "operator_count",
    "independent_reviewer_count", "external_signer_count",
    "hosted_evidence_human_approval_count", "solo_maintainer_attestation_count",
    "approval_count", "execution_authority_count", "issue39_authority_count",
    "historical_master_count", "open_finding_count", "contract_changing_finding_count",
    "decision_contradiction_finding_count", "security_incident_finding_count",
    "surface_omission_count", "evidence_defect_count", "required_skip_count",
    "unclassified_skip_count", "platform_divergence_count", "leakage_finding_count",
    "private_data_access_count", "real_host_operation_count", "provider_attempt_count",
    "cleanup_operation_count", "deletion_operation_count", "overwrite_operation_count",
    "failure_count",
)

class SoloMaintainerClosureManifestV1(CanonicalValue):
    @classmethod
    def create(cls, source: dict[str, object]) -> SoloMaintainerClosureManifestV1:
        _validate_manifest_body(source)
        return _with_fingerprint(cls, source, "manifest_fingerprint",
                                 "r2-solo-maintainer-closure-manifest-v1")

    @classmethod
    def from_json(cls, payload: object) -> SoloMaintainerClosureManifestV1:
        return _parse_value(cls, payload, _MANIFEST_FIELDS, "manifest_fingerprint",
                            "r2-solo-maintainer-closure-manifest-v1", _validate_manifest_body)

    @classmethod
    def from_mapping(cls, source: object) -> SoloMaintainerClosureManifestV1:
        return cls.from_json(canonical_json(source))

_CANDIDATE_FIELDS = (
    "candidate_type", "status", "manifest", "manifest_fingerprint",
    "confirmation_acknowledgement", "confirmation_window_seconds",
    "prepared_at_epoch", "expires_at_epoch", "confirmation_real_tty_required",
    "issue39_authority_count",
)


class SoloMaintainerClosureCandidateV1(CanonicalValue):
    @classmethod
    def create(cls, manifest: SoloMaintainerClosureManifestV1,
               prepared_at_epoch: int) -> SoloMaintainerClosureCandidateV1:
        body = {
            "candidate_type": "SoloMaintainerClosureCandidateV1",
            "status": "AWAITING_SOLO_MAINTAINER_CONFIRMATION",
            "manifest": manifest.to_mapping(),
            "manifest_fingerprint": manifest.manifest_fingerprint,
            "confirmation_acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT,
            "confirmation_window_seconds": CONFIRMATION_WINDOW_SECONDS,
            "prepared_at_epoch": prepared_at_epoch,
            "expires_at_epoch": prepared_at_epoch + CONFIRMATION_WINDOW_SECONDS,
            "confirmation_real_tty_required": 1,
            "issue39_authority_count": 0,
        }
        _validate_candidate_body(body)
        return _with_fingerprint(cls, body, "candidate_fingerprint",
                                 "r2-solo-maintainer-closure-candidate-v1")

    @classmethod
    def from_json(cls, payload: object) -> SoloMaintainerClosureCandidateV1:
        return _parse_value(cls, payload, _CANDIDATE_FIELDS, "candidate_fingerprint",
                            "r2-solo-maintainer-closure-candidate-v1", _validate_candidate_body)

    @property
    def manifest_value(self) -> SoloMaintainerClosureManifestV1:
        return SoloMaintainerClosureManifestV1.from_mapping(self.manifest)

_RECEIPT_FIELDS = (
    "receipt_type", "status", "manifest_fingerprint", "candidate_fingerprint",
    "final_master_binding_fingerprint", "final_commit_oid", "final_tree_oid",
    "source_package_fingerprint", "production_binding_fingerprint",
    "github_guardrail_snapshot_fingerprint", "hosted_evidence_set_fingerprint",
    "evidence_set_fingerprint", "gap_proof_set_fingerprint", "acknowledgement",
    "acknowledgement_fingerprint", "prepared_at_epoch", "confirmed_at_epoch",
    "expires_at_epoch", "confirmation_window_seconds", "assurance_model",
    "operator_count", "independent_reviewer_count", "external_signer_count",
    "hosted_evidence_human_approval_count", "solo_maintainer_attestation_count",
    "confirmation_real_tty_count", "stdin_stdout_stderr_console_verified",
    "approval_count", "execution_authority_count", "issue39_authority_count",
    "artifact_count", "created_count", "overwrite_count", "deletion_count",
    "cleanup_count", "provider_attempt_count", "real_host_operation_count",
    "private_data_access_count",
)


class SoloMaintainerAttestationReceiptV1(CanonicalValue):
    @classmethod
    def create(cls, candidate: SoloMaintainerClosureCandidateV1,
               confirmed_at_epoch: int) -> SoloMaintainerAttestationReceiptV1:
        body = _receipt_body(candidate, confirmed_at_epoch)
        _validate_receipt_body(body)
        return _with_fingerprint(cls, body, "receipt_fingerprint",
                                 "r2-solo-maintainer-attestation-receipt-v1")

    @classmethod
    def from_json(cls, payload: object) -> SoloMaintainerAttestationReceiptV1:
        return _parse_value(cls, payload, _RECEIPT_FIELDS, "receipt_fingerprint",
                            "r2-solo-maintainer-attestation-receipt-v1", _validate_receipt_body)

def _receipt_body(candidate: SoloMaintainerClosureCandidateV1,
                  confirmed: int) -> dict[str, object]:
    if type(candidate) is not SoloMaintainerClosureCandidateV1:
        raise SoloMaintainerClosureError()
    manifest = candidate.manifest
    copied = (
        "final_master_binding_fingerprint", "final_commit_oid", "final_tree_oid",
        "source_package_fingerprint", "production_binding_fingerprint",
        "github_guardrail_snapshot_fingerprint", "hosted_evidence_set_fingerprint",
        "evidence_set_fingerprint", "gap_proof_set_fingerprint",
    )
    body = {"receipt_type": "SoloMaintainerAttestationReceiptV1",
            "status": "SOLO_MAINTAINER_ATTESTATION_RECORDED",
            "manifest_fingerprint": candidate.manifest_fingerprint,
            "candidate_fingerprint": candidate.candidate_fingerprint,
            **{name: manifest[name] for name in copied},
            "acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT,
            "acknowledgement_fingerprint": fingerprint(
                "r2-solo-maintainer-attestation-receipt-v1",
                {"acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT}),
            "prepared_at_epoch": candidate.prepared_at_epoch,
            "confirmed_at_epoch": confirmed,
            "expires_at_epoch": candidate.expires_at_epoch,
            "confirmation_window_seconds": CONFIRMATION_WINDOW_SECONDS,
            "assurance_model": ASSURANCE_MODEL}
    body.update(_receipt_counts())
    return body

def _receipt_counts() -> dict[str, int]:
    return {
        "operator_count": 1, "independent_reviewer_count": 0,
        "external_signer_count": 0, "hosted_evidence_human_approval_count": 0,
        "solo_maintainer_attestation_count": 1, "confirmation_real_tty_count": 1,
        "stdin_stdout_stderr_console_verified": 1, "approval_count": 0,
        "execution_authority_count": 0, "issue39_authority_count": 0,
        "artifact_count": 2, "created_count": 2, "overwrite_count": 0,
        "deletion_count": 0, "cleanup_count": 0, "provider_attempt_count": 0,
        "real_host_operation_count": 0, "private_data_access_count": 0,
    }

def _validate_binding_body(body: dict[str, object]) -> None:
    valid = (set(body) == set(_BINDING_BODY)
             and body.get("binding_type") == "FinalMasterBindingV1"
             and is_git_oid(body.get("final_commit_oid"))
             and is_git_oid(body.get("final_tree_oid"))
             and body.get("closure_map_fingerprint") == _closure_map_fingerprint())
    names = ("source_package_fingerprint", "runbook_fingerprint", "workflow_fingerprint")
    if not valid or not all(is_fingerprint(body.get(name)) for name in names):
        raise SoloMaintainerClosureError()

def _validate_manifest_body(body: dict[str, object]) -> None:
    from .evidence import validate_manifest_body
    validate_manifest_body(body, set(_MANIFEST_FIELDS), FinalMasterBindingV1)


def _validate_candidate_body(body: dict[str, object]) -> None:
    if set(body) != set(_CANDIDATE_FIELDS):
        raise SoloMaintainerClosureError()
    manifest = SoloMaintainerClosureManifestV1.from_mapping(body.get("manifest"))
    expected = ("SoloMaintainerClosureCandidateV1", "AWAITING_SOLO_MAINTAINER_CONFIRMATION",
                manifest.manifest_fingerprint, CONFIRMATION_ACKNOWLEDGEMENT, 300, 1, 0)
    observed = (body.get("candidate_type"), body.get("status"), body.get("manifest_fingerprint"),
                body.get("confirmation_acknowledgement"), body.get("confirmation_window_seconds"),
                body.get("confirmation_real_tty_required"), body.get("issue39_authority_count"))
    prepared, expires = body.get("prepared_at_epoch"), body.get("expires_at_epoch")
    if observed != expected or not is_nonnegative_int(prepared) or expires != prepared + 300:
        raise SoloMaintainerClosureError()


def _validate_receipt_body(body: dict[str, object]) -> None:
    if set(body) != set(_RECEIPT_FIELDS):
        raise SoloMaintainerClosureError()
    expected = ("SoloMaintainerAttestationReceiptV1", "SOLO_MAINTAINER_ATTESTATION_RECORDED",
                CONFIRMATION_ACKNOWLEDGEMENT, CONFIRMATION_WINDOW_SECONDS, ASSURANCE_MODEL)
    observed = (body.get("receipt_type"), body.get("status"), body.get("acknowledgement"),
                body.get("confirmation_window_seconds"), body.get("assurance_model"))
    acknowledgement_fingerprint = fingerprint(
        "r2-solo-maintainer-attestation-receipt-v1",
        {"acknowledgement": CONFIRMATION_ACKNOWLEDGEMENT})
    if (observed != expected or body.get("acknowledgement_fingerprint") != acknowledgement_fingerprint
            or any(not is_fingerprint(body.get(name)) for name in _RECEIPT_FIELDS if name.endswith("fingerprint"))):
        raise SoloMaintainerClosureError()
    prepared, confirmed, expires = (body.get(name) for name in (
        "prepared_at_epoch", "confirmed_at_epoch", "expires_at_epoch"))
    if (not all(is_nonnegative_int(item) for item in (prepared, confirmed, expires))
            or not prepared <= confirmed < expires or expires != prepared + 300):
        raise SoloMaintainerClosureError()
    if any(body.get(name) != value for name, value in _receipt_counts().items()):
        raise SoloMaintainerClosureError()


def _with_fingerprint(kind: type[CanonicalValue], body: dict[str, object],
                      name: str, domain: str):
    return allocate_value(kind, {**body, name: fingerprint(domain, body)})


def _closure_map_fingerprint() -> str:
    from .evidence import closure_map_fingerprint
    return closure_map_fingerprint()


def _parse_value(kind: type[CanonicalValue], payload: object, body_fields: tuple[str, ...],
                 fingerprint_name: str, domain: str, validator):
    try:
        source = strict_object(payload)
        if set(source) != {*body_fields, fingerprint_name}:
            raise SoloMaintainerClosureError()
        body = {name: source[name] for name in body_fields}
        validator(body)
        if source[fingerprint_name] != fingerprint(domain, body):
            raise SoloMaintainerClosureError()
        return allocate_value(kind, source)
    except SoloMaintainerClosureError:
        raise
    except (CanonicalDataError, Exception):
        raise SoloMaintainerClosureError() from None
