"""Managed-unit prepare/publish single-actions for Issue #95."""

from __future__ import annotations

import unittest

from backend.r2_foundation_publication_v2 import (
    R2FoundationEffectObservationV2,
    begin_next_foundation_action_v2,
    commit_foundation_effect_v2,
)
from backend.r2_managed_unit_publication_v2 import (
    ManagedProgressStatusV2,
    ManagedUnitPhaseV2,
    ManagedUnitV2,
    R2ManagedRecoveryInspectionV2,
    R2ManagedUnitEffectObservationV2,
    R2ManagedUnitPlanV2,
    begin_next_managed_action_v2,
    classify_managed_pending_v2,
    commit_managed_effect_v2,
    resume_managed_transition_v2,
)
from backend.r2_production_binding import ProductionCommandV2, ProductionRoleV2
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    R2TransactionJournalV2,
)
from backend.r2_transaction_process.production_v2 import complete_transaction_action_v2
from tests.test_r2_foundation_publication_v2 import (
    _claim,
    _inspection,
    _plan as _foundation_plan,
    _restart,
)
from tests.test_r2_transaction_journal_v2 import _binding, _genesis


class R2ManagedUnitPublicationV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.foundation = _foundation_plan(self.binding)
        self.journal = _complete_foundation(self.binding, self.foundation)
        self.plan = _managed_plan(self.binding, self.foundation)

    def test_exact_plan_has_four_prepare_publish_pairs_and_fixed_owners(self):
        restarted = R2ManagedUnitPlanV2.from_json(
            self.plan.to_canonical_json(),
            binding=self.binding,
            foundation_plan=self.foundation,
        )
        self.assertEqual(restarted, self.plan)
        self.assertEqual((restarted.transition_count, restarted.unit_count), (8, 4))
        self.assertEqual(
            tuple((item.unit, item.phase) for item in restarted.transitions),
            tuple(
                (unit, phase)
                for unit in ManagedUnitV2
                for phase in (ManagedUnitPhaseV2.PREPARE, ManagedUnitPhaseV2.PUBLISH)
            ),
        )
        self.assertEqual(
            tuple(item.owner for item in restarted.transitions[::2]),
            (
                ProductionRoleV2.RUNTIME,
                ProductionRoleV2.DATABASE,
                ProductionRoleV2.CRX,
                ProductionRoleV2.CONFIG,
            ),
        )

    def test_all_eight_actions_reconstruct_and_retain_every_object_class(self):
        journal = self.journal
        for transition in self.plan.transitions:
            prior_head = journal.current_head_fingerprint
            claim = _claim(self.binding, self.plan, journal, transition)
            pending = begin_next_managed_action_v2(
                journal=journal, plan=self.plan, claim=claim
            )
            journal = _restart(pending.journal, self.binding)
            completion = complete_transaction_action_v2(
                self.binding,
                claim,
                prior_head,
                transition.transition_instance_fingerprint,
                self.plan.remaining_plan_fingerprint(transition),
            )
            effect = _effect(self.binding, transition, completion)
            self.assertTrue(effect.source_retained)
            self.assertTrue(effect.partial_retained)
            self.assertTrue(effect.failed_unit_retained)
            self.assertEqual(effect.destructive_operations, 0)
            committed = commit_managed_effect_v2(
                journal=journal, plan=self.plan, effect=effect
            )
            self.assertEqual((committed.host_mutations, committed.journal_appends), (1, 2))
            journal = _restart(committed.journal, self.binding)
        self.assertIs(committed.status, ManagedProgressStatusV2.MANAGED_UNITS_COMPLETE)
        self.assertEqual(self.plan.committed_prefix_count(journal), 8)

    def test_database_post_state_requires_acl_and_sqlite_proof_then_no_replay(self):
        journal = self.journal
        for expected in self.plan.transitions[:3]:
            journal = _commit_one(self.binding, self.plan, journal, expected)
        transition = self.plan.transitions[3]
        claim = _claim(self.binding, self.plan, journal, transition)
        pending = begin_next_managed_action_v2(
            journal=journal, plan=self.plan, claim=claim
        )
        receipt = _inspection(
            pending.journal, transition.post_state_fingerprint, post=True
        )
        proof = R2ManagedRecoveryInspectionV2.create(
            binding=self.binding,
            transition=transition,
            inspection=receipt,
            acl_conformance_fingerprint="c" * 64,
            semantic_conformance_fingerprint="d" * 64,
            acl_exact=True,
            semantic_exact=True,
        )
        classified = classify_managed_pending_v2(
            journal=pending.journal, plan=self.plan, inspection=proof
        )
        restarted = _restart(classified.journal, self.binding)
        resume_claim = _claim(
            self.binding,
            self.plan,
            restarted,
            transition,
            command=ProductionCommandV2.RESUME,
        )
        recovered = resume_managed_transition_v2(
            journal=restarted, plan=self.plan, claim=resume_claim
        )
        self.assertIs(
            recovered.status, ManagedProgressStatusV2.MANAGED_RECOVERED_COMMIT
        )
        self.assertEqual((recovered.host_mutations, recovered.journal_appends), (0, 2))
        with self.assertRaisesRegex(ValueError, "R2_MANAGED_UNIT_PUBLICATION_INVALID"):
            R2ManagedRecoveryInspectionV2.create(
                binding=self.binding,
                transition=transition,
                inspection=receipt,
                acl_conformance_fingerprint="c" * 64,
                semantic_conformance_fingerprint="d" * 64,
                acl_exact=True,
                semantic_exact=False,
            )

    def test_pre_state_fresh_authority_and_ambiguous_incident_stop(self):
        transition = self.plan.transitions[0]
        claim = _claim(self.binding, self.plan, self.journal, transition)
        pending = begin_next_managed_action_v2(
            journal=self.journal, plan=self.plan, claim=claim
        )
        for state, pre, expected in (
            (
                transition.pre_state_fingerprint,
                True,
                EffectClassificationV2.EFFECT_ABSENT_EXACT,
            ),
            ("e" * 64, False, EffectClassificationV2.EFFECT_AMBIGUOUS),
        ):
            receipt = _inspection(pending.journal, state, pre=pre)
            proof = R2ManagedRecoveryInspectionV2.create(
                binding=self.binding,
                transition=transition,
                inspection=receipt,
                acl_conformance_fingerprint="c" * 64,
                semantic_conformance_fingerprint="d" * 64,
                acl_exact=True,
                semantic_exact=True,
            )
            classified = classify_managed_pending_v2(
                journal=pending.journal, plan=self.plan, inspection=proof
            )
            self.assertIs(classified.classification, expected)
            if expected is EffectClassificationV2.EFFECT_AMBIGUOUS:
                self.assertIs(classified.status, ManagedProgressStatusV2.INCIDENT_STOP)
            else:
                restarted = _restart(classified.journal, self.binding)
                resume_claim = _claim(
                    self.binding,
                    self.plan,
                    restarted,
                    transition,
                    command=ProductionCommandV2.RESUME,
                )
                resumed = resume_managed_transition_v2(
                    journal=restarted, plan=self.plan, claim=resume_claim
                )
                self.assertIs(
                    resumed.status, ManagedProgressStatusV2.MANAGED_ACTION_PENDING
                )


