"""Closed authorization-sequence contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    RecoveryAuthorizationV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)

from .canonical import fingerprint, is_fingerprint
from .errors import CompositionContractError


AUTHORIZATION_PHASES = (
    (RealPreflightAuthorizationV1, "real_preflight", "current_topology_preflight"),
    (RealPreflightAuthorizationV1, "real_preflight", "host_baseline"),
    (RealPreflightAuthorizationV1, "real_preflight", "evidence_review"),
    (
        EvidencePublicationAuthorizationV1,
        "evidence_publication",
        "evidence_publication",
    ),
    (RealPreflightAuthorizationV1, "real_preflight", "evidence_verification"),
    (RealPreflightAuthorizationV1, "real_preflight", "final_audit_readiness"),
    (RealPreflightAuthorizationV1, "real_preflight", "recovery_inspection"),
    (CutoverExecutionAuthorizationV1, "cutover_execution", "execute"),
    (CutoverExecutionAuthorizationV1, "cutover_execution", "resume"),
    (RecoveryAuthorizationV1, "recovery", "rollback"),
    (RecoveryAuthorizationV1, "recovery", "legacy_recovery"),
)
_ERROR = "PROJECT_CONTAINER_AUTHORIZATION_SEQUENCE_INVALID"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class AuthorizationSequenceV1:
    profile_fingerprint: str = field(repr=False)
    governing_master_fingerprint: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    authorization_fingerprints: tuple[str, ...] = field(repr=False)
    expires_at_epoch: int = field(repr=False)
    _sandbox_authorized: bool = field(repr=False)
    sequence_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("AuthorizationSequenceV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        profile: CutoverProfileV1,
        operation_fingerprint: str,
        authorizations: tuple[object, ...],
        observed_at_epoch: int,
    ) -> AuthorizationSequenceV1:
        try:
            body = _validated_body(
                profile,
                operation_fingerprint,
                authorizations,
                observed_at_epoch,
            )
        except Exception:
            raise CompositionContractError(_ERROR) from None
        value = object.__new__(cls)
        for name, item in body.items():
            object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "sequence_fingerprint",
            fingerprint("project-container-authorization-sequence-v1", body),
        )
        return value


def _validated_body(profile, operation, authorizations, observed):
    if (
        type(profile) is not CutoverProfileV1
        or CutoverProfileV1.from_mapping(profile.to_mapping()) != profile
        or not is_fingerprint(operation)
        or type(authorizations) is not tuple
        or len(authorizations) != len(AUTHORIZATION_PHASES)
        or type(observed) is not int
        or not 0 <= observed < 2**63
    ):
        raise ValueError(_ERROR)
    for authorization, expected in zip(
        authorizations, AUTHORIZATION_PHASES, strict=True
    ):
        _require_authorization(authorization, expected, profile, operation, observed)
    return {
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_fingerprint": fingerprint(
            "project-container-governing-master-v1",
            profile.governing_master_commit,
        ),
        "operator_fingerprint": profile.operator_fingerprint,
        "operation_fingerprint": operation,
        "authorization_fingerprints": tuple(
            item.authorization_fingerprint for item in authorizations
        ),
        "expires_at_epoch": min(
            item.expires_at_epoch for item in authorizations
        ),
        "_sandbox_authorized": False,
    }


def _require_authorization(authorization, expected, profile, operation, observed):
    kind, operation_name, phase = expected
    if type(authorization) is not kind:
        raise ValueError(_ERROR)
    result = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation=operation_name,
        expected_operation_fingerprint=operation,
        expected_phase=phase,
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed,
    )
    if result.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise ValueError(_ERROR)


def _create_test_authorization_sequence(
    *,
    profile: CutoverProfileV1,
    operation_fingerprint: str,
    authorizations: tuple[object, ...],
    observed_at_epoch: int,
) -> AuthorizationSequenceV1:
    try:
        body = _validated_test_body(
            profile,
            operation_fingerprint,
            authorizations,
            observed_at_epoch,
        )
    except Exception:
        raise CompositionContractError(_ERROR) from None
    value = object.__new__(AuthorizationSequenceV1)
    for name, item in body.items():
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "sequence_fingerprint",
        fingerprint("project-container-test-authorization-sequence-v1", body),
    )
    return value


def _validated_test_body(profile, operation, authorizations, observed):
    if (
        type(profile) is not CutoverProfileV1
        or CutoverProfileV1.from_mapping(profile.to_mapping()) != profile
        or not is_fingerprint(operation)
        or type(authorizations) is not tuple
        or len(authorizations) != len(AUTHORIZATION_PHASES)
        or type(observed) is not int
    ):
        raise ValueError(_ERROR)
    for authorization, (_kind, _operation, phase) in zip(
        authorizations, AUTHORIZATION_PHASES, strict=True
    ):
        if (
            type(authorization) is not TestSandboxAuthorizationV1
            or authorization.profile_fingerprint != profile.profile_fingerprint
            or authorization.operation_fingerprint != operation
            or authorization.phase != phase
            or observed >= authorization.expires_at_epoch
        ):
            raise ValueError(_ERROR)
    return {
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_fingerprint": fingerprint(
            "project-container-governing-master-v1",
            profile.governing_master_commit,
        ),
        "operator_fingerprint": profile.operator_fingerprint,
        "operation_fingerprint": operation,
        "authorization_fingerprints": tuple(
            fingerprint(
                "project-container-test-phase-authorization-v1",
                {
                    "expires_at_epoch": item.expires_at_epoch,
                    "operation_fingerprint": item.operation_fingerprint,
                    "phase": item.phase,
                    "profile_fingerprint": item.profile_fingerprint,
                },
            )
            for item in authorizations
        ),
        "expires_at_epoch": min(
            item.expires_at_epoch for item in authorizations
        ),
        "_sandbox_authorized": True,
    }
