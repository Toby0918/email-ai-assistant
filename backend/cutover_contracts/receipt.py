"""Deterministic canonical content-free receipt envelope."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ._canonical import canonical_json, strict_json_object
from .errors import CutoverContractError
from .receipt_schema import (
    RECEIPT_BODY_KEYS,
    RECEIPT_ERROR,
    validate_receipt_body,
)


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
        fingerprint = hashlib.sha256(canonical_json(body)).hexdigest()
        return cls.from_mapping(
            {**body, "receipt_fingerprint": fingerprint}
        )

    @classmethod
    def from_mapping(cls, value: object) -> ReceiptEnvelopeV1:
        if type(value) is not dict:
            raise CutoverContractError(RECEIPT_ERROR)
        expected_keys = set(RECEIPT_BODY_KEYS) | {"receipt_fingerprint"}
        if set(value) != expected_keys:
            raise CutoverContractError(RECEIPT_ERROR)
        body = {key: value[key] for key in RECEIPT_BODY_KEYS}
        normalized = validate_receipt_body(body)
        fingerprint = value["receipt_fingerprint"]
        expected = hashlib.sha256(canonical_json(normalized)).hexdigest()
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
        if canonical_json(value) != payload:
            raise CutoverContractError(RECEIPT_ERROR)
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            name: _thaw(getattr(self, name))
            for name in (*RECEIPT_BODY_KEYS, "receipt_fingerprint")
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


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
