"""Closed contracts for the complete R2 provider-disabled validation slice."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from backend.cutover_composition_contracts.canonical import fingerprint, is_fingerprint
from backend.r2_config_publication import ConfigPublicationReceiptV1, ConfigPublicationStatus
from backend.r2_crx_publication import CrxPublicationReceiptV1, CrxPublicationStatus
from backend.r2_database_publication import DatabaseTransactionResultV1, DatabaseTransactionStatus
from backend.r2_evidence_process import EvidenceProcessResult, EvidenceProcessStatus
from backend.r2_independent_audits import AuditKind
from backend.r2_repository_manifest import RepositoryTopologyReceiptV1
from backend.r2_runtime_publication import RuntimePublicationReceiptV1, RuntimePublicationStatus


class ValidationBoundary(str, Enum):
    START_A = "start_a"
    HEALTH_A = "health_a"
    ANALYSIS_A = "analysis_a"
    CONFIRM_A = "confirm_a"
    ROW_A = "row_a"
    STOP_A = "stop_a"
    DATABASE_VERIFY = "database_verify"
    STOPPED_AUDIT = "stopped_audit"
    START_B = "start_b"
    HEALTH_B = "health_b"
    FINAL_AUDIT = "final_audit"


class ValidationStatus(str, Enum):
    VALIDATED = "PROVIDER_DISABLED_LIFECYCLE_VALIDATED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False)
class ValidationFaultSelectorV1:
    kind: str
    boundary: ValidationBoundary | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ValidationFaultSelectorV1 requires a fixed factory")

    @classmethod
    def none(cls):
        return _fault(cls, "none", None)

    @classmethod
    def crash(cls, boundary: ValidationBoundary):
        return _fault(cls, "crash", boundary)

    @classmethod
    def deterministic_failure(cls, boundary: ValidationBoundary):
        return _fault(cls, "deterministic_failure", boundary)

    @classmethod
    def ambiguous_failure(cls, boundary: ValidationBoundary):
        return _fault(cls, "ambiguous_failure", boundary)


@dataclass(frozen=True, slots=True, repr=False, init=False)
class ApprovedValidationSliceV1:
    operation_fingerprint: str
    profile_fingerprint: str
    authorization_fingerprint: str
    evidence_fingerprint: str
    journal_head_fingerprint: str
    runtime_fingerprint: str
    crx_fingerprint: str
    config_fingerprint: str
    database_role_fingerprint: str
    approved_identities_fingerprint: str
    slice_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ApprovedValidationSliceV1 requires create()")

    @classmethod
    def create(cls, **values):
        if not _valid_approved(values):
            raise ValueError("R2_VALIDATION_APPROVED_SLICE_INVALID")
        normalized = {
            "operation_fingerprint": values["operation_fingerprint"],
            "profile_fingerprint": values["profile_fingerprint"],
            "authorization_fingerprint": values["authorization_fingerprint"],
            "evidence_fingerprint": values["evidence_fingerprint"],
            "journal_head_fingerprint": values["repository"].journal_head_fingerprint,
            "runtime_fingerprint": values["runtime"].receipt_fingerprint,
            "crx_fingerprint": values["crx"].receipt_fingerprint,
            "config_fingerprint": values["config"].receipt_fingerprint,
            "database_role_fingerprint": values["database"].receipt_fingerprint,
            "approved_identities_fingerprint": values["approved_identities_fingerprint"],
        }
        result = object.__new__(cls)
        for name, value in normalized.items():
            object.__setattr__(result, name, value)
        object.__setattr__(result, "slice_fingerprint", fingerprint("r2-validation-slice-v1", normalized))
        return result


@dataclass(frozen=True, slots=True, repr=False)
class ValidationStartRequestV1:
    phase: str
    nonce: str
    profile_fingerprint: str
    runtime_fingerprint: str
    config_fingerprint: str
    database_role_fingerprint: str
    port: int
    primary_provider: str
    fallback_provider: str
    request_fingerprint: str


@dataclass(frozen=True, slots=True, repr=False, init=False)
class PublicRuleFallbackResultV1:
    request_fingerprint: str
    result_fingerprint: str
    analysis_engine_source: str
    provider_attempts: int
    safe: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("PublicRuleFallbackResultV1 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {"request_fingerprint", "result_fingerprint", "analysis_engine_source", "provider_attempts", "safe"}
        if set(values) != expected or not is_fingerprint(values["request_fingerprint"]) or not is_fingerprint(values["result_fingerprint"]) or type(values["analysis_engine_source"]) is not str or type(values["provider_attempts"]) is not int or type(values["safe"]) is not bool:
            raise ValueError("R2_VALIDATION_RESULT_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class OperatorPublicConfirmationV1:
    result_fingerprint: str
    confirmation_fingerprint: str
    confirmed: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("OperatorPublicConfirmationV1 requires create()")

    @classmethod
    def create(cls, **values):
        if set(values) != {"result_fingerprint", "confirmation_fingerprint", "confirmed"} or not all(is_fingerprint(values[name]) for name in ("result_fingerprint", "confirmation_fingerprint")) or type(values["confirmed"]) is not bool:
            raise ValueError("R2_VALIDATION_CONFIRMATION_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class PersistedPublicRowEvidenceV1:
    result_fingerprint: str
    database_role_fingerprint: str
    matching_rows: int
    write_count: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("PersistedPublicRowEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values):
        if set(values) != {"result_fingerprint", "database_role_fingerprint", "matching_rows", "write_count"} or not all(is_fingerprint(values[name]) for name in ("result_fingerprint", "database_role_fingerprint")) or any(type(values[name]) is not int for name in ("matching_rows", "write_count")):
            raise ValueError("R2_VALIDATION_ROW_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FinalDatabaseProofV1:
    database_role_fingerprint: str
    checkpoint: str
    matching_rows: int
    sidecar_count: int
    source_unchanged: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("FinalDatabaseProofV1 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {"database_role_fingerprint", "matching_rows", "sidecar_count", "source_unchanged"}
        if set(values) != expected or not is_fingerprint(values["database_role_fingerprint"]) or type(values["matching_rows"]) is not int or type(values["sidecar_count"]) is not int or type(values["source_unchanged"]) is not bool:
            raise ValueError("R2_VALIDATION_DATABASE_PROOF_INVALID")
        result = object.__new__(cls)
        for name, value in {**values, "checkpoint": "FINAL_OR_RECOVERY_VERIFY"}.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False)
class IndependentAuditRequestV1:
    audit_kind: AuditKind
    service_nonce: str
    service_process_id: int
    journal_head_fingerprint: str
    approved_identities_fingerprint: str
    health_evidence_fingerprint: str


@dataclass(frozen=True, slots=True, repr=False, init=False)
class IndependentAuditCompletionV1:
    audit_kind: AuditKind
    audit_process_id: int
    service_nonce: str
    service_process_id: int
    journal_head_fingerprint: str
    approved_identities_fingerprint: str
    health_evidence_fingerprint: str
    observed_at_epoch: int
    expires_at_epoch: int
    attested: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("IndependentAuditCompletionV1 requires create()")

    @classmethod
    def create(cls, **values):
        if not _valid_audit_completion(values):
            raise ValueError("R2_VALIDATION_AUDIT_COMPLETION_INVALID")
        result = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result


@dataclass(frozen=True, slots=True, repr=False)
class ValidationLifecycleResultV1:
    status: ValidationStatus
    completed_boundaries: int
    analysis_count: int
    database_write_count: int
    provider_attempts: int
    receipt_fingerprint: str


def start_request(approved, phase, nonce):
    body = {"phase": phase, "nonce": nonce, "profile": approved.profile_fingerprint, "runtime": approved.runtime_fingerprint, "config": approved.config_fingerprint, "database": approved.database_role_fingerprint, "port": 8765, "primary": "disabled", "fallback": "disabled"}
    if phase not in {"start_a", "start_b"} or not _uuid4(nonce):
        raise ValueError("R2_VALIDATION_START_REQUEST_INVALID")
    return ValidationStartRequestV1(phase, nonce, approved.profile_fingerprint, approved.runtime_fingerprint, approved.config_fingerprint, approved.database_role_fingerprint, 8765, "disabled", "disabled", fingerprint("r2-validation-start-request-v1", body))


def _fault(cls, kind, boundary):
    if kind != "none" and type(boundary) is not ValidationBoundary:
        raise ValueError("R2_VALIDATION_FAULT_INVALID")
    result = object.__new__(cls)
    object.__setattr__(result, "kind", kind)
    object.__setattr__(result, "boundary", boundary)
    return result


def _valid_approved(values):
    expected = {"operation_fingerprint", "profile_fingerprint", "authorization_fingerprint", "evidence", "evidence_fingerprint", "repository", "runtime", "crx", "config", "database", "approved_identities_fingerprint"}
    return set(values) == expected and all(is_fingerprint(values[name]) for name in ("operation_fingerprint", "profile_fingerprint", "authorization_fingerprint", "evidence_fingerprint", "approved_identities_fingerprint")) and type(values["evidence"]) is EvidenceProcessResult and values["evidence"].status is EvidenceProcessStatus.PUBLISHED and type(values["repository"]) is RepositoryTopologyReceiptV1 and values["repository"].status == "REPOSITORY_TOPOLOGY_PUBLISHED" and type(values["runtime"]) is RuntimePublicationReceiptV1 and values["runtime"].status is RuntimePublicationStatus.PUBLISHED and values["runtime"].complete and type(values["crx"]) is CrxPublicationReceiptV1 and values["crx"].status is CrxPublicationStatus.PUBLISHED and values["crx"].source_held_through_final_verify and values["crx"].target_held_through_final_verify and type(values["config"]) is ConfigPublicationReceiptV1 and values["config"].status is ConfigPublicationStatus.PUBLISHED and values["config"].provider_disabled and values["config"].loader_verified and type(values["database"]) is DatabaseTransactionResultV1 and values["database"].status is DatabaseTransactionStatus.PUBLISHED and values["database"].source_mutations == 0


def _valid_audit_completion(values):
    expected = {"audit_kind", "audit_process_id", "service_nonce", "service_process_id", "journal_head_fingerprint", "approved_identities_fingerprint", "health_evidence_fingerprint", "observed_at_epoch", "expires_at_epoch", "attested"}
    return set(values) == expected and type(values["audit_kind"]) is AuditKind and all(type(values[name]) is int and values[name] > 0 for name in ("audit_process_id", "service_process_id")) and _uuid4(values["service_nonce"]) and all(is_fingerprint(values[name]) for name in ("journal_head_fingerprint", "approved_identities_fingerprint", "health_evidence_fingerprint")) and type(values["observed_at_epoch"]) is int and type(values["expires_at_epoch"]) is int and type(values["attested"]) is bool


def _uuid4(value):
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, TypeError, ValueError):
        return False
    return type(value) is str and parsed.version == 4 and str(parsed) == value
