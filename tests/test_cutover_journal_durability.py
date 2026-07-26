"""Issue #52 synthetic durability and exclusive-owner tests."""

from __future__ import annotations

import threading
import unittest
from dataclasses import replace

from backend.cutover_journal import (
    DurabilityCutPoint,
    DurabilityPlatform,
    DurableJournalStore,
    JournalContractError,
    JournalRecordV1,
    SyntheticJournalMediumV1,
    verify_synthetic_journal_snapshot,
)
from tests.cutover_journal_fixtures import (
    journal_record_body_after,
    opaque_fingerprint,
    valid_bound_journal_record_body,
    valid_observed_record_body,
    valid_operation_binding,
)


EXPECTED_TRACES = {
    DurabilityPlatform.WINDOWS: (
        "PENDING_WRITE",
        "WINDOWS_PENDING_FILE_FLUSH",
        "FINAL_NO_REPLACE_PUBLICATION",
        "WINDOWS_PUBLISHED_FILE_FLUSH",
        "WINDOWS_NAMESPACE_FLUSH",
        "FINAL_STABLE_REREAD",
    ),
    DurabilityPlatform.LINUX: (
        "PENDING_WRITE",
        "LINUX_PENDING_FILE_FSYNC",
        "FINAL_NO_REPLACE_PUBLICATION",
        "LINUX_PUBLISHED_FILE_FSYNC",
        "LINUX_NAMESPACE_FSYNC",
        "FINAL_STABLE_REREAD",
    ),
}


