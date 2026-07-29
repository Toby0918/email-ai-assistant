"""Narrow managed Runtime, database, artifact, and Config composition."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .adapters import ManagedActivationAdapters, has_exact_adapter_bundle
from .canonical import canonical_json, fail, is_commit, is_fingerprint
from .errors import ManagedActivationError
from .receipts import RECEIPT_TYPES

_ERROR = "managed_activation_phase_invalid"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ManagedActivationPhase:
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ManagedActivationPhase requires create()")

    @classmethod
    def create(
        cls,
        *,
        operation_fingerprint: object,
        profile_fingerprint: object,
        governing_master_commit: object,
        authorization_fingerprint: object,
    ) -> ManagedActivationPhase:
        if (
            not is_fingerprint(operation_fingerprint)
            or not is_fingerprint(profile_fingerprint)
            or not is_commit(governing_master_commit)
            or not is_fingerprint(authorization_fingerprint)
        ):
            fail(_ERROR)
        phase = object.__new__(cls)
        object.__setattr__(
            phase, "operation_fingerprint", operation_fingerprint
        )
        object.__setattr__(phase, "profile_fingerprint", profile_fingerprint)
        object.__setattr__(
            phase, "governing_master_commit", governing_master_commit
        )
        object.__setattr__(
            phase, "authorization_fingerprint", authorization_fingerprint
        )
        return phase

    def publish(
        self, adapters: object
    ) -> ManagedActivationReceiptSetV1:
        if not has_exact_adapter_bundle(adapters):
            fail(_ERROR)
        try:
            callbacks = (
                adapters.runtime.publish_runtime,
                adapters.database.copy_stopped_database,
                adapters.artifact.publish_crx,
                adapters.config.publish_config,
            )
            receipts = []
            for index, callback in enumerate(callbacks):
                receipt = callback()
                self._validate_receipt(index, receipt)
                receipts.append(receipt)
            return ManagedActivationReceiptSetV1.create(
                receipts=tuple(receipts)
            )
        except ManagedActivationError:
            raise
        except Exception:
            fail("managed_activation_publication_failed")

    def _validate_receipt(self, index: int, receipt: object) -> None:
        if type(receipt) is not RECEIPT_TYPES[index]:
            fail(_ERROR)
        rebuilt = type(receipt).from_mapping(receipt.to_mapping())
        if rebuilt != receipt or not self._matches(receipt):
            fail(_ERROR)

    def _matches(self, receipt: object) -> bool:
        return (
            receipt.operation_fingerprint == self.operation_fingerprint
            and receipt.profile_fingerprint == self.profile_fingerprint
            and receipt.governing_master_commit
            == self.governing_master_commit
            and receipt.authorization_fingerprint
            == self.authorization_fingerprint
        )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ManagedActivationReceiptSetV1:
    receipts: tuple[object, object, object, object] = field(repr=False)
    published: int
    rejected: int
    receipt_set_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ManagedActivationReceiptSetV1 requires create()")

    @classmethod
    def create(cls, *, receipts: object):
        validated = _validated_receipts(receipts)
        body = _receipt_set_body(validated)
        fingerprint = hashlib.sha256(
            canonical_json(body, code=_ERROR)
        ).hexdigest()
        return _build_receipt_set(cls, validated, fingerprint)

    @classmethod
    def from_mapping(cls, value: object):
        if (
            type(value) is not dict
            or set(value)
            != {
                "schema_version",
                "receipt_set_type",
                "operation_fingerprint",
                "profile_fingerprint",
                "governing_master_commit",
                "authorization_fingerprint",
                "receipts",
                "published",
                "rejected",
                "receipt_set_fingerprint",
            }
            or value["published"] != 4
            or value["rejected"] != 0
        ):
            fail(_ERROR)
        receipts = _parse_receipts(value["receipts"])
        body = _receipt_set_body(receipts)
        expected = hashlib.sha256(
            canonical_json(body, code=_ERROR)
        ).hexdigest()
        supplied = value["receipt_set_fingerprint"]
        if (
            any(value[name] != body[name] for name in body)
            or not is_fingerprint(supplied)
            or supplied != expected
        ):
            fail(_ERROR)
        return _build_receipt_set(cls, receipts, expected)

    def to_mapping(self) -> dict[str, object]:
        return {
            **_receipt_set_body(self.receipts),
            "receipt_set_fingerprint": self.receipt_set_fingerprint,
        }

    @property
    def receipt_fingerprints(self) -> tuple[str, str, str, str]:
        return tuple(receipt.receipt_fingerprint for receipt in self.receipts)


    @property
    def operation_fingerprint(self) -> str:
        return self.receipts[0].operation_fingerprint

    @property
    def profile_fingerprint(self) -> str:
        return self.receipts[0].profile_fingerprint

    @property
    def governing_master_commit(self) -> str:
        return self.receipts[0].governing_master_commit

    @property
    def authorization_fingerprint(self) -> str:
        return self.receipts[0].authorization_fingerprint


def _validated_receipts(value: object):
    if type(value) not in {tuple, list} or len(value) != 4:
        fail(_ERROR)
    result = []
    for index, receipt in enumerate(value):
        if type(receipt) is not RECEIPT_TYPES[index]:
            fail(_ERROR)
        rebuilt = type(receipt).from_mapping(receipt.to_mapping())
        if rebuilt != receipt:
            fail(_ERROR)
        result.append(rebuilt)
    chain = (
        "operation_fingerprint",
        "profile_fingerprint",
        "governing_master_commit",
        "authorization_fingerprint",
    )
    if any(
        len({getattr(receipt, name) for receipt in result}) != 1
        for name in chain
    ) or len({receipt.receipt_fingerprint for receipt in result}) != 4:
        fail(_ERROR)
    return tuple(result)


def _parse_receipts(value: object):
    if type(value) is not list or len(value) != 4:
        fail(_ERROR)
    try:
        receipts = tuple(
            receipt_type.from_mapping(item)
            for receipt_type, item in zip(RECEIPT_TYPES, value, strict=True)
        )
    except (ManagedActivationError, TypeError, ValueError):
        fail(_ERROR)
    return _validated_receipts(receipts)


def _receipt_set_body(receipts) -> dict[str, object]:
    return {
        "schema_version": 1,
        "receipt_set_type": "ManagedActivationReceiptSetV1",
        "operation_fingerprint": receipts[0].operation_fingerprint,
        "profile_fingerprint": receipts[0].profile_fingerprint,
        "governing_master_commit": receipts[0].governing_master_commit,
        "authorization_fingerprint": receipts[0].authorization_fingerprint,
        "receipts": [receipt.to_mapping() for receipt in receipts],
        "published": 4,
        "rejected": 0,
    }


def _build_receipt_set(cls, receipts, fingerprint):
    value = object.__new__(cls)
    object.__setattr__(value, "receipts", receipts)
    object.__setattr__(value, "published", 4)
    object.__setattr__(value, "rejected", 0)
    object.__setattr__(value, "receipt_set_fingerprint", fingerprint)
    return value
