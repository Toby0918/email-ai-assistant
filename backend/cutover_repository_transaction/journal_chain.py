"""Strict hash and event-group verification for repository journals."""

from __future__ import annotations

from .errors import RepositoryTransactionError
from .journal_types import RepositoryJournalEvent


def verify_journal_chain(
    records,
    *,
    operation: str,
    profile: str,
    authorization: str,
    owner: str,
) -> None:
    previous = "0" * 64
    for record in records:
        if (
            record.previous_record_hash != previous
            or record.operation_fingerprint != operation
            or record.profile_fingerprint != profile
            or record.authorization_fingerprint != authorization
            or record.owner_fingerprint != owner
        ):
            _fail()
        previous = record.record_hash
    _verify_event_groups(records)


def _verify_event_groups(records) -> None:
    index = 0
    while index < len(records):
        intent = records[index]
        if intent.event != RepositoryJournalEvent.INTENT.value:
            _fail()
        if index + 1 == len(records):
            return
        second = records[index + 1]
        _require_same_mutation(intent, second)
        if second.event == RepositoryJournalEvent.ABORTED.value:
            index += 2
            continue
        if second.event != RepositoryJournalEvent.OBSERVED.value:
            _fail()
        if index + 2 == len(records):
            return
        committed = records[index + 2]
        _require_same_mutation(intent, committed)
        if (
            committed.event != RepositoryJournalEvent.COMMITTED.value
            or committed.observed_effect_fingerprint
            != second.observed_effect_fingerprint
        ):
            _fail()
        index += 3


def _require_same_mutation(intent, record) -> None:
    if (
        record.direction != intent.direction
        or record.boundary != intent.boundary
        or record.mutation_kind != intent.mutation_kind
        or record.mutation_index != intent.mutation_index
        or record.before_observation_fingerprint
        != intent.before_observation_fingerprint
        or record.expected_after_observation_fingerprint
        != intent.expected_after_observation_fingerprint
    ):
        _fail()


def _fail() -> None:
    raise RepositoryTransactionError("repository_journal_invalid") from None
