"""Four closed content-free ACL receipt schemas required by Issue #55."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import ClassVar

from .canonical import (
    canonical_json,
    exact_mapping,
    fingerprint,
    is_fingerprint,
)
from .errors import CutoverHostMutationError
from .roles import AclFailureCode, AclReceiptStatus


_ACL_ERROR = "acl_contract_invalid"
_BODY_KEYS = (
    "schema_version",
    "receipt_type",
    "status",
    "failure_code",
    "profile_fingerprint",
    "authorization_fingerprint",
    "policy_fingerprint",
    "observation_fingerprint",
    "accepted",
    "rejected",
    "observed_objects",
)


@dataclass(
    frozen=True,
    slots=True,
    init=False,
    repr=False,
    weakref_slot=True,
)
class _AclReceiptV1:
    schema_version: int
    receipt_type: str
    status: AclReceiptStatus
    failure_code: AclFailureCode
    profile_fingerprint: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
    policy_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    accepted: int
    rejected: int
    observed_objects: int
    receipt_fingerprint: str = field(repr=False)

    RECEIPT_TYPE: ClassVar[str] = ""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated ACL receipt required")

    @classmethod
    def create(
        cls,
        *,
        status: AclReceiptStatus,
        failure_code: AclFailureCode,
        profile_fingerprint: str,
        authorization_fingerprint: str,
        policy_fingerprint: str,
        observation_fingerprint: str,
        accepted: int,
        rejected: int,
        observed_objects: int,
    ) -> _AclReceiptV1:
        body = {
            "schema_version": 1,
            "receipt_type": cls.RECEIPT_TYPE,
            "status": status.value if type(status) is AclReceiptStatus else status,
            "failure_code": (
                failure_code.value
                if type(failure_code) is AclFailureCode
                else failure_code
            ),
            "profile_fingerprint": profile_fingerprint,
            "authorization_fingerprint": authorization_fingerprint,
            "policy_fingerprint": policy_fingerprint,
            "observation_fingerprint": observation_fingerprint,
            "accepted": accepted,
            "rejected": rejected,
            "observed_objects": observed_objects,
        }
        return cls.from_mapping(
            {
                **body,
                "receipt_fingerprint": fingerprint(
                    "acl-receipt-v1",
                    body,
                    code=_ACL_ERROR,
                ),
            }
        )

    @classmethod
    def from_mapping(cls, value: object) -> _AclReceiptV1:
        source = exact_mapping(
            value,
            (*_BODY_KEYS, "receipt_fingerprint"),
            code=_ACL_ERROR,
        )
        body = {key: source[key] for key in _BODY_KEYS}
        status, failure = _validate_receipt(cls, body)
        expected = fingerprint("acl-receipt-v1", body, code=_ACL_ERROR)
        if source["receipt_fingerprint"] != expected:
            _invalid()
        receipt = object.__new__(cls)
        for key in _BODY_KEYS:
            item = body[key]
            if key == "status":
                item = status
            elif key == "failure_code":
                item = failure
            object.__setattr__(receipt, key, item)
        object.__setattr__(receipt, "receipt_fingerprint", expected)
        return receipt

    @classmethod
    def from_json(cls, payload: object) -> _AclReceiptV1:
        if type(payload) is not bytes:
            _invalid()
        try:
            value = json.loads(payload)
        except (TypeError, ValueError, UnicodeError):
            _invalid()
        if canonical_json(value, code=_ACL_ERROR) != payload:
            _invalid()
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "receipt_type": self.receipt_type,
            "status": self.status.value,
            "failure_code": self.failure_code.value,
            "profile_fingerprint": self.profile_fingerprint,
            "authorization_fingerprint": self.authorization_fingerprint,
            "policy_fingerprint": self.policy_fingerprint,
            "observation_fingerprint": self.observation_fingerprint,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "observed_objects": self.observed_objects,
            "receipt_fingerprint": self.receipt_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=_ACL_ERROR)


class AclBaselineReceiptV1(_AclReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "AclBaselineReceiptV1"


class AclCompatibilityReceiptV1(_AclReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "AclCompatibilityReceiptV1"


class AclApplyReceiptV1(_AclReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "AclApplyReceiptV1"


class AclPostVerifyReceiptV1(_AclReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "AclPostVerifyReceiptV1"


def _validate_receipt(
    cls: type[_AclReceiptV1],
    body: dict[str, object],
) -> tuple[AclReceiptStatus, AclFailureCode]:
    try:
        status = AclReceiptStatus(body["status"])
        failure = AclFailureCode(body["failure_code"])
    except (TypeError, ValueError):
        _invalid()
    fingerprints = (
        "profile_fingerprint",
        "authorization_fingerprint",
        "policy_fingerprint",
        "observation_fingerprint",
    )
    counts = (body["accepted"], body["rejected"], body["observed_objects"])
    valid_status = (
        status is AclReceiptStatus.ACCEPTED
        and failure is AclFailureCode.NONE
        and counts[0:2] == (1, 0)
    ) or (
        status is AclReceiptStatus.REJECTED
        and failure is not AclFailureCode.NONE
        and counts[0:2] == (0, 1)
    )
    if (
        body["schema_version"] != 1
        or body["receipt_type"] != cls.RECEIPT_TYPE
        or any(not is_fingerprint(body[key]) for key in fingerprints)
        or any(type(item) is not int for item in counts)
        or not 0 <= counts[2] <= 1_000_000
        or not valid_status
    ):
        _invalid()
    return status, failure


def _invalid() -> None:
    raise CutoverHostMutationError(_ACL_ERROR)
