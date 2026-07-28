"""Synthetic journal and profile fixtures for Issue #55 tests."""

from __future__ import annotations

from backend.cutover_journal import (
    DurabilityPlatform,
    DurableJournalStore,
    JournalRecordV1,
    SyntheticJournalMediumV1,
)
from tests.cutover_journal_fixtures import (
    valid_bound_journal_record_body,
    valid_operation_binding,
)


def durable_intent(
    *,
    before_fingerprint: str,
    expected_after_fingerprint: str,
    platform: DurabilityPlatform,
) -> tuple[JournalRecordV1, object, DurableJournalStore]:
    binding = valid_operation_binding()
    medium = SyntheticJournalMediumV1.empty(platform=platform)
    store = DurableJournalStore.begin_synthetic(
        medium=medium,
        binding=binding,
    )
    body = valid_bound_journal_record_body(binding)
    body["before_observation_fingerprint"] = before_fingerprint
    body["expected_after_observation_fingerprint"] = (
        expected_after_fingerprint
    )
    intent = JournalRecordV1.create(body)
    permit = store.append_record(intent)
    return intent, permit, store
