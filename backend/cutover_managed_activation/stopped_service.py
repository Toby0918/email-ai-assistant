"""Strict stopped-service evidence accepted by the database copier."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .canonical import canonical_json, fail, is_commit, is_fingerprint

_ERROR = "stopped_service_receipt_invalid"
_BODY_KEYS = (
    "schema_version",
    "receipt_type",
    "status",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_commit",
    "authorization_fingerprint",
    "service_role_fingerprint",
    "database_source_fingerprint",
    "observation_fingerprint",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class StoppedServiceReceiptV1:
    schema_version: int
    receipt_type: str
    status: str
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
    service_role_fingerprint: str = field(repr=False)
    database_source_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("stopped receipt requires validated construction")

    @classmethod
    def create(cls, **values: object) -> StoppedServiceReceiptV1:
        body = _validated(
            {
                "schema_version": 1,
                "receipt_type": "StoppedServiceReceiptV1",
                "status": "STOPPED",
                **values,
            }
        )
        receipt_hash = hashlib.sha256(
            canonical_json(body, code=_ERROR)
        ).hexdigest()
        return cls.from_mapping(
            {**body, "receipt_fingerprint": receipt_hash}
        )

    @classmethod
    def from_mapping(cls, value: object) -> StoppedServiceReceiptV1:
        if (
            type(value) is not dict
            or set(value) != {*_BODY_KEYS, "receipt_fingerprint"}
        ):
            fail(_ERROR)
        body = _validated({name: value[name] for name in _BODY_KEYS})
        receipt_hash = value["receipt_fingerprint"]
        expected = hashlib.sha256(
            canonical_json(body, code=_ERROR)
        ).hexdigest()
        if not is_fingerprint(receipt_hash) or receipt_hash != expected:
            fail(_ERROR)
        receipt = object.__new__(cls)
        for name in _BODY_KEYS:
            object.__setattr__(receipt, name, body[name])
        object.__setattr__(receipt, "receipt_fingerprint", expected)
        return receipt

    def to_mapping(self) -> dict[str, object]:
        return {
            **{name: getattr(self, name) for name in _BODY_KEYS},
            "receipt_fingerprint": self.receipt_fingerprint,
        }


def _validated(value: dict[str, object]) -> dict[str, object]:
    fingerprints = (
        "operation_fingerprint",
        "profile_fingerprint",
        "authorization_fingerprint",
        "service_role_fingerprint",
        "database_source_fingerprint",
        "observation_fingerprint",
    )
    if (
        set(value) != set(_BODY_KEYS)
        or value["schema_version"] != 1
        or value["receipt_type"] != "StoppedServiceReceiptV1"
        or value["status"] != "STOPPED"
        or not is_commit(value["governing_master_commit"])
        or any(not is_fingerprint(value[name]) for name in fingerprints)
    ):
        fail(_ERROR)
    return dict(value)
