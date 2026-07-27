"""Pre-mutation binding of forward and recovery authorization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ._canonical import (
    canonical_json,
    is_commit,
    is_fingerprint,
    is_opaque_fingerprint,
    strict_json_object,
)
from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
    validate_real_host_authorization,
)
from .errors import JournalContractError


BINDING_ERROR = "JOURNAL_AUTHORIZATION_INVALID"
BINDING_BODY_KEYS = (
    "governing_master_commit",
    "operator_fingerprint",
    "operation_fingerprint",
    "profile_fingerprint",
    "forward_authorization_fingerprint",
    "recovery_authorization_fingerprint",
    "owner_fingerprint",
)


@dataclass(frozen=True, slots=True, init=False)
class JournalOperationBindingV1:
    governing_master_commit: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    forward_authorization_fingerprint: str = field(repr=False)
    recovery_authorization_fingerprint: str = field(repr=False)
    owner_fingerprint: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("JournalOperationBindingV1 requires validated construction")

    @classmethod
    def create(
        cls,
        *,
        profile: CutoverProfileV1,
        forward_authorization: CutoverExecutionAuthorizationV1,
        recovery_authorization: RecoveryAuthorizationV1,
        owner_fingerprint: str,
        observed_at_epoch: int,
    ) -> JournalOperationBindingV1:
        _validate_authorizations(
            profile,
            forward_authorization,
            recovery_authorization,
            observed_at_epoch,
        )
        if not is_opaque_fingerprint(owner_fingerprint):
            _invalid()
        body = {
            "governing_master_commit": profile.governing_master_commit,
            "operator_fingerprint": profile.operator_fingerprint,
            "operation_fingerprint": forward_authorization.operation_fingerprint,
            "profile_fingerprint": profile.profile_fingerprint,
            "forward_authorization_fingerprint": (
                forward_authorization.authorization_fingerprint
            ),
            "recovery_authorization_fingerprint": (
                recovery_authorization.authorization_fingerprint
            ),
            "owner_fingerprint": owner_fingerprint,
        }
        fingerprint = hashlib.sha256(
            canonical_json(body, code=BINDING_ERROR)
        ).hexdigest()
        return cls.from_mapping({**body, "binding_fingerprint": fingerprint})

    @classmethod
    def from_mapping(cls, value: object) -> JournalOperationBindingV1:
        source = _exact_mapping(value)
        body = {name: source[name] for name in BINDING_BODY_KEYS}
        if not _valid_body(body):
            _invalid()
        expected = hashlib.sha256(
            canonical_json(body, code=BINDING_ERROR)
        ).hexdigest()
        if source["binding_fingerprint"] != expected:
            _invalid()
        binding = object.__new__(cls)
        for name in BINDING_BODY_KEYS:
            object.__setattr__(binding, name, body[name])
        object.__setattr__(binding, "binding_fingerprint", expected)
        return binding

    @classmethod
    def from_json(cls, payload: object) -> JournalOperationBindingV1:
        value = strict_json_object(payload, code=BINDING_ERROR)
        if canonical_json(value, code=BINDING_ERROR) != payload:
            _invalid()
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, str]:
        return {
            "governing_master_commit": self.governing_master_commit,
            "operator_fingerprint": self.operator_fingerprint,
            "operation_fingerprint": self.operation_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "forward_authorization_fingerprint": (
                self.forward_authorization_fingerprint
            ),
            "recovery_authorization_fingerprint": (
                self.recovery_authorization_fingerprint
            ),
            "owner_fingerprint": self.owner_fingerprint,
            "binding_fingerprint": self.binding_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=BINDING_ERROR)


def profile_matches_binding(
    profile: object,
    binding: object,
) -> bool:
    if (
        type(profile) is not CutoverProfileV1
        or type(binding) is not JournalOperationBindingV1
    ):
        return False
    try:
        intact_profile = CutoverProfileV1.from_mapping(
            profile.to_mapping()
        )
        intact_binding = JournalOperationBindingV1.from_mapping(
            binding.to_mapping()
        )
    except Exception:
        return False
    return (
        intact_profile.profile_fingerprint
        == intact_binding.profile_fingerprint
        and intact_profile.governing_master_commit
        == intact_binding.governing_master_commit
        and intact_profile.operator_fingerprint
        == intact_binding.operator_fingerprint
    )


def _validate_authorizations(
    profile: object,
    forward: object,
    recovery: object,
    observed_at_epoch: object,
) -> None:
    if (
        type(profile) is not CutoverProfileV1
        or type(forward) is not CutoverExecutionAuthorizationV1
        or type(recovery) is not RecoveryAuthorizationV1
        or type(observed_at_epoch) is not int
        or forward.operation_fingerprint != recovery.operation_fingerprint
    ):
        _invalid()
    common = {
        "profile": profile,
        "expected_operator_fingerprint": profile.operator_fingerprint,
        "observed_at_epoch": observed_at_epoch,
    }
    forward_result = validate_real_host_authorization(
        forward,
        expected_operation="cutover_execution",
        expected_operation_fingerprint=forward.operation_fingerprint,
        expected_phase="execute",
        **common,
    )
    recovery_result = validate_real_host_authorization(
        recovery,
        expected_operation="recovery",
        expected_operation_fingerprint=recovery.operation_fingerprint,
        expected_phase="rollback",
        **common,
    )
    if (
        forward_result.status is not AuthorizationValidationStatus.AUTHORIZED
        or recovery_result.status is not AuthorizationValidationStatus.AUTHORIZED
    ):
        _invalid()


def _valid_body(value: dict[str, object]) -> bool:
    fingerprints = BINDING_BODY_KEYS[1:]
    return (
        is_commit(value["governing_master_commit"])
        and all(is_opaque_fingerprint(value[name]) for name in fingerprints)
        and value["forward_authorization_fingerprint"]
        != value["recovery_authorization_fingerprint"]
    )


def _exact_mapping(value: object) -> dict[str, object]:
    expected = (*BINDING_BODY_KEYS, "binding_fingerprint")
    if type(value) is not dict:
        _invalid()
    keys = tuple(value.keys())
    if (
        any(type(key) is not str for key in keys)
        or len(keys) != len(expected)
        or frozenset(keys) != frozenset(expected)
        or not is_fingerprint(value["binding_fingerprint"])
    ):
        _invalid()
    return value


def _invalid() -> None:
    raise JournalContractError(BINDING_ERROR)