def _managed_plan(binding, foundation):
    pairs = tuple((f"{index + 201:064x}", f"{index + 221:064x}") for index in range(8))
    return R2ManagedUnitPlanV2.create(
        binding=binding,
        foundation_plan=foundation,
        runtime_states=pairs[0:2],
        database_states=pairs[2:4],
        crx_states=pairs[4:6],
        config_states=pairs[6:8],
    )


def _complete_foundation(binding, plan):
    journal = R2TransactionJournalV2.create(
        binding=binding, genesis=_genesis(binding)
    )
    for transition in plan.transitions:
        head = journal.current_head_fingerprint
        claim = _claim(binding, plan, journal, transition)
        journal = begin_next_foundation_action_v2(
            journal=journal, plan=plan, claim=claim
        ).journal
        completion = complete_transaction_action_v2(
            binding,
            claim,
            head,
            transition.transition_instance_fingerprint,
            plan.remaining_plan_fingerprint(transition),
        )
        effect = R2FoundationEffectObservationV2.create(
            binding=binding,
            transition=transition,
            action_completion=completion,
            observed_state_fingerprint=transition.post_state_fingerprint,
            identity_fingerprint="a" * 64,
            byte_fingerprint="b" * 64,
        )
        journal = commit_foundation_effect_v2(
            journal=journal, plan=plan, effect=effect
        ).journal
    return _restart(journal, binding)


def _effect(binding, transition, completion):
    return R2ManagedUnitEffectObservationV2.create(
        binding=binding,
        transition=transition,
        action_completion=completion,
        observed_state_fingerprint=transition.post_state_fingerprint,
        identity_fingerprint="a" * 64,
        byte_fingerprint="b" * 64,
        acl_conformance_fingerprint="c" * 64,
        semantic_conformance_fingerprint="d" * 64,
        source_retained=True,
        partial_retained=True,
        failed_unit_retained=True,
        destructive_operations=0,
    )


def _commit_one(binding, plan, journal, transition):
    head = journal.current_head_fingerprint
    claim = _claim(binding, plan, journal, transition)
    pending = begin_next_managed_action_v2(journal=journal, plan=plan, claim=claim)
    completion = complete_transaction_action_v2(
        binding,
        claim,
        head,
        transition.transition_instance_fingerprint,
        plan.remaining_plan_fingerprint(transition),
    )
    return commit_managed_effect_v2(
        journal=pending.journal,
        plan=plan,
        effect=_effect(binding, transition, completion),
    ).journal


if __name__ == "__main__":
    unittest.main()
