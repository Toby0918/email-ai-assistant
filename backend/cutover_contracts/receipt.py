"""Deterministic canonical content-free receipt envelope."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ._canonical import canonical_json, strict_json_object
from .errors import CutoverContractError
from .receipt_schema import (
    RECEIPT_BODY_KEYS,
    RECEIPT_ERROR,
    _exact_dict,
    validate_receipt_body,
)
from .profile_schema import _is_fingerprint


@dataclass(frozen=True, slots=True, repr=False)
class _FrozenObject:
    items: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True, repr=False)
class _FrozenArray:
    items: tuple[object, ...]


@dataclass(frozen=True, slots=True, init=False)
class ReceiptEnvelopeV1:
    receipt_type: str = field(repr=False)
    status: str = field(repr=False)
    operation: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
    producer: str = field(repr=False)
    subject_role: str = field(repr=False)
    input_fingerprints: _FrozenArray = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    counts: _FrozenObject = field(repr=False)
    validity: _FrozenObject = field(repr=False)
    details: _FrozenObject = field(repr=False)
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ReceiptEnvelopeV1 requires validated construction")

    @classmethod
    def create(cls, value: object) -> ReceiptEnvelopeV1:
        body = validate_receipt_body(value)
        fingerprint = hashlib.sha256(
            canonical_json(body, code=RECEIPT_ERROR)
        ).hexdigest()
        return cls.from_mapping(
            {**body, "receipt_fingerprint": fingerprint}
        )

    @classmethod
    def from_mapping(cls, value: object) -> ReceiptEnvelopeV1:
        source = _exact_dict(
            value,
            (*RECEIPT_BODY_KEYS, "receipt_fingerprint"),
        )
        body = {key: source[key] for key in RECEIPT_BODY_KEYS}
        normalized = validate_receipt_body(body)
        fingerprint = source["receipt_fingerprint"]
        if not _is_fingerprint(fingerprint):
            raise CutoverContractError(RECEIPT_ERROR)
        expected = hashlib.sha256(
            canonical_json(normalized, code=RECEIPT_ERROR)
        ).hexdigest()
        if fingerprint != expected:
            raise CutoverContractError(RECEIPT_ERROR)
        receipt = object.__new__(cls)
        for name in RECEIPT_BODY_KEYS:
            object.__setattr__(receipt, name, _freeze(normalized[name]))
        object.__setattr__(receipt, "receipt_fingerprint", expected)
        return receipt

    @classmethod
    def from_json(cls, payload: object) -> ReceiptEnvelopeV1:
        value = strict_json_object(payload, code=RECEIPT_ERROR)
        if canonical_json(value, code=RECEIPT_ERROR) != payload:
            raise CutoverContractError(RECEIPT_ERROR)
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            "receipt_type": self.receipt_type,
            "status": self.status,
            "operation": self.operation,
            "operation_fingerprint": self.operation_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "governing_master_commit": self.governing_master_commit,
            "authorization_fingerprint": self.authorization_fingerprint,
            "producer": self.producer,
            "subject_role": self.subject_role,
            "input_fingerprints": _thaw(self.input_fingerprints),
            "observation_fingerprint": self.observation_fingerprint,
            "counts": _thaw(self.counts),
            "validity": _thaw(self.validity),
            "details": _thaw(self.details),
            "receipt_fingerprint": self.receipt_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=RECEIPT_ERROR)


def _freeze(value: object) -> object:
    if type(value) is dict:
        return _FrozenObject(
            tuple((key, _freeze(value[key])) for key in sorted(value))
        )
    if type(value) is list:
        return _FrozenArray(tuple(_freeze(item) for item in value))
    return value


def _thaw(value: object) -> object:
    if type(value) is _FrozenObject:
        return {key: _thaw(item) for key, item in value.items}
    if type(value) is _FrozenArray:
        return [_thaw(item) for item in value.items]
    return value
