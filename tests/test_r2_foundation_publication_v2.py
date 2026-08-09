"""Single-action foundation publication and recovery for Issue #94."""

from __future__ import annotations

import unittest

from backend.r2_foundation_publication_v2 import (
    FoundationBoundaryV2,
    FoundationProgressStatusV2,
    R2FoundationEffectObservationV2,
    R2FoundationPlanV2,
    begin_next_foundation_action_v2,
    classify_foundation_pending_v2,
    commit_foundation_effect_v2,
    resume_foundation_transition_v2,
)
from backend.r2_production_binding import (
    ProductionCommandV2,
    ProductionRoleV2,
)
from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    R2StateObservationV2,
    R2TransactionJournalV2,
    inspect_pending_transition_v2,
)
from backend.r2_transaction_process.production_v2 import (
    complete_transaction_action_v2,
    transaction_action_fingerprint_v2,
)
from tests.test_r2_transaction_journal_v2 import (
    NOW,
    _binding,
    _confirmed_claim,
    _genesis,
    _live_append_observation,
)


class R2FoundationPublicationV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.plan = _plan(self.binding)
        self.journal = R2TransactionJournalV2.create(
            binding=self.binding, genesis=_genesis(self.binding),
            **_live_append_observation(),
        )

    def test_exact_plan_has_unique_owners_and_eleven_worktrees(self):
        restarted = R2FoundationPlanV2.from_json(
            self.plan.to_canonical_json(), binding=self.binding
        )
        self.assertEqual(restarted, self.plan)
        self.assertEqual(len(restarted.transitions), 17)
        self.assertEqual(
            sum(
                item.boundary is FoundationBoundaryV2.WORKTREE_RECONSTRUCTION
                for item in restarted.transitions
            ),
            11,
        )
        self.assertEqual(
            tuple(item.owner for item in restarted.transitions[:6]),
            (
                ProductionRoleV2.LEGACY_SERVICE,
                ProductionRoleV2.LEGACY_SOURCE_ANCHOR,
                ProductionRoleV2.PROJECT_CONTAINER,
                ProductionRoleV2.MANAGED_MAIN,
                ProductionRoleV2.MANAGED_MAIN,
                ProductionRoleV2.REPOSITORY_ROOT,
            ),
        )
        self.assertEqual(
            len({item.transition_instance_fingerprint for item in restarted.transitions}),
            17,
        )

    def test_every_foundation_action_uses_fresh_confirmation_and_one_effect(self):
        journal = self.journal
        for transition in self.plan.transitions:
            prior_head = journal.current_head_fingerprint
            claim = _claim(self.binding, self.plan, journal, transition)
            pending = begin_next_foundation_action_v2(
                journal=journal, plan=self.plan, claim=claim,
                **_live_append_observation(),
            )
            self.assertIs(
                pending.status, FoundationProgressStatusV2.FOUNDATION_ACTION_PENDING
            )
            self.assertEqual((pending.host_mutations, pending.journal_appends), (0, 2))
            journal = _restart(pending.journal, self.binding)
            completion = complete_transaction_action_v2(
                self.binding,
                claim,
                prior_head,
                transition.transition_instance_fingerprint,
                self.plan.remaining_plan_fingerprint(transition),
            )
            effect = R2FoundationEffectObservationV2.create(
                binding=self.binding,
                transition=transition,
                action_completion=completion,
                observed_state_fingerprint=transition.post_state_fingerprint,
                identity_fingerprint="a" * 64,
                byte_fingerprint="b" * 64,
            )
            committed = commit_foundation_effect_v2(
                journal=journal, plan=self.plan, effect=effect
            )
            self.assertEqual((committed.host_mutations, committed.journal_appends), (1, 2))
            journal = _restart(committed.journal, self.binding)
        self.assertIs(
            committed.status, FoundationProgressStatusV2.FOUNDATION_COMPLETE
        )
        self.assertEqual(self.plan.committed_prefix_count(journal), 17)

    def test_pre_state_requires_fresh_confirmation_before_same_effect(self):
        transition, pending, _claim_value = self._pending()
        receipt = _inspection(pending.journal, transition.pre_state_fingerprint, pre=True)
        classified = classify_foundation_pending_v2(
            journal=pending.journal, plan=self.plan, inspection=receipt
        )
        self.assertEqual((classified.host_mutations, classified.journal_appends), (0, 1))
        self.assertIs(
            classified.classification, EffectClassificationV2.EFFECT_ABSENT_EXACT
        )
        restarted = _restart(classified.journal, self.binding)
        resume_claim = _claim(
            self.binding,
            self.plan,
            restarted,
            transition,
            command=ProductionCommandV2.RESUME,
        )
        resumed = resume_foundation_transition_v2(
            journal=restarted, plan=self.plan, claim=resume_claim,
            **_live_append_observation(),
        )
        self.assertIs(
            resumed.status, FoundationProgressStatusV2.FOUNDATION_ACTION_PENDING
        )
        self.assertEqual((resumed.host_mutations, resumed.journal_appends), (0, 2))

    def test_post_state_recovers_commit_without_replaying_effect(self):
        transition, pending, _claim_value = self._pending()
        receipt = _inspection(pending.journal, transition.post_state_fingerprint, post=True)
        classified = classify_foundation_pending_v2(
            journal=pending.journal, plan=self.plan, inspection=receipt
        )
        restarted = _restart(classified.journal, self.binding)
        resume_claim = _claim(
            self.binding,
            self.plan,
            restarted,
            transition,
            command=ProductionCommandV2.RESUME,
        )
        recovered = resume_foundation_transition_v2(
            journal=restarted, plan=self.plan, claim=resume_claim,
            **_live_append_observation(),
        )
        self.assertIs(
            recovered.status, FoundationProgressStatusV2.FOUNDATION_RECOVERED_COMMIT
        )
        self.assertEqual((recovered.host_mutations, recovered.journal_appends), (0, 2))
        self.assertEqual(self.plan.committed_prefix_count(recovered.journal), 1)

    def test_ambiguous_or_wrong_next_action_incident_stops(self):
        transition, pending, _claim_value = self._pending()
        receipt = _inspection(pending.journal, "d" * 64)
        classified = classify_foundation_pending_v2(
            journal=pending.journal, plan=self.plan, inspection=receipt
        )
        self.assertIs(classified.status, FoundationProgressStatusV2.INCIDENT_STOP)
        self.assertEqual((classified.host_mutations, classified.journal_appends), (0, 1))
        with self.assertRaisesRegex(ValueError, "R2_FOUNDATION_PUBLICATION_INVALID"):
            begin_next_foundation_action_v2(
                journal=self.journal,
                plan=self.plan,
                claim=_claim(
                    self.binding,
                    self.plan,
                    self.journal,
                    self.plan.transitions[1],
                ),
                **_live_append_observation(),
            )

    def _pending(self):
        transition = self.plan.transitions[0]
        claim = _claim(self.binding, self.plan, self.journal, transition)
        return transition, begin_next_foundation_action_v2(
            journal=self.journal, plan=self.plan, claim=claim,
            **_live_append_observation(),
        ), claim