class JournalDurabilityTests(unittest.TestCase):
    def test_append_requires_exact_file_and_namespace_barriers(self) -> None:
        for platform, expected_trace in EXPECTED_TRACES.items():
            with self.subTest(platform=platform):
                medium = SyntheticJournalMediumV1.empty(platform=platform)
                binding = valid_operation_binding()
                store = DurableJournalStore.begin_synthetic(
                    medium=medium,
                    binding=binding,
                )
                record = JournalRecordV1.create(
                    valid_bound_journal_record_body(binding)
                )

                permit = store.append_record(record)
                snapshot = medium.snapshot()

                self.assertEqual(permit.record_hash, record.record_hash)
                self.assertEqual(snapshot.trace, expected_trace)
                self.assertEqual(snapshot.pending_records, ())
                self.assertEqual(
                    snapshot.published_records,
                    (record.to_canonical_json(),),
                )
                self.assertEqual(
                    snapshot.namespace_barrier_hashes,
                    (record.record_hash,),
                )

    def test_pending_or_unbarriered_publication_never_returns_permit(
        self,
    ) -> None:
        cut_points = (
            DurabilityCutPoint.BEFORE_PENDING_WRITE,
            DurabilityCutPoint.DURING_PENDING_WRITE,
            DurabilityCutPoint.AFTER_PENDING_WRITE,
            DurabilityCutPoint.AFTER_PENDING_FILE_BARRIER,
            DurabilityCutPoint.AFTER_NO_REPLACE_PUBLICATION,
            DurabilityCutPoint.AFTER_PUBLISHED_FILE_BARRIER,
        )
        for cut_point in cut_points:
            with self.subTest(cut_point=cut_point):
                medium = SyntheticJournalMediumV1.empty(
                    platform=DurabilityPlatform.WINDOWS,
                    cut_point=cut_point,
                )
                binding = valid_operation_binding()
                store = DurableJournalStore.begin_synthetic(
                    medium=medium,
                    binding=binding,
                )
                record = JournalRecordV1.create(
                    valid_bound_journal_record_body(binding)
                )

                with self.assertRaisesRegex(
                    JournalContractError, "^SYNTHETIC_CRASH$"
                ):
                    store.append_record(record)

                snapshot = medium.snapshot()
                self.assertNotIn(
                    record.record_hash,
                    snapshot.namespace_barrier_hashes,
                )

    def test_lost_acknowledgement_allows_only_exact_record_retry(
        self,
    ) -> None:
        cut_points = (
            DurabilityCutPoint.AFTER_PENDING_WRITE,
            DurabilityCutPoint.AFTER_PENDING_FILE_BARRIER,
            DurabilityCutPoint.AFTER_NO_REPLACE_PUBLICATION,
            DurabilityCutPoint.AFTER_PUBLISHED_FILE_BARRIER,
            DurabilityCutPoint.AFTER_NAMESPACE_BARRIER,
            DurabilityCutPoint.AFTER_FINAL_STABLE_REREAD,
        )
        for cut_point in cut_points:
            with self.subTest(cut_point=cut_point):
                medium = SyntheticJournalMediumV1.empty(
                    platform=DurabilityPlatform.WINDOWS,
                    cut_point=cut_point,
                )
                binding = valid_operation_binding()
                store = DurableJournalStore.begin_synthetic(
                    medium=medium,
                    binding=binding,
                )
                record = JournalRecordV1.create(
                    valid_bound_journal_record_body(binding)
                )
                with self.assertRaisesRegex(
                    JournalContractError, "^SYNTHETIC_CRASH$"
                ):
                    store.append_record(record)

                permit = store.append_record(record)
                snapshot = medium.snapshot()

                self.assertEqual(permit.record_hash, record.record_hash)
                self.assertEqual(
                    snapshot.published_records,
                    (record.to_canonical_json(),),
                )
                self.assertEqual(
                    snapshot.namespace_barrier_hashes,
                    (record.record_hash,),
                )

    def test_effect_permit_forces_stable_reread_after_namespace_crash(
        self,
    ) -> None:
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX,
            cut_point=DurabilityCutPoint.AFTER_NAMESPACE_BARRIER,
        )
        binding = valid_operation_binding()
        store = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        record = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            store.append_record(record)
        self.assertNotIn("FINAL_STABLE_REREAD", medium.snapshot().trace)

        permit = store._durable_permit_for(record)
        snapshot = medium.snapshot()

        self.assertEqual(permit.record_hash, record.record_hash)
        self.assertEqual(
            snapshot.stable_reread_hashes,
            (record.record_hash,),
        )
        self.assertEqual(snapshot.trace[-1], "FINAL_STABLE_REREAD")

    def test_stale_owner_cannot_complete_missing_stable_reread(
        self,
    ) -> None:
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX,
            cut_point=DurabilityCutPoint.AFTER_NAMESPACE_BARRIER,
        )
        binding = valid_operation_binding()
        stale = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        record = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            stale.append_record(record)
        medium.simulate_restart()
        before = medium.snapshot()

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OWNER_INVALID$"
        ):
            stale.append_record(record)

        self.assertEqual(medium.snapshot(), before)

    def test_one_operation_medium_has_one_exclusive_owner(self) -> None:
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        binding = valid_operation_binding()
        store = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )

        competing = valid_operation_binding(owner_index=8)
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OWNER_ACTIVE$"
        ):
            DurableJournalStore.begin_synthetic(
                medium=medium,
                binding=competing,
            )

        store.close()
        replacement = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=competing,
        )
        replacement.close()

    def test_stale_store_cannot_use_or_release_recovered_owner(self) -> None:
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        binding = valid_operation_binding()
        stale = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        medium.simulate_restart()
        active = DurableJournalStore.recover_synthetic(
            medium=medium,
            binding=binding,
        )
        record = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OWNER_INVALID$"
        ):
            stale.append_record(record)
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OWNER_INVALID$"
        ):
            stale.close()

        permit = active.append_record(record)
        self.assertEqual(permit.record_hash, record.record_hash)
        active.close()

    def test_restart_cannot_overtake_an_inflight_append(self) -> None:
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        binding = valid_operation_binding()
        store = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        record = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        entered = threading.Event()
        release = threading.Event()

        class PausingPending(dict):
            def get(self, key, default=None):
                result = super().get(key, default)
                entered.set()
                release.wait(timeout=5)
                return result

        medium._pending = PausingPending()
        outcome = []

        def append():
            try:
                store.append_record(record)
                outcome.append("OK")
            except JournalContractError as error:
                outcome.append(str(error))

        thread = threading.Thread(target=append)
        thread.start()
        self.assertTrue(entered.wait(timeout=5))
        try:
            with self.assertRaisesRegex(
                JournalContractError, "^JOURNAL_MEDIUM_BUSY$"
            ):
                medium.simulate_restart()
        finally:
            release.set()
            thread.join(timeout=10)

        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, ["OK"])
        self.assertEqual(
            medium.snapshot().published_records,
            (record.to_canonical_json(),),
        )

    def test_store_rejects_invalid_transition_before_pending_write(
        self,
    ) -> None:
        binding = valid_operation_binding()
        invalid_bodies = []
        committed = valid_bound_journal_record_body(binding)
        committed.update(valid_observed_record_body(event_code="COMMITTED"))
        committed.update(
            {
                "sequence": 1,
                "previous_record_hash": "0" * 64,
                "governing_master_commit": binding.governing_master_commit,
                "operation_fingerprint": binding.operation_fingerprint,
                "profile_fingerprint": binding.profile_fingerprint,
                "forward_authorization_fingerprint": (
                    binding.forward_authorization_fingerprint
                ),
                "recovery_authorization_fingerprint": (
                    binding.recovery_authorization_fingerprint
                ),
                "owner_fingerprint": binding.owner_fingerprint,
                "authorization_fingerprint": (
                    binding.forward_authorization_fingerprint
                ),
            }
        )
        invalid_bodies.append(committed)
        reverse = valid_bound_journal_record_body(binding)
        reverse.update(
            {
                "direction": "REVERSE",
                "authorization_fingerprint": (
                    binding.recovery_authorization_fingerprint
                ),
                "before_observation_fingerprint": opaque_fingerprint(6),
                "expected_after_observation_fingerprint": opaque_fingerprint(5),
            }
        )
        invalid_bodies.append(reverse)
        wrong_step = valid_bound_journal_record_body(binding)
        wrong_step["step_code"] = "SYNTHETIC_PUBLISH"
        invalid_bodies.append(wrong_step)

        for body in invalid_bodies:
            with self.subTest(
                direction=body["direction"],
                event=body["event_code"],
                step=body["step_code"],
            ):
                medium = SyntheticJournalMediumV1.empty(
                    platform=DurabilityPlatform.LINUX
                )
                store = DurableJournalStore.begin_synthetic(
                    medium=medium,
                    binding=binding,
                )
                record = JournalRecordV1.create(body)

                with self.assertRaisesRegex(
                    JournalContractError, "^JOURNAL_CHAIN_INVALID$"
                ):
                    store.append_record(record)

                self.assertEqual(medium.snapshot().pending_records, ())
                self.assertEqual(medium.snapshot().published_records, ())

    def test_store_rejects_mutated_record_before_any_write_or_permit(
        self,
    ) -> None:
        for attribute, value in (
            ("record_hash", opaque_fingerprint(999)),
            (
                "expected_after_observation_fingerprint",
                opaque_fingerprint(998),
            ),
        ):
            with self.subTest(attribute=attribute):
                binding = valid_operation_binding()
                medium = SyntheticJournalMediumV1.empty(
                    platform=DurabilityPlatform.LINUX
                )
                store = DurableJournalStore.begin_synthetic(
                    medium=medium,
                    binding=binding,
                )
                record = JournalRecordV1.create(
                    valid_bound_journal_record_body(binding)
                )
                object.__setattr__(record, attribute, value)
                before = medium.snapshot()

                with self.assertRaisesRegex(
                    JournalContractError, "^JOURNAL_RECORD_INVALID$"
                ):
                    store.append_record(record)

                self.assertEqual(medium.snapshot(), before)

    def test_recovery_owner_rejects_truncated_pending_record(self) -> None:
        binding = valid_operation_binding()
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX,
            cut_point=DurabilityCutPoint.DURING_PENDING_WRITE,
        )
        store = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        record = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            store.append_record(record)
        medium.simulate_restart()

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_CHAIN_INVALID$"
        ):
            DurableJournalStore.recover_synthetic(
                medium=medium,
                binding=binding,
            )

    def test_recovery_owner_requires_a_complete_verified_chain(self) -> None:
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        binding = valid_operation_binding()
        store = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        intent = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        store.append_record(intent)
        observed = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="EFFECT_OBSERVED",
            )
        )
        store.append_record(observed)
        committed = JournalRecordV1.create(
            journal_record_body_after(
                observed,
                event_code="COMMITTED",
            )
        )
        store.append_record(committed)
        next_intent_body = journal_record_body_after(
            committed,
            event_code="INTENT",
            step_code="SYNTHETIC_PUBLISH",
        )
        next_intent_body["before_observation_fingerprint"] = (
            intent.expected_after_observation_fingerprint
        )
        next_intent_body["expected_after_observation_fingerprint"] = (
            opaque_fingerprint(10)
        )
        next_intent = JournalRecordV1.create(next_intent_body)
        store.append_record(next_intent)
        store.close()
        medium.simulate_restart()

        recovered = DurableJournalStore.recover_synthetic(
            medium=medium,
            binding=binding,
        )
        chain = verify_synthetic_journal_snapshot(
            medium.snapshot(),
            binding=binding,
        )

        self.assertEqual(chain.forward_committed, 1)
        self.assertEqual(chain.reverse_committed, 0)
        self.assertEqual(chain.open_event, "INTENT")
        recovered.close()

        snapshot = medium.snapshot()
        invalid_snapshots = (
            replace(
                snapshot,
                published_records=(
                    snapshot.published_records[0][:-1],
                    *snapshot.published_records[1:],
                ),
            ),
            replace(
                snapshot,
                published_records=(
                    snapshot.published_records[0],
                    snapshot.published_records[0],
                    *snapshot.published_records[2:],
                ),
            ),
            replace(snapshot, namespace_barrier_hashes=()),
        )
        for invalid in invalid_snapshots:
            with self.assertRaisesRegex(
                JournalContractError, "^JOURNAL_CHAIN_INVALID$"
            ):
                verify_synthetic_journal_snapshot(
                    invalid,
                    binding=binding,
                )


if __name__ == "__main__":
    unittest.main()
