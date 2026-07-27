"""Issue #52 hostile chain and restart fail-closed tests."""

from __future__ import annotations

import unittest
from dataclasses import replace

from backend.cutover_journal import (
    DurabilityPlatform,
    DurableJournalStore,
    JournalContractError,
    JournalOperationStatus,
    JournalRecordV1,
    SyntheticEffectStateV1,
    SyntheticJournalMediumV1,
    inspect_restart,
    verify_synthetic_journal_snapshot,
)
from tests.cutover_journal_fixtures import (
    journal_record_body_after,
    opaque_fingerprint,
    valid_bound_journal_record_body,
    valid_operation_binding,
    valid_operation_contracts,
)


class HostileHash:
    def __hash__(self) -> int:
        raise RuntimeError("hostile hash detail")


class JournalChainTests(unittest.TestCase):
    def test_missing_duplicate_wrong_previous_and_wrong_binding_fail(
        self,
    ) -> None:
        binding, snapshot, records = _committed_snapshot()
        intent, observed, committed = records
        wrong_previous_body = journal_record_body_after(
            intent,
            event_code="EFFECT_OBSERVED",
        )
        wrong_previous_body["previous_record_hash"] = opaque_fingerprint(999)
        wrong_previous = JournalRecordV1.create(wrong_previous_body)
        wrong_binding_body = valid_bound_journal_record_body(binding)
        wrong_binding_body["operation_fingerprint"] = opaque_fingerprint(998)
        wrong_binding_body["profile_fingerprint"] = opaque_fingerprint(997)
        wrong_binding = JournalRecordV1.create(wrong_binding_body)
        hostile_snapshots = (
            _records_snapshot(snapshot, (intent, committed)),
            _records_snapshot(snapshot, (intent, intent)),
            _records_snapshot(snapshot, (intent, wrong_previous)),
            _records_snapshot(snapshot, (wrong_binding,)),
            replace(
                snapshot,
                pending_barrier_hashes=(
                    opaque_fingerprint(996),
                    *snapshot.pending_barrier_hashes,
                ),
            ),
        )

        for hostile in hostile_snapshots:
            with self.subTest(records=len(hostile.published_records)):
                with self.assertRaisesRegex(
                    JournalContractError, "^JOURNAL_CHAIN_INVALID$"
                ):
                    verify_synthetic_journal_snapshot(
                        hostile,
                        binding=binding,
                    )

    def test_hostile_snapshot_never_leaks_runtime_exception(self) -> None:
        binding, snapshot, _records = _committed_snapshot()
        hostile = replace(
            snapshot,
            pending_barrier_hashes=(HostileHash(),),
        )

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_CHAIN_INVALID$"
        ):
            verify_synthetic_journal_snapshot(
                hostile,
                binding=binding,
            )

    def test_corrupt_restart_is_incident_stop_and_read_only(self) -> None:
        binding, snapshot, _records = _committed_snapshot()
        profile, _forward, recovery = valid_operation_contracts()
        effect = SyntheticEffectStateV1.from_restart(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
            current_observation_fingerprint=opaque_fingerprint(6),
            identity_mapping_intact=True,
            forward_invocations=1,
        )
        corrupt = replace(snapshot, namespace_barrier_hashes=())

        result = inspect_restart(
            snapshot=corrupt,
            binding=binding,
            profile=profile,
            effect_snapshot=effect.snapshot(),
            resume_authorization=None,
            recovery_authorization=recovery,
            observed_at_epoch=1_800_000_100,
        )

        self.assertEqual(
            result.status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        self.assertEqual(corrupt.namespace_barrier_hashes, ())
        self.assertEqual(result.counts.rejected, 1)


def _committed_snapshot():
    binding = valid_operation_binding()
    medium = SyntheticJournalMediumV1.empty(
        platform=DurabilityPlatform.LINUX
    )
    store = DurableJournalStore.begin_synthetic(
        medium=medium,
        binding=binding,
    )
    intent = JournalRecordV1.create(
        valid_bound_journal_record_body(binding)
    )
    observed = JournalRecordV1.create(
        journal_record_body_after(
            intent,
            event_code="EFFECT_OBSERVED",
        )
    )
    committed = JournalRecordV1.create(
        journal_record_body_after(
            observed,
            event_code="COMMITTED",
        )
    )
    for record in (intent, observed, committed):
        store.append_record(record)
    return binding, medium.snapshot(), (intent, observed, committed)


def _records_snapshot(snapshot, records):
    hashes = tuple(record.record_hash for record in records)
    return replace(
        snapshot,
        pending_records=(),
        published_records=tuple(
            record.to_canonical_json() for record in records
        ),
        pending_barrier_hashes=hashes,
        published_barrier_hashes=hashes,
        namespace_barrier_hashes=hashes,
    )


if __name__ == "__main__":
    unittest.main()
