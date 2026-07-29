"""Exact identity facts selected from the verified transaction journal."""

from __future__ import annotations

from .durable_store import _RepositoryJournalStore
from .errors import RepositoryTransactionError
from .journal_types import ForwardBoundary, RepositoryMutationKind


def journaled_container_identity(scope) -> str:
    records = tuple(
        record
        for record in _RepositoryJournalStore.open_verified(
            scope
        ).verified_records()
        if (
            record.direction == "forward"
            and record.event == "committed"
            and record.boundary == ForwardBoundary.CONTAINER_PUBLISHED.value
            and record.mutation_kind
            == RepositoryMutationKind.CREATE_DIRECTORY.value
            and record.mutation_index == 26
        )
    )
    if (
        len(records) != 1
        or type(records[0].observed_effect_fingerprint) is not str
        or len(records[0].observed_effect_fingerprint) != 64
    ):
        raise RepositoryTransactionError(
            "repository_container_audit_policy_failed"
        ) from None
    return records[0].observed_effect_fingerprint
