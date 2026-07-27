"""Issue #52 restart inspection and recovery classification tests."""

from __future__ import annotations

import copy
import hashlib
import pickle
import threading
import unittest

from backend.cutover_journal import (
    DurabilityCutPoint,
    DurabilityPlatform,
    DurableJournalStore,
    JournalContractError,
    JournalOperationPhase,
    JournalOperationBindingV1,
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
    canonical_json,
    journal_record_body_after,
    opaque_fingerprint,
    replacement_recovery_authorization,
    valid_bound_journal_record_body,
    valid_operation_binding,
    valid_operation_contracts,
)


class JournalRecoveryTests(unittest.TestCase):
    def test_operation_binding_requires_prebound_recovery_authority(
        self,
    ) -> None:
        profile, forward, recovery = valid_operation_contracts()

        binding = JournalOperationBindingV1.create(
            profile=profile,
            forward_authorization=forward,
            recovery_authorization=recovery,
            owner_fingerprint=opaque_fingerprint(7),
            observed_at_epoch=1_800_000_100,
        )

        self.assertEqual(
            binding.recovery_authorization_fingerprint,
            recovery.authorization_fingerprint,
        )
        self.assertNotIn(binding.profile_fingerprint, repr(binding))
        self.assertFalse(hasattr(binding, "__dict__"))

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_AUTHORIZATION_INVALID$"
        ):
            JournalOperationBindingV1.create(
                profile=profile,
                forward_authorization=forward,
                recovery_authorization=None,
                owner_fingerprint=opaque_fingerprint(7),
                observed_at_epoch=1_800_000_100,
            )

    def test_forward_transaction_journals_before_effect_and_commits(self) -> None:
        profile, forward, recovery = valid_operation_contracts()
        binding = JournalOperationBindingV1.create(
            profile=profile,
            forward_authorization=forward,
            recovery_authorization=recovery,
            owner_fingerprint=opaque_fingerprint(7),
            observed_at_epoch=1_800_000_100,
        )
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
        transaction = SyntheticJournalTransaction.begin(
            store=store,
            binding=binding,
            effect_state=effect,
        )

        transaction.run_next_forward(
            profile=profile,
            authorization=forward,
            inspected_at_epoch=1_800_000_100,
            action_at_epoch=1_800_000_101,
        )
        first_chain = verify_synthetic_journal_snapshot(
            medium.snapshot(),
            binding=binding,
        )

        self.assertEqual(first_chain.forward_committed, 1)
        self.assertEqual(first_chain.open_event, None)
        self.assertEqual(effect.observation_fingerprint, opaque_fingerprint(6))
        self.assertEqual(effect.forward_invocations, 1)

        transaction.run_next_forward(
            profile=profile,
            authorization=forward,
            inspected_at_epoch=1_800_000_102,
            action_at_epoch=1_800_000_103,
        )
        complete_chain = verify_synthetic_journal_snapshot(
            medium.snapshot(),
            binding=binding,
        )

        self.assertEqual(complete_chain.forward_committed, 2)
        self.assertEqual(effect.observation_fingerprint, opaque_fingerprint(10))
        self.assertEqual(effect.forward_invocations, 2)

    def test_no_effect_before_durable_intent_or_second_auth_check(self) -> None:
        profile, forward, recovery = valid_operation_contracts()
        binding = JournalOperationBindingV1.create(
            profile=profile,
            forward_authorization=forward,
            recovery_authorization=recovery,
            owner_fingerprint=opaque_fingerprint(7),
            observed_at_epoch=1_800_000_100,
        )
        cases = (
            (
                DurabilityCutPoint.AFTER_PUBLISHED_FILE_BARRIER,
                TransactionCutPoint.NONE,
                1_800_000_101,
                "SYNTHETIC_CRASH",
            ),
            (
                DurabilityCutPoint.NONE,
                TransactionCutPoint.NONE,
                forward.expires_at_epoch,
                "JOURNAL_AUTHORIZATION_INVALID",
            ),
        )
        for medium_cut, transaction_cut, action_epoch, code in cases:
            with self.subTest(code=code):
                medium = SyntheticJournalMediumV1.empty(
                    platform=DurabilityPlatform.WINDOWS,
                    cut_point=medium_cut,
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
                transaction = SyntheticJournalTransaction.begin(
                    store=store,
                    binding=binding,
                    effect_state=effect,
                )

                with self.assertRaisesRegex(
                    JournalContractError, f"^{code}$"
                ):
                    transaction.run_next_forward(
                        profile=profile,
                        authorization=forward,
                        inspected_at_epoch=1_800_000_100,
                        action_at_epoch=action_epoch,
                        cut_point=transaction_cut,
                    )

                self.assertEqual(effect.forward_invocations, 0)

    def test_crash_after_effect_leaves_open_intent_without_blind_retry(
        self,
    ) -> None:
        profile, forward, recovery = valid_operation_contracts()
        binding = JournalOperationBindingV1.create(
            profile=profile,
            forward_authorization=forward,
            recovery_authorization=recovery,
            owner_fingerprint=opaque_fingerprint(7),
            observed_at_epoch=1_800_000_100,
        )
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
        transaction = SyntheticJournalTransaction.begin(
            store=store,
            binding=binding,
            effect_state=effect,
        )

        with self.assertRaisesRegex(
            JournalContractError, "^SYNTHETIC_CRASH$"
        ):
            transaction.run_next_forward(
                profile=profile,
                authorization=forward,
                inspected_at_epoch=1_800_000_100,
                action_at_epoch=1_800_000_101,
                cut_point=TransactionCutPoint.AFTER_EFFECT,
            )

        chain = verify_synthetic_journal_snapshot(
            medium.snapshot(),
            binding=binding,
        )
        self.assertEqual(chain.open_event, "INTENT")
        self.assertEqual(effect.observation_fingerprint, opaque_fingerprint(6))
        self.assertEqual(effect.forward_invocations, 1)

    def test_restart_inspection_is_read_only_and_public_shape_is_closed(
        self,
    ) -> None:
        profile, _forward, recovery = valid_operation_contracts()
        binding = valid_operation_binding()
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        effect = SyntheticEffectStateV1.create(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
        )
        journal_before = medium.snapshot()
        effect_before = effect.snapshot()

        result = inspect_restart(
            snapshot=journal_before,
            binding=binding,
            profile=profile,
            effect_snapshot=effect_before,
            resume_authorization=None,
            recovery_authorization=recovery,
            observed_at_epoch=1_800_000_100,
        )

        self.assertEqual(result.status, JournalOperationStatus.SAFE_ABORT)
        self.assertEqual(result.phase, JournalOperationPhase.TERMINAL)
        self.assertEqual(
            set(result.to_mapping()),
            {"status", "receipt_fingerprint", "phase", "counts"},
        )
        self.assertEqual(medium.snapshot(), journal_before)
        self.assertEqual(effect.snapshot(), effect_before)
        self.assertFalse(hasattr(result, "append_record"))
        self.assertFalse(hasattr(result, "__dict__"))

    def test_restart_classifies_pre_post_and_unknown_without_effect(
        self,
    ) -> None:
        for cut_point, expected_phase in (
            (
                TransactionCutPoint.AFTER_INTENT,
                JournalOperationPhase.FORWARD_ACTION,
            ),
            (
                TransactionCutPoint.AFTER_EFFECT,
                JournalOperationPhase.FORWARD_OBSERVATION,
            ),
        ):
            with self.subTest(cut_point=cut_point):
                context = _crashed_forward_context(cut_point=cut_point)
                result = inspect_restart(
                    snapshot=context["medium"].snapshot(),
                    binding=context["binding"],
                    profile=context["profile"],
                    effect_snapshot=context["effect"].snapshot(),
                    resume_authorization=context["resume"],
                    recovery_authorization=context["recovery"],
                    observed_at_epoch=1_800_000_110,
                )

                self.assertEqual(
                    result.status,
                    JournalOperationStatus.RESUME_ALLOWED,
                )
                self.assertEqual(result.phase, expected_phase)
                self.assertEqual(context["effect"].forward_invocations, int(
                    cut_point is TransactionCutPoint.AFTER_EFFECT
                ))

        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_INTENT
        )
        unknown = SyntheticEffectStateV1.from_restart(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
            current_observation_fingerprint=opaque_fingerprint(999),
            identity_mapping_intact=True,
        )
        result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=unknown.snapshot(),
            resume_authorization=context["resume"],
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_110,
        )
        self.assertEqual(result.status, JournalOperationStatus.INCIDENT_STOP)

    def test_expired_resume_uses_only_prebound_recovery_classification(
        self,
    ) -> None:
        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_EFFECT
        )
        _profile, expired_resume, _recovery = valid_operation_contracts(
            forward_phase="resume",
            forward_expires_at=1_800_000_105,
        )

        result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=expired_resume,
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_110,
        )

        self.assertEqual(
            result.status,
            JournalOperationStatus.ROLLBACK_REQUIRED,
        )
        self.assertEqual(
            result.phase,
            JournalOperationPhase.FORWARD_OBSERVATION,
        )

        _profile, _resume, expired_recovery = valid_operation_contracts(
            recovery_expires_at=1_800_000_105,
        )
        incident = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=expired_resume,
            recovery_authorization=expired_recovery,
            observed_at_epoch=1_800_000_110,
        )
        self.assertEqual(
            incident.status,
            JournalOperationStatus.INCIDENT_STOP,
        )

    def test_complete_forward_plan_is_cutover_succeeded(self) -> None:
        profile, forward, recovery = valid_operation_contracts()
        binding = valid_operation_binding()
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.WINDOWS
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
        transaction = SyntheticJournalTransaction.begin(
            store=store,
            binding=binding,
            effect_state=effect,
        )
        for epoch in (1_800_000_100, 1_800_000_102):
            transaction.run_next_forward(
                profile=profile,
                authorization=forward,
                inspected_at_epoch=epoch,
                action_at_epoch=epoch + 1,
            )
        store.close()
        medium.simulate_restart()

        result = inspect_restart(
            snapshot=medium.snapshot(),
            binding=binding,
            profile=profile,
            effect_snapshot=effect.snapshot(),
            resume_authorization=None,
            recovery_authorization=recovery,
            observed_at_epoch=1_800_000_110,
        )

        self.assertEqual(
            result.status,
            JournalOperationStatus.CUTOVER_SUCCEEDED,
        )
        self.assertEqual(result.counts.forward_committed, 2)

    def test_explicit_resume_exact_retry_never_repeats_post_effect(self) -> None:
        for cut_point, expected_invocations in (
            (TransactionCutPoint.AFTER_INTENT, 1),
            (TransactionCutPoint.AFTER_EFFECT, 1),
        ):
            with self.subTest(cut_point=cut_point):
                context = _crashed_forward_context(cut_point=cut_point)
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
                    expected_invocations,
                )
                records = tuple(
                    JournalRecordV1.from_json(payload)
                    for payload in context[
                        "medium"
                    ].snapshot().published_records
                )
                self.assertIn(
                    "RESUME_BOUND",
                    tuple(record.event_code for record in records),
                )

    def test_explicit_resume_revalidates_expiry_before_any_append(
        self,
    ) -> None:
        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_INTENT
        )
        _profile, short_resume, _recovery = valid_operation_contracts(
            forward_phase="resume",
            forward_expires_at=1_800_000_105,
        )
        inspected = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=short_resume,
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_104,
        )
        self.assertEqual(
            inspected.status,
            JournalOperationStatus.RESUME_ALLOWED,
        )
        before = context["medium"].snapshot()
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_AUTHORIZATION_INVALID$"
        ):
            resume_synthetic(
                store=store,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=short_resume,
                effect_state=context["effect"],
                observed_at_epoch=short_resume.expires_at_epoch,
                action_at_epoch=short_resume.expires_at_epoch,
            )

        self.assertEqual(context["medium"].snapshot(), before)
        self.assertEqual(context["effect"].forward_invocations, 0)

    def test_resume_between_steps_binds_new_authorization_to_next_intent(
        self,
    ) -> None:
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
        transaction = SyntheticJournalTransaction.begin(
            store=store,
            binding=binding,
            effect_state=effect,
        )
        transaction.run_next_forward(
            profile=profile,
            authorization=forward,
            inspected_at_epoch=1_800_000_100,
            action_at_epoch=1_800_000_101,
        )
        store.close()
        medium.simulate_restart()
        recovered = DurableJournalStore.recover_synthetic(
            medium=medium,
            binding=binding,
        )

        resume_synthetic(
            store=recovered,
            binding=binding,
            profile=profile,
            resume_authorization=resume,
            effect_state=effect,
            observed_at_epoch=1_800_000_110,
            action_at_epoch=1_800_000_111,
        )

        records = tuple(
            JournalRecordV1.from_json(payload)
            for payload in medium.snapshot().published_records
        )
        second_intent = records[3]
        self.assertEqual(second_intent.event_code, "INTENT")
        self.assertEqual(
            second_intent.authorization_fingerprint,
            resume.authorization_fingerprint,
        )
        self.assertEqual(effect.forward_invocations, 2)

    def test_prebound_recovery_reconciles_and_reverses_after_expiry(
        self,
    ) -> None:
        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_EFFECT
        )
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
            observed_at_epoch=1_800_000_700,
            action_at_epoch=1_800_000_701,
        )
        chain = verify_synthetic_journal_snapshot(
            context["medium"].snapshot(),
            binding=context["binding"],
        )

        self.assertEqual(chain.forward_committed, 1)
        self.assertEqual(chain.reverse_committed, 1)
        self.assertEqual(context["effect"].forward_invocations, 1)
        self.assertEqual(context["effect"].reverse_invocations, 1)
        self.assertEqual(
            context["effect"].observation_fingerprint,
            opaque_fingerprint(5),
        )

    def test_rollback_steps_are_journal_derived_lifo(self) -> None:
        profile, forward, recovery = valid_operation_contracts()
        binding = valid_operation_binding()
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.WINDOWS
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
        transaction = SyntheticJournalTransaction.begin(
            store=store,
            binding=binding,
            effect_state=effect,
        )
        for epoch in (1_800_000_100, 1_800_000_102):
            transaction.run_next_forward(
                profile=profile,
                authorization=forward,
                inspected_at_epoch=epoch,
                action_at_epoch=epoch + 1,
            )
        store.close()
        medium.simulate_restart()
        recovered = DurableJournalStore.recover_synthetic(
            medium=medium,
            binding=binding,
        )
        for epoch in (1_800_000_700, 1_800_000_702):
            rollback_next_synthetic(
                store=recovered,
                binding=binding,
                profile=profile,
                recovery_authorization=recovery,
                effect_state=effect,
                observed_at_epoch=epoch,
                action_at_epoch=epoch + 1,
            )

        records = tuple(
            JournalRecordV1.from_json(payload)
            for payload in medium.snapshot().published_records
        )
        reverse_intents = tuple(
            record
            for record in records
            if record.direction == "REVERSE"
            and record.event_code == "INTENT"
        )
        self.assertEqual(
            tuple(record.step_code for record in reverse_intents),
            ("SYNTHETIC_PUBLISH", "SYNTHETIC_PREPARE"),
        )
        self.assertEqual(effect.reverse_invocations, 2)
        self.assertEqual(effect.observation_fingerprint, opaque_fingerprint(5))

    def test_replacement_recovery_and_broken_identity_are_incidents(
        self,
    ) -> None:
        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_EFFECT
        )
        _profile, expired_resume, _recovery = valid_operation_contracts(
            forward_phase="resume",
            forward_expires_at=1_800_000_105,
        )
        replacement = replacement_recovery_authorization()
        result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=expired_resume,
            recovery_authorization=replacement,
            observed_at_epoch=1_800_000_110,
        )
        self.assertEqual(
            result.status,
            JournalOperationStatus.INCIDENT_STOP,
        )

        broken = SyntheticEffectStateV1.from_restart(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
            current_observation_fingerprint=opaque_fingerprint(6),
            identity_mapping_intact=False,
            forward_invocations=1,
        )
        broken_result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=broken.snapshot(),
            resume_authorization=context["resume"],
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_110,
        )
        self.assertEqual(
            broken_result.status,
            JournalOperationStatus.INCIDENT_STOP,
        )

        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        before = context["medium"].snapshot()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_AUTHORIZATION_INVALID$"
        ):
            rollback_next_synthetic(
                store=store,
                binding=context["binding"],
                profile=context["profile"],
                recovery_authorization=replacement,
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        self.assertEqual(context["medium"].snapshot(), before)

    def test_expired_resume_binding_can_be_replaced_by_fresh_authority(
        self,
    ) -> None:
        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_INTENT
        )
        _profile, short_resume, _recovery = valid_operation_contracts(
            forward_phase="resume",
            forward_expires_at=1_800_000_105,
        )
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_AUTHORIZATION_INVALID$"
        ):
            resume_synthetic(
                store=store,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=short_resume,
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_104,
                action_at_epoch=1_800_000_105,
            )
        store.close()
        context["medium"].simulate_restart()
        _profile, fresh_resume, _recovery = valid_operation_contracts(
            forward_phase="resume",
            forward_expires_at=1_800_000_700,
        )

        result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=fresh_resume,
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_110,
        )
        self.assertEqual(
            result.status,
            JournalOperationStatus.RESUME_ALLOWED,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        resume_synthetic(
            store=recovered,
            binding=context["binding"],
            profile=context["profile"],
            resume_authorization=fresh_resume,
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

    def test_recovery_commits_observed_fact_across_expired_resume_binding(
        self,
    ) -> None:
        context = _crashed_forward_context(
            cut_point=TransactionCutPoint.AFTER_OBSERVED
        )
        _profile, short_resume, _recovery = valid_operation_contracts(
            forward_phase="resume",
            forward_expires_at=1_800_000_105,
        )
        store = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_AUTHORIZATION_INVALID$"
        ):
            resume_synthetic(
                store=store,
                binding=context["binding"],
                profile=context["profile"],
                resume_authorization=short_resume,
                effect_state=context["effect"],
                observed_at_epoch=1_800_000_104,
                action_at_epoch=1_800_000_105,
            )
        store.close()
        context["medium"].simulate_restart()
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )

        rollback_next_synthetic(
            store=recovered,
            binding=context["binding"],
            profile=context["profile"],
            recovery_authorization=context["recovery"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_700,
            action_at_epoch=1_800_000_701,
        )

        chain = verify_synthetic_journal_snapshot(
            context["medium"].snapshot(),
            binding=context["binding"],
        )
        self.assertEqual(chain.forward_committed, 1)
        self.assertEqual(chain.reverse_committed, 1)
        self.assertEqual(context["effect"].forward_invocations, 1)
        self.assertEqual(context["effect"].reverse_invocations, 1)

    def test_recovery_resolves_pending_forward_before_lifo_reverse(
        self,
    ) -> None:
        context = _one_committed_forward_context()
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_PENDING_WRITE
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
                inspected_at_epoch=1_800_000_102,
                action_at_epoch=1_800_000_103,
            )
        context["store"].close()
        context["medium"].simulate_restart()
        result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=None,
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_110,
        )
        self.assertEqual(
            result.status,
            JournalOperationStatus.ROLLBACK_REQUIRED,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )

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
        self.assertEqual(chain.forward_committed, 2)
        self.assertEqual(chain.reverse_committed, 1)
        self.assertEqual(context["effect"].observation_fingerprint, opaque_fingerprint(5))

    def test_pending_reverse_is_classified_for_recovery_not_resume(
        self,
    ) -> None:
        context = _one_committed_forward_context()
        context["medium"].cut_point = (
            DurabilityCutPoint.AFTER_PENDING_WRITE
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
                observed_at_epoch=1_800_000_102,
                action_at_epoch=1_800_000_103,
            )
        context["store"].close()
        context["medium"].simulate_restart()
        _profile, resume, _recovery = valid_operation_contracts(
            forward_phase="resume"
        )

        result = inspect_restart(
            snapshot=context["medium"].snapshot(),
            binding=context["binding"],
            profile=context["profile"],
            effect_snapshot=context["effect"].snapshot(),
            resume_authorization=resume,
            recovery_authorization=context["recovery"],
            observed_at_epoch=1_800_000_110,
        )

        self.assertEqual(
            result.status,
            JournalOperationStatus.ROLLBACK_REQUIRED,
        )
        recovered = DurableJournalStore.recover_synthetic(
            medium=context["medium"],
            binding=context["binding"],
        )
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

    def test_profile_binding_mismatch_rejects_all_action_paths(self) -> None:
        profile, forward, recovery = valid_operation_contracts()
        binding = _forged_profile_binding()
        for action in ("execute", "resume", "rollback"):
            with self.subTest(action=action):
                _assert_profile_binding_action_rejected(
                    self,
                    action=action,
                    profile=profile,
                    forward=forward,
                    recovery=recovery,
                    binding=binding,
                )

    def test_effect_requires_a_store_issued_durable_intent_permit(
        self,
    ) -> None:
        effect = SyntheticEffectStateV1.create(
            initial_observation_fingerprint=opaque_fingerprint(5),
            prepared_observation_fingerprint=opaque_fingerprint(6),
            published_observation_fingerprint=opaque_fingerprint(10),
        )

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            effect._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=None,
                durable_permit=None,
            )
        self.assertEqual(effect.forward_invocations, 0)

    def test_durable_intent_permit_is_owner_bound_and_single_use(
        self,
    ) -> None:
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
        permit = store.append_record(intent)
        effect = _fresh_effect_state()

        effect._apply(
            direction="FORWARD",
            step_code="SYNTHETIC_PREPARE",
            intent=intent,
            durable_permit=permit,
        )

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            _fresh_effect_state()._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=intent,
                durable_permit=permit,
            )
        second_medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        second_store = DurableJournalStore.begin_synthetic(
            medium=second_medium,
            binding=binding,
        )
        stale_permit = second_store.append_record(intent)
        second_store.close()
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            _fresh_effect_state()._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=intent,
                durable_permit=stale_permit,
            )

    def test_historical_intent_cannot_mint_a_new_effect_permit(
        self,
    ) -> None:
        context = _one_committed_forward_context()
        intent = JournalRecordV1.from_json(
            context["medium"].snapshot().published_records[0]
        )
        rollback_next_synthetic(
            store=context["store"],
            binding=context["binding"],
            profile=context["profile"],
            recovery_authorization=context["recovery"],
            effect_state=context["effect"],
            observed_at_epoch=1_800_000_102,
            action_at_epoch=1_800_000_103,
        )
        before = context["effect"].snapshot()

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            context["store"]._durable_permit_for(intent)

        self.assertEqual(context["effect"].snapshot(), before)

    def test_permit_copy_and_deepcopy_are_rejected(self) -> None:
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
        permit = store.append_record(intent)

        for copier in (copy.copy, copy.deepcopy):
            with self.subTest(copier=copier.__name__):
                with self.assertRaises(TypeError):
                    copier(permit)
        with self.assertRaises(TypeError):
            pickle.dumps(permit)

    def test_all_permits_share_current_active_intent_consumption(self) -> None:
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
        first = store.append_record(intent)
        second = store._durable_permit_for(intent)
        effect = _fresh_effect_state()

        effect._apply(
            direction="FORWARD",
            step_code="SYNTHETIC_PREPARE",
            intent=intent,
            durable_permit=second,
        )

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            _fresh_effect_state()._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=intent,
                durable_permit=first,
            )

    def test_permit_cannot_reset_store_owned_consumption_state(
        self,
    ) -> None:
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
        permit = store.append_record(intent)
        _fresh_effect_state()._apply(
            direction="FORWARD",
            step_code="SYNTHETIC_PREPARE",
            intent=intent,
            durable_permit=permit,
        )

        with self.assertRaises(AttributeError):
            permit._issuance.consumed = False
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            _fresh_effect_state()._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=intent,
                durable_permit=permit,
            )

    def test_concurrent_permit_consumption_has_exactly_one_winner(
        self,
    ) -> None:
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
        permit = store.append_record(intent)
        barrier = threading.Barrier(2)
        outcomes = []

        def consume(effect):
            try:
                barrier.wait(timeout=5)
                effect._apply(
                    direction="FORWARD",
                    step_code="SYNTHETIC_PREPARE",
                    intent=intent,
                    durable_permit=permit,
                )
                outcomes.append("OK")
            except JournalContractError as error:
                outcomes.append(str(error))

        threads = [
            threading.Thread(target=consume, args=(_fresh_effect_state(),))
            for _index in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(
            sorted(outcomes),
            ["JOURNAL_EFFECT_PERMIT_INVALID", "OK"],
        )

    def test_concurrent_first_permit_mint_has_one_effect_winner(
        self,
    ) -> None:
        binding = valid_operation_binding()
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        initial = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        intent = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        initial.append_record(intent)
        initial.close()
        medium.simulate_restart()
        store = DurableJournalStore.recover_synthetic(
            medium=medium,
            binding=binding,
        )
        entered = threading.Event()
        release = threading.Event()
        busy_done = threading.Event()
        start = threading.Barrier(3)

        class PausingScope(dict):
            def get(self, key, default=None):
                entered.set()
                release.wait(timeout=5)
                return super().get(key, default)

        store._permit_scope_tokens = PausingScope()
        outcomes = []
        effects = [_fresh_effect_state(), _fresh_effect_state()]

        def mint_and_apply(effect):
            try:
                start.wait(timeout=5)
                permit = store._durable_permit_for(intent)
                effect._apply(
                    direction="FORWARD",
                    step_code="SYNTHETIC_PREPARE",
                    intent=intent,
                    durable_permit=permit,
                )
                outcomes.append("OK")
            except JournalContractError as error:
                outcomes.append(str(error))
                busy_done.set()

        threads = [
            threading.Thread(target=mint_and_apply, args=(effect,))
            for effect in effects
        ]
        for thread in threads:
            thread.start()
        start.wait(timeout=5)
        self.assertTrue(entered.wait(timeout=5))
        self.assertTrue(busy_done.wait(timeout=5))
        release.set()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(
            sorted(outcomes),
            ["JOURNAL_MEDIUM_BUSY", "OK"],
        )
        self.assertEqual(
            sorted(effect.forward_invocations for effect in effects),
            [0, 1],
        )

    def test_head_cannot_advance_during_permit_claim_and_effect(
        self,
    ) -> None:
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
        permit = store.append_record(intent)
        rebound = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="RESUME_BOUND",
                authorization_fingerprint=opaque_fingerprint(11),
            )
        )
        entered = threading.Event()
        release = threading.Event()

        class PausingClaim(dict):
            def pop(self, key, default=None):
                entered.set()
                release.wait(timeout=5)
                return super().pop(key, default)

        store._active_permit_tokens = PausingClaim(
            store._active_permit_tokens
        )
        outcome = []

        def consume():
            try:
                _fresh_effect_state()._apply(
                    direction="FORWARD",
                    step_code="SYNTHETIC_PREPARE",
                    intent=intent,
                    durable_permit=permit,
                )
                outcome.append("OK")
            except JournalContractError as error:
                outcome.append(str(error))

        thread = threading.Thread(target=consume)
        thread.start()
        self.assertTrue(entered.wait(timeout=5))
        try:
            with self.assertRaisesRegex(
                JournalContractError, "^JOURNAL_MEDIUM_BUSY$"
            ):
                store.append_record(rebound)
        finally:
            release.set()
            thread.join(timeout=10)

        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, ["OK"])
        self.assertEqual(
            len(medium.snapshot().published_records), 1
        )

    def test_authorizing_head_must_remain_stable_at_effect_claim(
        self,
    ) -> None:
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
        store.append_record(intent)
        bound = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="RESUME_BOUND",
                authorization_fingerprint=opaque_fingerprint(11),
            )
        )
        store.append_record(bound)
        permit = store._durable_permit_for(intent)
        medium._stable_rereads.pop(bound.sequence)
        effect = _fresh_effect_state()
        before = effect.snapshot()

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            effect._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=intent,
                durable_permit=permit,
            )

        self.assertEqual(effect.snapshot(), before)

    def test_permit_fields_cannot_be_retargeted_to_non_durable_intent(
        self,
    ) -> None:
        binding = valid_operation_binding()
        medium = SyntheticJournalMediumV1.empty(
            platform=DurabilityPlatform.LINUX
        )
        store = DurableJournalStore.begin_synthetic(
            medium=medium,
            binding=binding,
        )
        prepare = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        permit = store.append_record(prepare)
        effect = _fresh_effect_state()
        effect._apply(
            direction="FORWARD",
            step_code="SYNTHETIC_PREPARE",
            intent=prepare,
            durable_permit=permit,
        )
        publish_body = journal_record_body_after(
            prepare,
            event_code="INTENT",
            step_code="SYNTHETIC_PUBLISH",
        )
        publish_body["before_observation_fingerprint"] = opaque_fingerprint(6)
        publish_body["expected_after_observation_fingerprint"] = (
            opaque_fingerprint(10)
        )
        non_durable_publish = JournalRecordV1.create(publish_body)

        with self.assertRaises((AttributeError, TypeError)):
            permit.record_hash = non_durable_publish.record_hash
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            effect._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PUBLISH",
                intent=non_durable_publish,
                durable_permit=permit,
            )

    def test_observed_not_applied_invalidates_outstanding_permit(
        self,
    ) -> None:
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
        permit = store.append_record(intent)
        observed = JournalRecordV1.create(
            journal_record_body_after(
                intent,
                event_code="EFFECT_OBSERVED",
                effect_outcome="NOT_APPLIED",
                authorization_fingerprint=(
                    binding.recovery_authorization_fingerprint
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
        store.append_record(rebound)

        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            store._durable_permit_for(intent)
        with self.assertRaisesRegex(
            JournalContractError, "^JOURNAL_EFFECT_PERMIT_INVALID$"
        ):
            _fresh_effect_state()._apply(
                direction="FORWARD",
                step_code="SYNTHETIC_PREPARE",
                intent=intent,
                durable_permit=permit,
            )


if __name__ == "__main__":
    unittest.main()


def _crashed_forward_context(
    *,
    cut_point: TransactionCutPoint,
) -> dict[str, object]:
    profile, forward, recovery = valid_operation_contracts()
    _same_profile, resume, _same_recovery = valid_operation_contracts(
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
    transaction = SyntheticJournalTransaction.begin(
        store=store,
        binding=binding,
        effect_state=effect,
    )
    with unittest.TestCase().assertRaisesRegex(
        JournalContractError, "^SYNTHETIC_CRASH$"
    ):
        transaction.run_next_forward(
            profile=profile,
            authorization=forward,
            inspected_at_epoch=1_800_000_100,
            action_at_epoch=1_800_000_101,
            cut_point=cut_point,
        )
    store.close()
    medium.simulate_restart()
    return {
        "profile": profile,
        "recovery": recovery,
        "resume": resume,
        "binding": binding,
        "medium": medium,
        "effect": effect,
    }


def _one_committed_forward_context() -> dict[str, object]:
    profile, forward, recovery = valid_operation_contracts()
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
    transaction = SyntheticJournalTransaction.begin(
        store=store,
        binding=binding,
        effect_state=effect,
    )
    transaction.run_next_forward(
        profile=profile,
        authorization=forward,
        inspected_at_epoch=1_800_000_100,
        action_at_epoch=1_800_000_101,
    )
    return {
        "profile": profile,
        "forward": forward,
        "recovery": recovery,
        "binding": binding,
        "medium": medium,
        "store": store,
        "effect": effect,
    }


def _fresh_effect_state() -> SyntheticEffectStateV1:
    return SyntheticEffectStateV1.create(
        initial_observation_fingerprint=opaque_fingerprint(5),
        prepared_observation_fingerprint=opaque_fingerprint(6),
        published_observation_fingerprint=opaque_fingerprint(10),
    )


def _forged_profile_binding() -> JournalOperationBindingV1:
    mapping = valid_operation_binding().to_mapping()
    mapping["profile_fingerprint"] = opaque_fingerprint(999)
    body = dict(mapping)
    body.pop("binding_fingerprint")
    mapping["binding_fingerprint"] = hashlib.sha256(
        canonical_json(body)
    ).hexdigest()
    return JournalOperationBindingV1.from_mapping(mapping)


def _assert_profile_binding_action_rejected(
    test: unittest.TestCase,
    *,
    action: str,
    profile,
    forward,
    recovery,
    binding: JournalOperationBindingV1,
) -> None:
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
    if action != "execute":
        intent = JournalRecordV1.create(
            valid_bound_journal_record_body(binding)
        )
        store.append_record(intent)
    before = medium.snapshot()
    with test.assertRaisesRegex(
        JournalContractError, "^JOURNAL_AUTHORIZATION_INVALID$"
    ):
        if action == "execute":
            transaction = SyntheticJournalTransaction.begin(
                store=store,
                binding=binding,
                effect_state=effect,
            )
            transaction.run_next_forward(
                profile=profile,
                authorization=forward,
                inspected_at_epoch=1_800_000_100,
                action_at_epoch=1_800_000_101,
            )
        elif action == "resume":
            _profile, resume, _recovery = valid_operation_contracts(
                forward_phase="resume"
            )
            resume_synthetic(
                store=store,
                binding=binding,
                profile=profile,
                resume_authorization=resume,
                effect_state=effect,
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
        else:
            rollback_next_synthetic(
                store=store,
                binding=binding,
                profile=profile,
                recovery_authorization=recovery,
                effect_state=effect,
                observed_at_epoch=1_800_000_110,
                action_at_epoch=1_800_000_111,
            )
    test.assertEqual(medium.snapshot(), before)
    test.assertEqual(effect.forward_invocations, 0)
    test.assertEqual(effect.reverse_invocations, 0)
