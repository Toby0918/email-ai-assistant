"""Strict canonical content-free repository journal records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .errors import RepositoryTransactionError
from .journal_types import (
    ForwardBoundary,
    RepositoryJournalDirection,
    RepositoryJournalEvent,
    RepositoryJournalOutcome,
    RepositoryMutationKind,
    ReverseBoundary,
)

_BODY_FIELDS = (
    "schema_version",
    "sequence",
    "previous_record_hash",
    "direction",
    "boundary",
    "mutation_kind",
    "mutation_index",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_commit",
    "authorization_fingerprint",
    "owner_fingerprint",
    "before_observation_fingerprint",
    "expected_after_observation_fingerprint",
    "observed_effect_fingerprint",
    "event",
    "outcome",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RepositoryJournalRecordV1:
    schema_version: int
    sequence: int
    previous_record_hash: str = field(repr=False)
    direction: str
    boundary: str
    mutation_kind: str
    mutation_index: int
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_commit: str = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
    owner_fingerprint: str = field(repr=False)
    before_observation_fingerprint: str = field(repr=False)
    expected_after_observation_fingerprint: str = field(repr=False)
    observed_effect_fingerprint: str = field(repr=False)
    event: str
    outcome: str
    record_hash: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated repository journal record required")

    @classmethod
    def create(cls, value: object) -> RepositoryJournalRecordV1:
        body = _validated_body(value)
        return _new_record(cls, body, _body_hash(body))

    @classmethod
    def from_mapping(cls, value: object) -> RepositoryJournalRecordV1:
        source = _exact_mapping(value, (*_BODY_FIELDS, "record_hash"))
        body = _validated_body({name: source[name] for name in _BODY_FIELDS})
        record_hash = source["record_hash"]
        if not _is_fingerprint(record_hash) or record_hash != _body_hash(body):
            _invalid()
        return _new_record(cls, body, record_hash)

    @classmethod
    def from_json(cls, payload: object) -> RepositoryJournalRecordV1:
        source = _strict_json(payload)
        record = cls.from_mapping(source)
        if record.to_canonical_json() != payload:
            _invalid()
        return record

    def to_mapping(self) -> dict[str, object]:
        return {
            **{name: getattr(self, name) for name in _BODY_FIELDS},
            "record_hash": self.record_hash,
        }

    def to_canonical_json(self) -> bytes:
        return _canonical_json(self.to_mapping())


def _validated_body(value: object) -> dict[str, object]:
    source = _exact_mapping(value, _BODY_FIELDS)
    if not _valid_scalar_fields(source) or not _valid_closed_fields(source):
        _invalid()
    if not _valid_event_matrix(source):
        _invalid()
    return {name: source[name] for name in _BODY_FIELDS}


def _valid_scalar_fields(source: dict[str, object]) -> bool:
    fingerprints = (
        "previous_record_hash",
        "operation_fingerprint",
        "profile_fingerprint",
        "authorization_fingerprint",
        "owner_fingerprint",
        "before_observation_fingerprint",
        "expected_after_observation_fingerprint",
        "observed_effect_fingerprint",
    )
    return (
        type(source["schema_version"]) is int
        and source["schema_version"] == 1
        and type(source["sequence"]) is int
        and 1 <= source["sequence"] <= 1_000_000
        and type(source["mutation_index"]) is int
        and 1 <= source["mutation_index"] <= 1_000_000
        and all(_is_fingerprint(source[name]) for name in fingerprints)
        and _is_commit(source["governing_master_commit"])
    )


def _valid_closed_fields(source: dict[str, object]) -> bool:
    direction = source["direction"]
    boundary = source["boundary"]
    allowed_boundaries = (
        {item.value for item in ForwardBoundary}
        if direction == RepositoryJournalDirection.FORWARD.value
        else {item.value for item in ReverseBoundary}
    )
    return (
        direction in {item.value for item in RepositoryJournalDirection}
        and boundary in allowed_boundaries
        and source["mutation_kind"]
        in {item.value for item in RepositoryMutationKind}
        and source["event"] in {item.value for item in RepositoryJournalEvent}
        and source["outcome"]
        in {item.value for item in RepositoryJournalOutcome}
    )


def _valid_event_matrix(source: dict[str, object]) -> bool:
    event = source["event"]
    outcome = source["outcome"]
    observed = source["observed_effect_fingerprint"]
    expected = source["expected_after_observation_fingerprint"]
    if event == RepositoryJournalEvent.INTENT.value:
        return (
            outcome == RepositoryJournalOutcome.PENDING.value
            and observed == "0" * 64
        )
    if event == RepositoryJournalEvent.ABORTED.value:
        return (
            outcome == RepositoryJournalOutcome.NOT_APPLIED.value
            and observed == source["before_observation_fingerprint"]
        )
    return (
        outcome == RepositoryJournalOutcome.APPLIED.value
        and observed != "0" * 64
    )


def _new_record(cls, body, record_hash):
    record = object.__new__(cls)
    for name in _BODY_FIELDS:
        object.__setattr__(record, name, body[name])
    object.__setattr__(record, "record_hash", record_hash)
    return record


def _strict_json(payload: object) -> dict[str, object]:
    if type(payload) is not bytes or len(payload) > 16_384:
        _invalid()
    try:
        return json.loads(payload.decode("ascii"), object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        _invalid()


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if type(key) is not str or key in result:
            _invalid()
        result[key] = value
    return result


def _exact_mapping(
    value: object, fields: tuple[str, ...]
) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(fields):
        _invalid()
    if any(type(key) is not str for key in value):
        _invalid()
    return value


def _body_hash(body: dict[str, object]) -> str:
    return hashlib.sha256(_canonical_json(body)).hexdigest()


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        _invalid()


def _is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_commit(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _invalid() -> None:
    raise RepositoryTransactionError("repository_journal_invalid")
