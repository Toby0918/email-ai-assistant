"""Exact operation, Profile, master, and operator binding."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)

from .authorization_sequence import AuthorizationSequenceV1
from .canonical import fingerprint, is_fingerprint
from .errors import CompositionContractError


class OperatorEntryStatus(str, Enum):
    """Fixed content-free lock outcomes."""

    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"
    BLOCKED_AUTHORIZATION_MISSING = "BLOCKED_AUTHORIZATION_MISSING"
    BLOCKED_AUTHORIZATION_WRONG_TYPE = "BLOCKED_AUTHORIZATION_WRONG_TYPE"
    BLOCKED_AUTHORIZATION_NOT_YET_VALID = (
        "BLOCKED_AUTHORIZATION_NOT_YET_VALID"
    )
    BLOCKED_AUTHORIZATION_EXPIRED = "BLOCKED_AUTHORIZATION_EXPIRED"
    BLOCKED_AUTHORIZATION_WRONG_PROFILE = (
        "BLOCKED_AUTHORIZATION_WRONG_PROFILE"
    )
    BLOCKED_AUTHORIZATION_WRONG_MASTER = (
        "BLOCKED_AUTHORIZATION_WRONG_MASTER"
    )
    BLOCKED_AUTHORIZATION_WRONG_OPERATION = (
        "BLOCKED_AUTHORIZATION_WRONG_OPERATION"
    )
    BLOCKED_AUTHORIZATION_WRONG_OPERATOR = (
        "BLOCKED_AUTHORIZATION_WRONG_OPERATOR"
    )
    BLOCKED_AUTHORIZATION_WRONG_PHASE = (
        "BLOCKED_AUTHORIZATION_WRONG_PHASE"
    )
    BLOCKED_AUTHORIZATION_INVALID = "BLOCKED_AUTHORIZATION_INVALID"
    BLOCKED_TEST_AUTHORIZATION = "BLOCKED_TEST_AUTHORIZATION"


@dataclass(frozen=True, slots=True)
class OperatorEntryResult:
    """One fixed blocked result with no host evidence."""

    status: OperatorEntryStatus
    blocked: int
    executed: int


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CompositionBindingV1:
    """One immutable content-free composition binding."""

    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_fingerprint: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    authorization_sequence_fingerprint: str = field(repr=False)
    authorization_expires_at_epoch: int = field(repr=False)
    binding_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CompositionBindingV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        profile: CutoverProfileV1,
        operation_fingerprint: str,
        authorization_sequence: AuthorizationSequenceV1,
    ) -> CompositionBindingV1:
        try:
            body = _binding_body(
                profile,
                operation_fingerprint,
                authorization_sequence,
            )
        except Exception:
            raise CompositionContractError(
                "PROJECT_CONTAINER_COMPOSITION_BINDING_INVALID"
            ) from None
        value = object.__new__(cls)
        for name, item in body.items():
            object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "binding_fingerprint",
            fingerprint("project-container-composition-binding-v1", body),
        )
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            "operation_fingerprint": self.operation_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "governing_master_fingerprint": (
                self.governing_master_fingerprint
            ),
            "operator_fingerprint": self.operator_fingerprint,
            "authorization_sequence_fingerprint": (
                self.authorization_sequence_fingerprint
            ),
            "authorization_expires_at_epoch": (
                self.authorization_expires_at_epoch
            ),
            "binding_fingerprint": self.binding_fingerprint,
        }


def locked_operator_entry(
    *,
    profile: object,
    authorization: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
    authorization_type: type,
    operation: str,
    phase: str,
) -> OperatorEntryResult:
    """Validate an exact phase and grant no executable composition."""

    if authorization is None:
        return _blocked(OperatorEntryStatus.BLOCKED_AUTHORIZATION_MISSING)
    if type(authorization) is TestSandboxAuthorizationV1:
        return _blocked(OperatorEntryStatus.BLOCKED_TEST_AUTHORIZATION)
    if type(authorization) is not authorization_type:
        return _blocked(OperatorEntryStatus.BLOCKED_AUTHORIZATION_WRONG_TYPE)
    if (
        type(profile) is not CutoverProfileV1
        or type(operation_fingerprint) is not str
        or type(observed_at_epoch) is not int
    ):
        return _blocked(OperatorEntryStatus.BLOCKED_AUTHORIZATION_INVALID)
    try:
        validation = validate_real_host_authorization(
            authorization,
            profile=profile,
            expected_operation=operation,
            expected_operation_fingerprint=operation_fingerprint,
            expected_phase=phase,
            expected_operator_fingerprint=profile.operator_fingerprint,
            observed_at_epoch=observed_at_epoch,
        )
    except Exception:
        return _blocked(OperatorEntryStatus.BLOCKED_AUTHORIZATION_INVALID)
    if validation.status is AuthorizationValidationStatus.AUTHORIZED:
        return _blocked(OperatorEntryStatus.BLOCKED_NO_APPROVED_COMMAND)
    try:
        status = OperatorEntryStatus(validation.status.value)
    except ValueError:
        status = OperatorEntryStatus.BLOCKED_AUTHORIZATION_INVALID
    return _blocked(status)


def _blocked(status: OperatorEntryStatus) -> OperatorEntryResult:
    return OperatorEntryResult(status=status, blocked=1, executed=0)


def _binding_body(profile, operation, sequence):
    if (
        type(profile) is not CutoverProfileV1
        or CutoverProfileV1.from_mapping(profile.to_mapping()) != profile
        or not is_fingerprint(operation)
        or type(sequence) is not AuthorizationSequenceV1
    ):
        raise ValueError
    master = fingerprint(
        "project-container-governing-master-v1",
        profile.governing_master_commit,
    )
    expected = (
        profile.profile_fingerprint,
        master,
        profile.operator_fingerprint,
        operation,
    )
    actual = (
        sequence.profile_fingerprint,
        sequence.governing_master_fingerprint,
        sequence.operator_fingerprint,
        sequence.operation_fingerprint,
    )
    if actual != expected:
        raise ValueError
    return {
        "operation_fingerprint": operation,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_fingerprint": master,
        "operator_fingerprint": profile.operator_fingerprint,
        "authorization_sequence_fingerprint": (
            sequence.sequence_fingerprint
        ),
        "authorization_expires_at_epoch": sequence.expires_at_epoch,
    }