def _plan(binding):
    pairs = tuple((f"{index + 1:064x}", f"{index + 101:064x}") for index in range(17))
    return R2FoundationPlanV2.create(
        binding=binding,
        quiescence_states=pairs[0],
        legacy_anchor_states=pairs[1],
        container_states=pairs[2],
        main_states=pairs[3],
        whole_tree_acl_states=pairs[4],
        repository_states=pairs[5],
        worktree_states=pairs[6:],
    )


def _claim(binding, plan, journal, transition, *, command=ProductionCommandV2.EXECUTE):
    action = transaction_action_fingerprint_v2(
        binding,
        command,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=transition.transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint=plan.remaining_plan_fingerprint(transition),
    )
    sequence = len(journal.execution_confirmation_claims) + 1
    return _confirmed_claim(
        binding=binding,
        command=command,
        action_fingerprint=action,
        head=journal.current_head_fingerprint,
        transition=transition.transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint=plan.remaining_plan_fingerprint(transition),
        claim_sequence=sequence,
        confirmed_at_epoch=NOW,
    )


def _inspection(journal, state, *, pre=False, post=False):
    observation = R2StateObservationV2.create(
        binding_fingerprint=journal.binding_fingerprint,
        journal_head_fingerprint=journal.current_head_fingerprint,
        transition_instance_fingerprint=journal.records[-1].transition_instance_fingerprint,
        observed_state_fingerprint=state,
        identity_fingerprint="e" * 64,
        byte_fingerprint="f" * 64,
        pre_state_match=pre,
        post_state_match=post,
    )
    return inspect_pending_transition_v2(
        journal=journal,
        first_observation=observation,
        second_observation=R2StateObservationV2.from_json(
            observation.to_canonical_json()
        ),
    )


def _restart(journal, binding):
    return R2TransactionJournalV2.from_framed_bytes(
        journal.to_framed_bytes(), binding=binding
    )


if __name__ == "__main__":
    unittest.main()
