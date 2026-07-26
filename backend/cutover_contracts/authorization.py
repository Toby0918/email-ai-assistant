"""Nominal, externally supplied real-host authorization values."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar

from ._canonical import canonical_json, strict_json_object
from .authorization_schema import (
    AUTHORIZATION_BODY_KEYS,
    AUTHORIZATION_ERROR,
    validate_authorization_body,
)
from .errors import CutoverContractError


@dataclass(frozen=True, slots=True, init=False)
class _RealAuthorizationV1:
    authorization_type: str = field(repr=False)
    operation: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    phase: str = field(repr=False)
    issued_at_epoch: int = field(repr=False)
    not_before_epoch: int = field(repr=False)
    expires_at_epoch: int = field(repr=False)
    authorization_fingerprint: str = field(repr=False)

    AUTHORIZATION_TYPE: ClassVar[str] = ""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("real authorization requires external canonical input")

    @classmethod
    def from_mapping(cls, value: object) -> _RealAuthorizationV1:
        if type(value) is not dict:
            raise CutoverContractError(AUTHORIZATION_ERROR)
        expected_keys = set(AUTHORIZATION_BODY_KEYS) | {
            "authorization_fingerprint"
        }
        if set(value) != expected_keys:
            raise CutoverContractError(AUTHORIZATION_ERROR)
        body = {key: value[key] for key in AUTHORIZATION_BODY_KEYS}
        normalized = validate_authorization_body(
            body, expected_type=cls.AUTHORIZATION_TYPE
        )
        fingerprint = value["authorization_fingerprint"]
        expected = hashlib.sha256(canonical_json(normalized)).hexdigest()
        if fingerprint != expected:
            raise CutoverContractError(AUTHORIZATION_ERROR)
        authorization = object.__new__(cls)
        for name in AUTHORIZATION_BODY_KEYS:
            object.__setattr__(authorization, name, normalized[name])
        object.__setattr__(
            authorization, "authorization_fingerprint", expected
        )
        return authorization

    @classmethod
    def from_json(cls, payload: object) -> _RealAuthorizationV1:
        value = strict_json_object(payload, code=AUTHORIZATION_ERROR)
        if canonical_json(value) != payload:
            raise CutoverContractError(AUTHORIZATION_ERROR)
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in (
                *AUTHORIZATION_BODY_KEYS,
                "authorization_fingerprint",
            )
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


class RealPreflightAuthorizationV1(_RealAuthorizationV1):
    __slots__ = ()
    AUTHORIZATION_TYPE = "RealPreflightAuthorizationV1"


class EvidencePublicationAuthorizationV1(_RealAuthorizationV1):
    __slots__ = ()
    AUTHORIZATION_TYPE = "EvidencePublicationAuthorizationV1"


class CutoverExecutionAuthorizationV1(_RealAuthorizationV1):
    __slots__ = ()
    AUTHORIZATION_TYPE = "CutoverExecutionAuthorizationV1"


class RecoveryAuthorizationV1(_RealAuthorizationV1):
    __slots__ = ()
    AUTHORIZATION_TYPE = "RecoveryAuthorizationV1"


REAL_AUTHORIZATION_TYPES = (
    RealPreflightAuthorizationV1,
    EvidencePublicationAuthorizationV1,
    CutoverExecutionAuthorizationV1,
    RecoveryAuthorizationV1,
)
