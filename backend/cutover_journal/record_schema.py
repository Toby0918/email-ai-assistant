"""Closed schema for canonical journal records."""

from __future__ import annotations

from ._canonical import (
    ZERO_FINGERPRINT,
    is_commit,
    is_fingerprint,
    is_opaque_fingerprint,
)
from .errors import JournalContractError
from .journal_types import (
    JournalDirection,
    JournalEffectOutcome,
    JournalEventCode,
    JournalStepCode,
)


JOURNAL_RECORD_ERROR = "JOURNAL_RECORD_INVALID"
RECORD_BODY_KEYS = (
    "record_type",
    "sequence",
    "previous_record_hash",
    "step_code",
    "direction",
    "event_code",
    "governing_master_commit",
    "operation_fingerprint",
    "profile_fingerprint",
    "forward_authorization_fingerprint",
    "recovery_authorization_fingerprint",
    "owner_fingerprint",
    "authorization_fingerprint",
    "before_observation_fingerprint",
    "expected_after_observation_fingerprint",
    "observed_effect_fingerprint",
    "effect_outcome",
)


def validate_record_body(value: object) -> dict[str, object]:
    source = _exact_dict(value, RECORD_BODY_KEYS)
    if (
        type(source["record_type"]) is not str
        or source["record_type"] != "JournalRecordV1"
        or not _valid_sequence(source)
        or not _valid_codes(source)
        or not _valid_bindings(source)
        or not _valid_observations(source)
        or not _valid_event_state(source)
    ):
        _invalid()
    return {key: source[key] for key in RECORD_BODY_KEYS}


def _valid_sequence(source: dict[str, object]) -> bool:
    sequence = source["sequence"]
    previous = source["previous_record_hash"]
    return (
        type(sequence) is int
        and 1 <= sequence <= 1_000_000
        and is_fingerprint(previous)
        and (
            previous == ZERO_FINGERPRINT
            if sequence == 1
            else previous != ZERO_FINGERPRINT
        )
    )


def _valid_codes(source: dict[str, object]) -> bool:
    return (
        type(source["step_code"]) is str
        and source["step_code"] in {item.value for item in JournalStepCode}
        and type(source["direction"]) is str
        and source["direction"] in {item.value for item in JournalDirection}
        and type(source["event_code"]) is str
        and source["event_code"] in {item.value for item in JournalEventCode}
        and type(source["effect_outcome"]) is str
        and source["effect_outcome"]
        in {item.value for item in JournalEffectOutcome}
    )


def _valid_bindings(source: dict[str, object]) -> bool:
    fingerprint_fields = (
        "operation_fingerprint",
        "profile_fingerprint",
        "forward_authorization_fingerprint",
        "recovery_authorization_fingerprint",
        "owner_fingerprint",
        "authorization_fingerprint",
    )
    if (
        not is_commit(source["governing_master_commit"])
        or not all(
            is_opaque_fingerprint(source[name]) for name in fingerprint_fields
        )
        or source["forward_authorization_fingerprint"]
        == source["recovery_authorization_fingerprint"]
    ):
        return False
    authorization = source["authorization_fingerprint"]
    if source["direction"] == JournalDirection.REVERSE.value:
        return authorization == source["recovery_authorization_fingerprint"]
    if source["event_code"] == JournalEventCode.INTENT.value:
        return authorization != source[
            "recovery_authorization_fingerprint"
        ]
    if source["event_code"] == JournalEventCode.RESUME_BOUND.value:
        return authorization not in {
            source["forward_authorization_fingerprint"],
            source["recovery_authorization_fingerprint"],
        }
    return True


def _valid_observations(source: dict[str, object]) -> bool:
    before = source["before_observation_fingerprint"]
    expected = source["expected_after_observation_fingerprint"]
    return (
        is_opaque_fingerprint(before)
        and is_opaque_fingerprint(expected)
        and before != expected
        and is_fingerprint(source["observed_effect_fingerprint"])
    )


def _valid_event_state(source: dict[str, object]) -> bool:
    event = source["event_code"]
    outcome = source["effect_outcome"]
    observed = source["observed_effect_fingerprint"]
    if event in {
        JournalEventCode.INTENT.value,
        JournalEventCode.RESUME_BOUND.value,
    }:
        return (
            outcome == JournalEffectOutcome.PENDING.value
            and observed == ZERO_FINGERPRINT
        )
    if outcome == JournalEffectOutcome.APPLIED.value:
        return observed == source["expected_after_observation_fingerprint"]
    if outcome == JournalEffectOutcome.NOT_APPLIED.value:
        return observed == source["before_observation_fingerprint"]
    return False


def _exact_dict(
    value: object, expected_keys: tuple[str, ...]
) -> dict[str, object]:
    if type(value) is not dict:
        _invalid()
    keys = tuple(value.keys())
    if (
        any(type(key) is not str for key in keys)
        or len(keys) != len(expected_keys)
        or frozenset(keys) != frozenset(expected_keys)
    ):
        _invalid()
    return value


def _invalid() -> None:
    raise JournalContractError(JOURNAL_RECORD_ERROR)
