"""Strict content-free receipts for managed publication."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import ClassVar

from .canonical import canonical_json, fail, is_commit, is_fingerprint

_ERROR = "managed_activation_receipt_invalid"
_BODY_KEYS = (
    "schema_version",
    "receipt_type",
    "status",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_commit",
    "authorization_fingerprint",
    "role",
    "input_fingerprints",
    "observation_fingerprint",
    "counts",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class _PublicationReceiptV1:
    schema_version: int
    receipt_type: str
    status: str
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
    role: str
    input_fingerprints: tuple[str, ...] = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    counts: tuple[tuple[str, int], ...]
    receipt_fingerprint: str = field(repr=False)

    RECEIPT_TYPE: ClassVar[str] = ""
    ROLE: ClassVar[str] = ""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("publication receipt requires validated construction")

    @classmethod
    def create(
        cls,
        *,
        operation_fingerprint: object,
        profile_fingerprint: object,
        governing_master_commit: object,
        authorization_fingerprint: object,
        input_fingerprints: object,
        observation_fingerprint: object,
        counts: object,
    ):
        body = _validated_body(
            cls,
            {
                "schema_version": 1,
                "receipt_type": cls.RECEIPT_TYPE,
                "status": "PUBLISHED",
                "operation_fingerprint": operation_fingerprint,
                "profile_fingerprint": profile_fingerprint,
                "governing_master_commit": governing_master_commit,
                "authorization_fingerprint": authorization_fingerprint,
                "role": cls.ROLE,
                "input_fingerprints": input_fingerprints,
                "observation_fingerprint": observation_fingerprint,
                "counts": counts,
            },
        )
        receipt_hash = hashlib.sha256(
            canonical_json(body, code=_ERROR)
        ).hexdigest()
        return cls.from_mapping(
            {**body, "receipt_fingerprint": receipt_hash}
        )

    @classmethod
    def from_mapping(cls, value: object):
        if type(value) is not dict:
            fail(_ERROR)
        expected = (*_BODY_KEYS, "receipt_fingerprint")
        if set(value) != set(expected):
            fail(_ERROR)
        body = _validated_body(
            cls, {name: value[name] for name in _BODY_KEYS}
        )
        receipt_hash = value["receipt_fingerprint"]
        expected_hash = hashlib.sha256(
            canonical_json(body, code=_ERROR)
        ).hexdigest()
        if not is_fingerprint(receipt_hash) or receipt_hash != expected_hash:
            fail(_ERROR)
        receipt = object.__new__(cls)
        for name in _BODY_KEYS:
            normalized = body[name]
            if name == "input_fingerprints":
                normalized = tuple(normalized)
            elif name == "counts":
                normalized = tuple(sorted(normalized.items()))
            object.__setattr__(receipt, name, normalized)
        object.__setattr__(receipt, "receipt_fingerprint", expected_hash)
        return receipt

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "receipt_type": self.receipt_type,
            "status": self.status,
            "operation_fingerprint": self.operation_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "governing_master_commit": self.governing_master_commit,
            "authorization_fingerprint": self.authorization_fingerprint,
            "role": self.role,
            "input_fingerprints": list(self.input_fingerprints),
            "observation_fingerprint": self.observation_fingerprint,
            "counts": dict(self.counts),
            "receipt_fingerprint": self.receipt_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=_ERROR)


class ManagedRuntimeReceiptV1(_PublicationReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "ManagedRuntimeReceiptV1"
    ROLE = "runtime"


class StoppedDatabaseCopyReceiptV1(_PublicationReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "StoppedDatabaseCopyReceiptV1"
    ROLE = "database"


class CrxPublicationReceiptV1(_PublicationReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "CrxPublicationReceiptV1"
    ROLE = "browser_extension"


class ConfigPublicationReceiptV1(_PublicationReceiptV1):
    __slots__ = ()
    RECEIPT_TYPE = "ConfigPublicationReceiptV1"
    ROLE = "config"


def _validated_body(cls: type, value: dict[str, object]) -> dict[str, object]:
    if (
        set(value) != set(_BODY_KEYS)
        or value["schema_version"] != 1
        or value["receipt_type"] != cls.RECEIPT_TYPE
        or value["status"] != "PUBLISHED"
        or value["role"] != cls.ROLE
        or not is_fingerprint(value["operation_fingerprint"])
        or not is_fingerprint(value["profile_fingerprint"])
        or not is_commit(value["governing_master_commit"])
        or not is_fingerprint(value["authorization_fingerprint"])
        or not is_fingerprint(value["observation_fingerprint"])
        or not _valid_inputs(value["input_fingerprints"])
        or not _valid_counts(value["counts"])
    ):
        fail(_ERROR)
    return {
        **value,
        "input_fingerprints": list(value["input_fingerprints"]),
        "counts": {
            "published": value["counts"]["published"],
            "rejected": value["counts"]["rejected"],
        },
    }


def _valid_inputs(value: object) -> bool:
    return (
        type(value) in {tuple, list}
        and 1 <= len(value) <= 16
        and all(is_fingerprint(item) for item in value)
        and len(set(value)) == len(value)
    )


def _valid_counts(value: object) -> bool:
    return (
        type(value) is dict
        and set(value) == {"published", "rejected"}
        and value["published"] == 1
        and value["rejected"] == 0
    )


RECEIPT_TYPES = (
    ManagedRuntimeReceiptV1,
    StoppedDatabaseCopyReceiptV1,
    CrxPublicationReceiptV1,
    ConfigPublicationReceiptV1,
)
