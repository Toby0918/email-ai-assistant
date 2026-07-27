"""Issue #52 forward and reverse crash-boundary matrix."""

from __future__ import annotations

import unittest

from backend.cutover_journal import (
    DurabilityCutPoint,
    DurabilityPlatform,
    DurableJournalStore,
    JournalContractError,
    JournalOperationStatus,
    JournalRecordV1,
    SyntheticEffectStateV1,
    SyntheticJournalMediumV1,
    SyntheticJournalTransaction,
    TransactionCutPoint,
    inspect_restart,
    resume_synthetic,
    rollback_next_synthetic,
    verify_synthetic_journal_snapshot,
)
from tests.cutover_journal_fixtures import (
    journal_record_body_after,
    opaque_fingerprint,
    valid_bound_journal_record_body,
    valid_operation_binding,
    valid_operation_contracts,
)


CRASH_POINTS = tuple(
    point
    for point in TransactionCutPoint
    if point is not TransactionCutPoint.NONE
)


class JournalCrashMatrixTests(unittest.TestCase):
    def test_namespace_lost_ack_intent_resumes_to_stable_commit(
        self,
    ) -> None:
        context = _base_context()
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_NAMESPACE_BARRIER
        )
        transaction = SyntheticJournalTransaction.begin(
            store=context["store"],
            binding=context["binding"],
            effect_state=context["effect"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            transaction.run_next_forward(
                profile=context["profile"],
                authorization=context["forward"],
                inspected_at_epoch=1_800_000_100,
                action_at_epoch=1_800_000_101,
            )
        self.assertEqual(
            context["medium"].snapshot().stable_reread_hashes,
            (),
        )
        _restart(context)
        self.assertEqual(
            _inspect(context, include_resume=True).status,
            JournalOperationStatus.RESUME_ALLOWED,
        )

        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        resume_synthetic(
            store=store,
            binding=context["binding"],
            profile=context["profile"],
            resume_authorization=context["resume"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_110,
            action_at_epoch=1_800_000_111,
        )

        snapshot = context["medium"].snapshot()
        records = tuple(
            JournalRecordV1.from_json(payload)
            for payload in snapshot.published_records
        )
        self.assertEqual(
            snapshot.stable_reread_hashes,
            tuple(record.record_hash for record in records),
        )
        self.assertEqual(
            verify_synthetic_journal_snapshot(
                snapshot,
                binding=context["binding"],
            ).forward_committed,
            1,
        )
        self.assertEqual(context["effect"].forward_invocations, 1)

    def test_namespace_lost_ack_resume_bound_continues_exactly_once(
        self,
    ) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_INTENT)
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_NAMESPACE_BARRIER
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            _resume(context, store)
        context["store"] = store
        _restart(context)

        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        _resume(context, recovered)

        _assert_stable_chain(self, context, forward_committed=1)
        self.assertEqual(context["effect"].forward_invocations, 1)

    def test_namespace_lost_ack_observed_fact_continues_without_replay(
        self,
    ) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_EFFECT)
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            _resume(
                context,
                store,
                cut_point=TransactionCutPoint.BEFORE_OBSERVED,
            )
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_NAMESPACE_BARRIER
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            _resume(context, store)
        context["store"] = store
        _restart(context)

        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        _resume(context, recovered)

        _assert_stable_chain(self, context, forward_committed=1)
        self.assertEqual(context["effect"].forward_invocations, 1)

    def test_namespace_lost_ack_commit_stabilizes_before_next_intent(
        self,
    ) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_EFFECT)
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        for _index in range(2):
            with self.assertRaisesRegex(
                JournalContractError, "^SYNTHETIC_CRASH$"
            ):
                _resume(
                    context,
                    store,
                    cut_point=TransactionCutPoint.BEFORE_COMMIT,
                )
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_NAMESPACE_BARRIER
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            _resume(context, store)
        context["store"] = store
        _restart(context)

        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        _resume(context, recovered)

        _assert_stable_chain(self, context, forward_committed=2)
        self.assertEqual(context["effect"].forward_invocations, 2)

    def test_every_durability_boundary_has_read_only_classification(
        self,
    ) -> None:
        expected = {
            DurabilityCutPoint.BEFORE_PENDING_WRITE: (
                JournalOperationStatus.SAFE_ABORT
            ),
            DurabilityCutPoint.DURING_PENDING_WRITE: (
                JournalOperationStatus.INCIDENT_STOP
            ),
            DurabilityCutPoint.AFTER_PENDING_WRITE: (
                JournalOperationStatus.RESUME_ALLOWED
            ),
            DurabilityCutPoint.AFTER_PENDING_FILE_BARRIER: (
                JournalOperationStatus.RESUME_ALLOWED
            ),
            DurabilityCutPoint.AFTER_NO_REPLACE_PUBLICATION: (
                JournalOperationStatus.INCIDENT_STOP
            ),
            DurabilityCutPoint.AFTER_PUBLISHED_FILE_BARRIER: (
                JournalOperationStatus.INCIDENT_STOP
            ),
            DurabilityCutPoint.AFTER_NAMESPACE_BARRIER: (
                JournalOperationStatus.RESUME_ALLOWED
            ),
            DurabilityCutPoint.AFTER_FINAL_STABLE_REREAD: (
                JournalOperationStatus.RESUME_ALLOWED
            ),
        }
        for platform in DurabilityPlatform:
            for cut_point, expected_status in expected.items():
                with self.subTest(
                    platform=platform,
                    cut_point=cut_point,
                ):
                    context = _base_context()
                    context["medium"] = SyntheticJournalMediumV1.empty(
                        platform=platform,
                        cut_point=cut_point,
                    )
                    context["store"] = DurableJournalStore.begin_synthetic(
                        medium=context["medium"],
                        binding=context["binding"],
                    )
                    record = JournalRecordV1.create(
                        valid_bound_journal_record_body(
                            context["binding"]
                        )
                    )
                    with self.assertRaisesRegex(
                        JournalContractError, "^SYNTHETIC_CRASH$"
                    ):
                        context["store"].append_record(record)
                    _restart(context)

                    result = _inspect(context, include_resume=True)

                    self.assertEqual(result.status, expected_status)
                    self.assertEqual(
                        context["effect"].forward_invocations,
                        0,
                    )

    def test_every_forward_boundary_is_classified_without_blind_retry(
        self,
    ) -> None:
        for cut_point in CRASH_POINTS:
            with self.subTest(cut_point=cut_point):
                context = _forward_crash(cut_point)
                result = _inspect(context, include_resume=True)

                expected = (
                    JournalOperationStatus.SAFE_ABORT
                    if cut_point is TransactionCutPoint.BEFORE_INTENT
                    else JournalOperationStatus.RESUME_ALLOWED
                )
                self.assertEqual(result.status, expected)
                before_invocations = context["effect"].forward_invocations

                if cut_point not in {
                    TransactionCutPoint.BEFORE_INTENT,
                    TransactionCutPoint.AFTER_COMMIT,
                }:
                    store = DurableJournalStore.recover_synthetic(
                        medium=context["medium"],
                        binding=context["binding"],
                    )
                    resume_synthetic(
                        store=store,
                        binding=context["binding"],
                        profile=context["profile"],
                        resume_authorization=context["resume"],
                        effect_state=context["effect"],
                        observed_at_epoch=1_800_000_110,
                        action_at_epoch=1_800_000_111,
                    )
                    chain = verify_synthetic_journal_snapshot(
                        context["medium"].snapshot(),
                        binding=context["binding"],
                    )
                    self.assertEqual(chain.forward_committed, 1)
                    self.assertEqual(
                        context["effect"].forward_invocations,
                        1,
                    )
                    self.assertLessEqual(before_invocations, 1)

    def test_durable_forward_observation_never_allows_replay_after_drift(
        self,
    ) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_OBSERVED)
        context["effect"] = SyntheticEffectStateV1.from_restart(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
            current_observation_fingerprint=opaque_fingerprint(5),
            identity_mapping_intact=True,
            forward_invocations=1,
        )

        result = _inspect(context, include_resume=True)

        self.assertEqual(
            result.status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=context["resume"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["effect"].forward_invocations, 1)

    def test_broken_identity_blocks_direct_forward_and_reverse_actions(
        self,
    ) -> None:
        forward = _forward_crash(TransactionCutPoint.AFTER_EFFECT)
        forward["effect"] = _restart_effect(
            current=opaque_fingerprint(6),
            identity_mapping_intact=False,
            forward_invocations=1,
        )
        self.assertEqual(
            _inspect(forward, include_resume=True).status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        forward_store = DurableJournalStore.recover_synthetic(
            medium=forward["medium"],
            binding=forward["binding"],
        )
        forward_before = forward["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=forward_store,
                binding=forward["binding"],
                profile=forward["profile"],
                resume_authorization=forward["resume"],
                effect_state=forward["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(forward["medium"].snapshot(), forward_before)

        reverse = _reverse_crash(TransactionCutPoint.AFTER_EFFECT)
        reverse["effect"] = _restart_effect(
            current=opaque_fingerprint(5),
            identity_mapping_intact=False,
            forward_invocations=1,
            reverse_invocations=1,
        )
        self.assertEqual(
            _inspect(reverse, include_resume=False).status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        reverse_store = DurableJournalStore.recover_synthetic(
            medium=reverse["medium"],
            binding=reverse["binding"],
        )
        reverse_before = reverse["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            rollback_next_synthetic(
                store=reverse_store,
                binding=reverse["binding"],
                profile=reverse["profile"],
                recovery_authorization=reverse["recovery"],
                effect_state=reverse["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(reverse["medium"].snapshot(), reverse_before)

    def test_substituted_effect_mapping_cannot_forge_observed_commit(
        self,
    ) -> None:
        forward = _forward_crash(TransactionCutPoint.AFTER_INTENT)
        forward["effect"] = _restart_effect(
            current=opaque_fingerprint(5),
            prepared=opaque_fingerprint(11),
        )
        self.assertEqual(
            _inspect(forward, include_resume=True).status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=forward["medium"],
            binding=forward["binding"],
        )
        before = forward["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=recovered,
                binding=forward["binding"],
                profile=forward["profile"],
                resume_authorization=forward["resume"],
                effect_state=forward["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(forward["medium"].snapshot(), before)
        self.assertEqual(forward["effect"].forward_invocations, 0)

        reverse = _reverse_crash(TransactionCutPoint.AFTER_INTENT)
        reverse["effect"] = _restart_effect(
            current=opaque_fingerprint(6),
            prepared=opaque_fingerprint(11),
            forward_invocations=1,
        )
        self.assertEqual(
            _inspect(reverse, include_resume=False).status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=reverse["medium"],
            binding=reverse["binding"],
        )
        before = reverse["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            rollback_next_synthetic(
                store=recovered,
                binding=reverse["binding"],
                profile=reverse["profile"],
                recovery_authorization=reverse["recovery"],
                effect_state=reverse["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(reverse["medium"].snapshot(), before)

    def test_pending_intent_cannot_launder_an_unpermitted_effect(
        self,
    ) -> None:
        context = _base_context()
        context["medium"] = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX,
            cut_point=DurabilityCutPoint.AFTER_PENDING_WRITE,
        )
        context["store"] = DurableJournalStore.begin_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        transaction = SyntheticJournalTransaction.begin(
            store=context["store"],
            binding=context["binding"],
            effect_state=context["effect"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            transaction.run_next_forward(
                profile=context["profile"],
                authorization=context["forward"],
                inspected_at_epoch=1_800_000_100,
                action_at_epoch=1_800_000_101,
            )
        _restart(context)
        context["effect"] = _restart_effect(
            current=opaque_fingerprint(6),
            forward_invocations=1,
        )
        self.assertEqual(
            _inspect(context, include_resume=True).status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        before = context["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=context["resume"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["medium"].snapshot(), before)

    def test_pending_only_intent_can_be_completed_but_never_blindly_used(
        self,
    ) -> None:
        context = _base_context()
        context["medium"] = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX,
            cut_point=DurabilityCutPoint.AFTER_PENDING_WRITE,
        )
        context["store"] = DurableJournalStore.begin_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        record = JournalRecordV1.create(
            valid_bound_journal_record_body(context["binding"])
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            context["store"].append_record(record)
        _restart(context)
        self.assertEqual(
            _inspect(context, include_resume=True).status,
            JournalOperationStatus.RESUME_ALLOWED,
        )
        self.assertEqual(context["effect"].forward_invocations, 0)
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )

        resume_synthetic(
            store=recovered,
            binding=context["binding"],
            profile=context["profile"],
            resume_authorization=context["resume"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_110,
            action_at_epoch=1_800_000_111,
        )

        chain = verify_synthetic_journal_snapshot(
            context["medium"].snapshot(),
            binding=context["binding"],
        )
        self.assertEqual(chain.forward_committed, 1)
        self.assertEqual(context["effect"].forward_invocations, 1)

    def test_pending_followup_records_complete_without_effect_replay(
        self,
    ) -> None:
        cases = (
            ("FORWARD", "EFFECT_OBSERVED"),
            ("FORWARD", "COMMITTED"),
            ("REVERSE", "EFFECT_OBSERVED"),
            ("REVERSE", "COMMITTED"),
        )
        cut_points = (
            DurabilityCutPoint.AFTER_PENDING_WRITE,
            DurabilityCutPoint.AFTER_PENDING_FILE_BARRIER,
        )
        for direction, event_code in cases:
            for cut_point in cut_points:
                with self.subTest(
                    direction=direction,
                    event_code=event_code,
                    cut_point=cut_point,
                ):
                    context = _pending_followup_crash(
                        direction=direction,
                        event_code=event_code,
                        cut_point=cut_point,
                    )
                    before_inspection = context["medium"].snapshot()
                    result = _inspect(
                        context,
                        include_resume=direction == "FORWARD",
                    )
                    self.assertEqual(
                        context["medium"].snapshot(), before_inspection
                    )
                    self.assertEqual(result.counts.pending, 1)
                    expected = (
                        JournalOperationStatus.RESUME_ALLOWED
                        if direction == "FORWARD"
                        else JournalOperationStatus.ROLLBACK_REQUIRED
                    )
                    self.assertEqual(result.status, expected)
                    recovered = DurableJournalStore.recover_synthetic(
                        medium=context["medium"],
                        binding=context["binding"],
                    )
                    if direction == "FORWARD":
                        resume_synthetic(
                            store=recovered,
                            binding=context["binding"],
                            profile=context["profile"],
                            resume_authorization=context["resume"],
                            effect_state=context["effect"],
                            observed_at_epoch=1_800_000_110,
                            action_at_epoch=1_800_000_111,
                        )
                    else:
                        rollback_next_synthetic(
                            store=recovered,
                            binding=context["binding"],
                            profile=context["profile"],
                            recovery_authorization=context["recovery"],
                            effect_state=context["effect"],
                            observed_at_epoch=1_800_000_110,
                            action_at_epoch=1_800_000_111,
                        )
                    chain = verify_synthetic_journal_snapshot(
                        context["medium"].snapshot(),
                        binding=context["binding"],
                    )
                    self.assertIsNone(chain._pending_record)
                    self.assertEqual(chain.forward_committed, 1)
                    self.assertEqual(
                        chain.reverse_committed,
                        1 if direction == "REVERSE" else 0,
                    )
                    self.assertEqual(
                        context["effect"].forward_invocations, 1
                    )
                    self.assertEqual(
                        context["effect"].reverse_invocations,
                        1 if direction == "REVERSE" else 0,
                    )
                    after_status = _inspect(
                        context,
                        include_resume=direction == "FORWARD",
                    ).status
                    self.assertEqual(
                        after_status,
                        (
                            JournalOperationStatus.RESUME_ALLOWED
                            if direction == "FORWARD"
                            else JournalOperationStatus.SAFE_ABORT
                        ),
                    )

    def test_pending_not_applied_fact_is_recovery_only(self) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_INTENT)
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        intent = JournalRecordV1.from_json(
            context["medium"].snapshot().published_records[-1]
        )
        observed = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="EFFECT_OBSERVED",
                effect_outcome="NOT_APPLIED",
                authorization_fingerprint=(
                    context["binding"].recovery_authorization_fingerprint
                ),
            )
        )
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_PENDING_WRITE
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            store.append_record(observed)
        store.close()
        context["medium"].simulate_restart()
        self.assertEqual(
            _inspect(context, include_resume=True).status,
            JournalOperationStatus.ROLLBACK_REQUIRED,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        before = context["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=context["resume"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["medium"].snapshot(), before)
        rollback_next_synthetic(
            store=recovered,
            binding=context["binding"],
            profile=context["profile"],
            recovery_authorization=context["recovery"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_112,
            action_at_epoch=1_800_000_113,
        )
        chain = verify_synthetic_journal_snapshot(
            context["medium"].snapshot(),
            binding=context["binding"],
        )
        self.assertEqual(chain._forward_outcomes, ("NOT_APPLIED",))
        self.assertEqual(context["effect"].forward_invocations, 0)

    def test_pending_observed_fact_mismatch_is_incident_stop(self) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_INTENT)
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        intent = JournalRecordV1.from_json(
            context["medium"].snapshot().published_records[-1]
        )
        observed = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="EFFECT_OBSERVED",
            )
        )
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_PENDING_WRITE
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            store.append_record(observed)
        store.close()
        context["medium"].simulate_restart()

        before = context["medium"].snapshot()
        result = _inspect(context, include_resume=True)

        self.assertEqual(
            result.status, JournalOperationStatus.INCIDENT_STOP
        )
        self.assertEqual(context["medium"].snapshot(), before)

    def test_pending_resume_bound_cannot_override_not_applied_fact(
        self,
    ) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_INTENT)
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        intent = JournalRecordV1.from_json(
            context["medium"].snapshot().published_records[-1]
        )
        observed = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="EFFECT_OBSERVED",
                effect_outcome="NOT_APPLIED",
                authorization_fingerprint=(
                    context["binding"].recovery_authorization_fingerprint
                ),
            )
        )
        store.append_record(observed)
        rebound = JournalRecordV1.create(
            journal_record_body_after(
                observed,
                event_code="RESUME_BOUND",
                authorization_fingerprint=opaque_fingerprint(11),
            )
        )
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_PENDING_WRITE
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            store.append_record(rebound)
        store.close()
        context["medium"].simulate_restart()

        self.assertEqual(
            _inspect(context, include_resume=True).status,
            JournalOperationStatus.ROLLBACK_REQUIRED,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        before = context["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=context["resume"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["medium"].snapshot(), before)

    def test_terminal_not_applied_never_classifies_as_resumable(
        self,
    ) -> None:
        context = _base_context()
        transaction = SyntheticJournalTransaction.begin(
            store=context["store"],
            binding=context["binding"],
            effect_state=context["effect"],
        )
        transaction.run_next_forward(
            profile=context["profile"],
            authorization=context["forward"],
            inspected_at_epoch=1_800_000_100,
            action_at_epoch=1_800_000_101,
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            transaction.run_next_forward(
                profile=context["profile"],
                authorization=context["forward"],
                inspected_at_epoch=1_800_000_102,
                action_at_epoch=1_800_000_103,
                cut_point=TransactionCutPoint.AFTER_INTENT,
            )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            rollback_next_synthetic(
                store=context["store"],
                binding=context["binding"],
                profile=context["profile"],
                recovery_authorization=context["recovery"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_104,
                action_at_epoch=1_800_000_105,
                cut_point=TransactionCutPoint.BEFORE_INTENT,
            )
        _restart(context)

        result = _inspect(context, include_resume=True)

        self.assertEqual(
            result.status, JournalOperationStatus.ROLLBACK_REQUIRED
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        before = context["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_TRANSITION_INVALID$"
        ):
            resume_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=context["resume"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["medium"].snapshot(), before)
        rollback_next_synthetic(
            store=recovered,
            binding=context["binding"],
            profile=context["profile"],
            recovery_authorization=context["recovery"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_112,
            action_at_epoch=1_800_000_113,
        )
        chain = verify_synthetic_journal_snapshot(
            context["medium"].snapshot(),
            binding=context["binding"],
        )
        self.assertEqual(
            chain._forward_outcomes, ("APPLIED", "NOT_APPLIED")
        )
        self.assertEqual(chain.reverse_committed, 1)

    def test_max_invocation_counts_fail_before_journal_or_effect(
        self,
    ) -> None:
        forward = _base_context()
        forward["effect"] = _restart_effect(
            current=opaque_fingerprint(5),
            forward_invocations=1_000_000,
        )
        transaction = SyntheticJournalTransaction.begin(
            store=forward["store"],
            binding=forward["binding"],
            effect_state=forward["effect"],
        )
        forward_journal = forward["medium"].snapshot()
        forward_effect = forward["effect"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            transaction.run_next_forward(
                profile=forward["profile"],
                authorization=forward["forward"],
                inspected_at_epoch=1_800_000_100,
                action_at_epoch=1_800_000_101,
            )
        self.assertEqual(forward["medium"].snapshot(), forward_journal)
        self.assertEqual(forward["effect"].snapshot(), forward_effect)

        reverse = _base_context()
        transaction = SyntheticJournalTransaction.begin(
            store=reverse["store"],
            binding=reverse["binding"],
            effect_state=reverse["effect"],
        )
        transaction.run_next_forward(
            profile=reverse["profile"],
            authorization=reverse["forward"],
            inspected_at_epoch=1_800_000_100,
            action_at_epoch=1_800_000_101,
        )
        reverse["effect"] = _restart_effect(
            current=opaque_fingerprint(6),
            forward_invocations=1,
            reverse_invocations=1_000_000,
        )
        reverse_journal = reverse["medium"].snapshot()
        reverse_effect = reverse["effect"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            rollback_next_synthetic(
                store=reverse["store"],
                binding=reverse["binding"],
                profile=reverse["profile"],
                recovery_authorization=reverse["recovery"],
                effect_state=reverse["effect"],
                observed_at_epoch=1_800_000_102,
                action_at_epoch=1_800_000_103,
            )
        self.assertEqual(reverse["medium"].snapshot(), reverse_journal)
        self.assertEqual(reverse["effect"].snapshot(), reverse_effect)

    def test_every_reverse_boundary_is_classified_and_exactly_retried(
        self,
    ) -> None:
        for cut_point in CRASH_POINTS:
            with self.subTest(cut_point=cut_point):
                context = _reverse_crash(cut_point)
                result = _inspect(context, include_resume=False)
                expected = (
                    JournalOperationStatus.SAFE_ABORT
                    if cut_point is TransactionCutPoint.AFTER_COMMIT
                    else JournalOperationStatus.ROLLBACK_REQUIRED
                )
                self.assertEqual(result.status, expected)

                if cut_point is not TransactionCutPoint.AFTER_COMMIT:
                    store = DurableJournalStore.recover_synthetic(
                        medium=context["medium"],
                        binding=context["binding"],
                    )
                    rollback_next_synthetic(
                        store=store,
                        binding=context["binding"],
                        profile=context["profile"],
                        recovery_authorization=context["recovery"],
                        effect_state=context["effect"],
                        observed_at_epoch=1_800_000_110,
                        action_at_epoch=1_800_000_111,
                    )
                chain = verify_synthetic_journal_snapshot(
                    context["medium"].snapshot(),
                    binding=context["binding"],
                )
                self.assertEqual(chain.reverse_committed, 1)
                self.assertEqual(context["effect"].reverse_invocations, 1)
                self.assertEqual(
                    context["effect"].observation_fingerprint,
                    opaque_fingerprint(5),
                )

    def test_durable_reverse_observation_never_allows_replay_after_drift(
        self,
    ) -> None:
        context = _reverse_crash(TransactionCutPoint.AFTER_OBSERVED)
        context["effect"] = SyntheticEffectStateV1.from_restart(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
            current_observation_fingerprint=opaque_fingerprint(6),
            identity_mapping_intact=True,
            forward_invocations=1,
            reverse_invocations=1,
        )

        result = _inspect(context, include_resume=False)

        self.assertEqual(
            result.status,
            JournalOperationStatus.INCIDENT_STOP,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            rollback_next_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                recovery_authorization=context["recovery"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["effect"].reverse_invocations, 1)

    def test_not_applied_observation_cannot_be_overwritten_by_resume(
        self,
    ) -> None:
        context = _forward_crash(TransactionCutPoint.AFTER_INTENT)
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_FINAL_STABLE_REREAD
        )
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            rollback_next_synthetic(
                store=store,
                binding=context["binding"],
                profile=context["profile"],
                recovery_authorization=context["recovery"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        store.close()
        context["medium"].simulate_restart()

        result = _inspect(context, include_resume=True)

        self.assertEqual(
            result.status,
            JournalOperationStatus.ROLLBACK_REQUIRED,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        before = context["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_OBSERVATION_AMBIGUOUS$"
        ):
            resume_synthetic(
                store=recovered,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=context["resume"],
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_112,
                action_at_epoch=1_800_000_113,
            )
        self.assertEqual(context["medium"].snapshot(), before)
        self.assertEqual(context["effect"].forward_invocations, 0)
        rollback_next_synthetic(
            store=recovered,
            binding=context["binding"],
            profile=context["profile"],
            recovery_authorization=context["recovery"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_114,
            action_at_epoch=1_800_000_115,
        )
        chain = verify_synthetic_journal_snapshot(
            context["medium"].snapshot(),
            binding=context["binding"],
        )
        self.assertEqual(chain.forward_committed, 1)
        self.assertEqual(chain.reverse_committed, 0)


def _base_context() -> dict[str, object]:
    profile, forward, recovery = valid_operation_contracts()
    _profile, resume, _recovery = valid_operation_contracts(
        forward_phase="resume"
    )
    binding = valid_operation_binding()
    medium = SyntheticJournalMediumV1.empty(
        platform=DurabilityPlatform.LINUX
    )
    store = DurableJournalStore.begin_synthetic(
        medium=medium,
        binding=binding,
    )
    effect = SyntheticEffectStateV1.create(
        initial_observation_fingerprint=opaque_fingerprint(5),
        prepared_observation_fingerprint=opaque_fingerprint(6),
        published_observation_fingerprint=opaque_fingerprint(10),
    )
    return {
        "profile": profile,
        "forward": forward,
        "resume": resume,
        "recovery": recovery,
        "binding": binding,
        "medium": medium,
        "store": store,
        "effect": effect,
    }


def _forward_crash(
    cut_point: TransactionCutPoint,
) -> dict[str, object]:
    context = _base_context()
    transaction = SyntheticJournalTransaction.begin(
        store=context["store"],
        binding=context["binding"],
        effect_state=context["effect"],
    )
    with unittest.TestCase().assertRaisesRegex(
        JournalContractError, "^SYNTHETIC_CRASH$"
    ):
        transaction.run_next_forward(
            profile=context["profile"],
            authorization=context["forward"],
            inspected_at_epoch=1_800_000_100,
            action_at_epoch=1_800_000_101,
            cut_point=cut_point,
        )
    _restart(context)
    return context


def _reverse_crash(
    cut_point: TransactionCutPoint,
) -> dict[str, object]:
    context = _base_context()
    transaction = SyntheticJournalTransaction.begin(
        store=context["store"],
        binding=context["binding"],
        effect_state=context["effect"],
    )
    transaction.run_next_forward(
        profile=context["profile"],
        authorization=context["forward"],
        inspected_at_epoch=1_800_000_100,
        action_at_epoch=1_800_000_101,
    )
    with unittest.TestCase().assertRaisesRegex(
        JournalContractError, "^SYNTHETIC_CRASH$"
    ):
        rollback_next_synthetic(
            store=context["store"],
            binding=context["binding"],
            profile=context["profile"],
            recovery_authorization=context["recovery"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_102,
            action_at_epoch=1_800_000_103,
            cut_point=cut_point,
        )
    _restart(context)
    return context


def _pending_followup_crash(
    *,
    direction: str,
    event_code: str,
    cut_point: DurabilityCutPoint,
) -> dict[str, object]:
    transaction_cut_point = (
        TransactionCutPoint.AFTER_EFFECT
        if event_code == "EFFECT_OBSERVED"
        else TransactionCutPoint.AFTER_OBSERVED
    )
    context = (
        _forward_crash(transaction_cut_point)
        if direction == "FORWARD"
        else _reverse_crash(transaction_cut_point)
    )
    store = DurableJournalStore.recover_synthetic(
        medium=context["medium"],
        binding=context["binding"],
    )
    previous = JournalRecordV1.from_json(
        context["medium"].snapshot().published_records[-1]
    )
    candidate = JournalRecordV1.create(
        journal_record_body_after(
            previous,
            event_code=event_code,
        )
    )
    context["medium"].cut_point = cut_point
    with unittest.TestCase().assertRaisesRegex(
        JournalContractError, "^SYNTHETIC_CRASH$"
    ):
        store.append_record(candidate)
    store.close()
    context["medium"].simulate_restart()
    return context


def _restart(context: dict[str, object]) -> None:
    context["store"].close()
    context["medium"].simulate_restart()


def _restart_effect(
    *,
    current: str,
    prepared: str = "",
    identity_mapping_intact: bool = True,
    forward_invocations: int = 0,
    reverse_invocations: int = 0,
) -> SyntheticEffectStateV1:
    return SyntheticEffectStateV1.from_restart(
        initial_observation_fingerprint=opaque_fingerprint(5),
        prepared_observation_fingerprint=(
            prepared or opaque_fingerprint(6)
        ),
        published_observation_fingerprint=opaque_fingerprint(10),
        current_observation_fingerprint=current,
        identity_mapping_intact=identity_mapping_intact,
        forward_invocations=forward_invocations,
        reverse_invocations=reverse_invocations,
    )


def _resume(
    context: dict[str, object],
    store: DurableJournalStore,
    *,
    cut_point: TransactionCutPoint = TransactionCutPoint.NONE,
) -> None:
    resume_synthetic(
        store=store,
        binding=context["binding"],
        profile=context["profile"],
        resume_authorization=context["resume"],
        effect_state=context["effect"],
        observed_at_epoch=1_800_000_110,
        action_at_epoch=1_800_000_111,
        cut_point=cut_point,
    )


def _assert_stable_chain(
    test_case: unittest.TestCase,
    context: dict[str, object],
    *,
    forward_committed: int,
) -> None:
    snapshot = context["medium"].snapshot()
    records = tuple(
        JournalRecordV1.from_json(payload)
        for payload in snapshot.published_records
    )
    test_case.assertEqual(
        snapshot.stable_reread_hashes,
        tuple(record.record_hash for record in records),
    )
    chain = verify_synthetic_journal_snapshot(
        snapshot,
        binding=context["binding"],
    )
    test_case.assertEqual(chain.forward_committed, forward_committed)


def _inspect(
    context: dict[str, object],
    *,
    include_resume: bool,
):
    return inspect_restart(
        snapshot=context["medium"].snapshot(),
        binding=context["binding"],
        profile=context["profile"],
        effect_snapshot=context["effect"].snapshot(),
        resume_authorization=context["resume"] if include_resume else None,
        recovery_authorization=context["recovery"],
        observed_at_epoch=1_800_000_110,
    )


if __name__ == "__main__":
    unittest.main()
