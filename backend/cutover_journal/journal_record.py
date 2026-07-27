"""Deterministic create-only journal record value."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ._canonical import canonical_json, is_fingerprint, strict_json_object
from .errors import JournalContractError
from .record_schema import (
    JOURNAL_RECORD_ERROR,
    RECORD_BODY_KEYS,
    validate_record_body,
)


@dataclass(frozen=True, slots=True, init=False)
class JournalRecordV1:
    record_type: str = field(repr=False)
    sequence: int = field(repr=False)
    previous_record_hash: str = field(repr=False)
    step_code: str = field(repr=False)
    direction: str = field(repr=False)
    event_code: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    forward_authorization_fingerprint: str = field(repr=False)
    recovery_authorization_fingerprint: str = field(repr=False)
    owner_fingerprint: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
    before_observation_fingerprint: str = field(repr=False)
    expected_after_observation_fingerprint: str = field(repr=False)
    observed_effect_fingerprint: str = field(repr=False)
    effect_outcome: str = field(repr=False)
    record_hash: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("JournalRecordV1 requires validated construction")

    @classmethod
    def create(cls, value: object) -> JournalRecordV1:
        body = validate_record_body(value)
        record_hash = hashlib.sha256(
            canonical_json(body, code=JOURNAL_RECORD_ERROR)
        ).hexdigest()
        return cls.from_mapping({**body, "record_hash": record_hash})

    @classmethod
    def from_mapping(cls, value: object) -> JournalRecordV1:
        source = _exact_record_mapping(value)
        body = {key: source[key] for key in RECORD_BODY_KEYS}
        normalized = validate_record_body(body)
        expected = hashlib.sha256(
            canonical_json(normalized, code=JOURNAL_RECORD_ERROR)
        ).hexdigest()
        if source["record_hash"] != expected:
            raise JournalContractError(JOURNAL_RECORD_ERROR)
        record = object.__new__(cls)
        for name in RECORD_BODY_KEYS:
            object.__setattr__(record, name, normalized[name])
        object.__setattr__(record, "record_hash", expected)
        return record

    @classmethod
    def from_json(cls, payload: object) -> JournalRecordV1:
        value = strict_json_object(payload, code=JOURNAL_RECORD_ERROR)
        if canonical_json(value, code=JOURNAL_RECORD_ERROR) != payload:
            raise JournalContractError(JOURNAL_RECORD_ERROR)
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            "record_type": self.record_type,
            "sequence": self.sequence,
            "previous_record_hash": self.previous_record_hash,
            "step_code": self.step_code,
            "direction": self.direction,
            "event_code": self.event_code,
            "governing_master_commit": self.governing_master_commit,
            "operation_fingerprint": self.operation_fingerprint,
            "profile_fingerprint": self.profile_fingerprint,
            "forward_authorization_fingerprint": (
                self.forward_authorization_fingerprint
            ),
            "recovery_authorization_fingerprint": (
                self.recovery_authorization_fingerprint
            ),
            "owner_fingerprint": self.owner_fingerprint,
            "authorization_fingerprint": self.authorization_fingerprint,
            "before_observation_fingerprint": (
                self.before_observation_fingerprint
            ),
            "expected_after_observation_fingerprint": (
                self.expected_after_observation_fingerprint
            ),
            "observed_effect_fingerprint": (
                self.observed_effect_fingerprint
            ),
            "effect_outcome": self.effect_outcome,
            "record_hash": self.record_hash,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=JOURNAL_RECORD_ERROR)


def _exact_record_mapping(value: object) -> dict[str, object]:
    expected = (*RECORD_BODY_KEYS, "record_hash")
    if type(value) is not dict:
        raise JournalContractError(JOURNAL_RECORD_ERROR)
    keys = tuple(value.keys())
    if (
        any(type(key) is not str for key in keys)
        or len(keys) != len(expected)
        or frozenset(keys) != frozenset(expected)
        or not is_fingerprint(value["record_hash"])
    ):
        raise JournalContractError(JOURNAL_RECORD_ERROR)
    return value
