"""Closed phase and validity schemas for external authorizations."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import CutoverContractError
from .profile_schema import _is_commit, _is_fingerprint


AUTHORIZATION_ERROR = "AUTHORIZATION_CONTRACT_INVALID"
AUTHORIZATION_BODY_KEYS = (
    "authorization_type",
    "operation",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_commit",
    "operator_fingerprint",
    "phase",
    "issued_at_epoch",
    "not_before_epoch",
    "expires_at_epoch",
)


@dataclass(frozen=True, slots=True)
class AuthorizationSpec:
    operation: str
    phases: tuple[str, ...]
    maximum_lifetime_seconds: int


AUTHORIZATION_SPECS = {
    "RealPreflightAuthorizationV1": AuthorizationSpec(
        operation="real_preflight",
        phases=(
            "current_topology_preflight",
            "host_baseline",
            "evidence_review",
            "evidence_verification",
            "final_audit_readiness",
            "recovery_inspection",
        ),
        maximum_lifetime_seconds=900,
    ),
    "EvidencePublicationAuthorizationV1": AuthorizationSpec(
        operation="evidence_publication",
        phases=("evidence_publication",),
        maximum_lifetime_seconds=900,
    ),
    "CutoverExecutionAuthorizationV1": AuthorizationSpec(
        operation="cutover_execution",
        phases=("execute", "resume"),
        maximum_lifetime_seconds=900,
    ),
    "RecoveryAuthorizationV1": AuthorizationSpec(
        operation="recovery",
        phases=("rollback", "incident_containment", "legacy_recovery"),
        maximum_lifetime_seconds=86_400,
    ),
}


def validate_authorization_body(
    value: object, *, expected_type: str
) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(AUTHORIZATION_BODY_KEYS):
        _invalid()
    spec = AUTHORIZATION_SPECS.get(expected_type)
    if (
        spec is None
        or value["authorization_type"] != expected_type
        or value["operation"] != spec.operation
        or value["phase"] not in spec.phases
        or not _is_fingerprint(value["operation_fingerprint"])
        or not _is_fingerprint(value["profile_fingerprint"])
        or not _is_commit(value["governing_master_commit"])
        or not _is_fingerprint(value["operator_fingerprint"])
    ):
        _invalid()
    _validate_validity(value, spec)
    return {key: value[key] for key in AUTHORIZATION_BODY_KEYS}


def spec_for_operation(operation: object) -> AuthorizationSpec | None:
    if type(operation) is not str:
        return None
    for spec in AUTHORIZATION_SPECS.values():
        if spec.operation == operation:
            return spec
    return None


def _validate_validity(
    value: dict[str, object], spec: AuthorizationSpec
) -> None:
    issued = value["issued_at_epoch"]
    not_before = value["not_before_epoch"]
    expires = value["expires_at_epoch"]
    if (
        type(issued) is not int
        or type(not_before) is not int
        or type(expires) is not int
        or not 0 <= issued <= not_before < expires < 2**63
        or expires - issued > spec.maximum_lifetime_seconds
    ):
        _invalid()


def _invalid() -> None:
    raise CutoverContractError(AUTHORIZATION_ERROR)
