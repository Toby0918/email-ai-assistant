"""Deep production-composition seam for the ten reviewed commands."""

import unittest

from backend.cutover_composition_contracts import (
    AuthorizationSequenceV1,
    CompositionBindingV1,
    CompositionStage,
    ProjectContainerReceiptChainV1,
)
from backend.migration_evidence_publication_composition import (
    MigrationEvidencePublicationRolesV1,
)
from backend.cutover_transaction_composition import (
    CutoverTransactionRolesV1,
    JournalOwnerV1,
)
from backend.cutover_composition_contracts.authorization_sequence import (
    AUTHORIZATION_PHASES,
    _create_test_authorization_sequence,
)
from backend.cutover_contracts import CutoverProfileV1, TestSandboxAuthorizationV1
from backend.r2_solo_maintainer_closure import FinalMasterBindingV1
from backend.r2_production_binding import (
    ProductionBindingError,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)
from backend.r2_production_binding._canonical import fingerprint
from backend.r2_production_composition import (
    EvidenceProductionAdapterV1,
    PreflightProductionAdapterV1,
    ProductionAdapterSlotV1,
    TransactionProductionAdapterV1,
    build_production_binding_candidate_v1,
    operator_subject_fingerprint_v1,
    production_adapter_catalog_v1,
)
from backend.real_host_preflight_composition import RealHostPreflightRolesV1
from tests.cutover_composition_binders import (
    TestOwnedCompositionScopeV1,
    bind_test_preflight,
    bind_test_publication,
    bind_test_transaction,
)
from tests.cutover_composition_fixtures import JOURNAL_OWNER, stage_receipt
from tests.cutover_contract_fixtures import valid_profile_body
from tests.r2_execution_confirmation_fixture import (
    appended_execution_claim,
    execution_candidate,
    execution_claim,
)


class R2ProductionCompositionV1Tests(unittest.TestCase):
    def test_catalog_has_exactly_three_adapter_slots_and_ten_commands(self):
        catalog = production_adapter_catalog_v1()
        expected_types = {
            ProductionAdapterSlotV1.PREFLIGHT: PreflightProductionAdapterV1,
            ProductionAdapterSlotV1.EVIDENCE: EvidenceProductionAdapterV1,
            ProductionAdapterSlotV1.TRANSACTION: TransactionProductionAdapterV1,
        }

        self.assertEqual(tuple(item.command for item in catalog), tuple(ProductionCommandV2))
        self.assertEqual({item.slot for item in catalog}, set(ProductionAdapterSlotV1))
        self.assertEqual(
            {slot: sum(item.slot is slot for item in catalog) for slot in ProductionAdapterSlotV1},
            {
                ProductionAdapterSlotV1.PREFLIGHT: 6,
                ProductionAdapterSlotV1.EVIDENCE: 1,
                ProductionAdapterSlotV1.TRANSACTION: 3,
            },
        )
        self.assertTrue(
            all(item.adapter_type is expected_types[item.slot] for item in catalog)
        )

    def test_preflight_adapter_returns_validated_composition_outcome(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        claim = _claim(
            binding,
            ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
        )
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )

        outcome = adapter.invoke(binding=binding, claim=claim)

        self.assertIs(
            outcome.command,
            ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
        )
        self.assertIs(outcome.stage, CompositionStage.CURRENT_TOPOLOGY)
        self.assertEqual(outcome.read_operations, 1)
        self.assertEqual(outcome.provider_attempts, 0)
        with self.assertRaises(ProductionBindingError):
            adapter.invoke(binding=binding, claim=claim)

    def test_confirmed_claim_without_journal_append_cannot_reach_adapter(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        candidate = execution_candidate(
            binding,
            command=ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
        )
        claim = execution_claim(binding, candidate=candidate)
        adapter = PreflightProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            evidence_publication_receipt=None,
            recovery_receipt=None,
        )

        with self.assertRaises(ProductionBindingError):
            adapter.invoke(binding=binding, claim=claim)

    def test_transaction_adapter_returns_validated_terminal_chain_outcome(self):
        binding, composition, _initial, scope = _transaction_context()
        self.addCleanup(scope.close)
        transition = "5" * 64
        plan = "0" * 64
        command = ProductionCommandV2.EXECUTE
        claim = _claim(
            binding,
            command,
            journal_owner=JOURNAL_OWNER,
        )
        adapter = TransactionProductionAdapterV1.create(
            binding=binding,
            composition=composition,
        )

        outcome = adapter.invoke(
            binding=binding,
            claim=claim,
            journal_head_fingerprint=claim.prior_journal_head_fingerprint,
            transition_instance_fingerprint=transition,
            remaining_reverse_plan_fingerprint=plan,
        )

        self.assertIs(outcome.command, command)
        self.assertEqual(outcome.mutations, 1)
        self.assertEqual(outcome.transition_instance_fingerprint, transition)
        self.assertEqual(outcome.remaining_reverse_plan_fingerprint, plan)
        self.assertNotEqual(outcome.chain_fingerprint, "")

    def test_failed_adapter_attempt_still_consumes_confirmation(self):
        binding, composition, _initial, scope = _transaction_context()
        self.addCleanup(scope.close)
        transition = "5" * 64
        plan = "0" * 64
        command = ProductionCommandV2.EXECUTE
        claim = _claim(
            binding,
            command,
            journal_owner=JOURNAL_OWNER,
        )
        adapter = TransactionProductionAdapterV1.create(
            binding=binding,
            composition=composition,
        )

        with self.assertRaises(ProductionBindingError):
            adapter.invoke(
                binding=binding,
                claim=claim,
                journal_head_fingerprint="f" * 64,
                transition_instance_fingerprint=transition,
                remaining_reverse_plan_fingerprint=plan,
            )
        with self.assertRaises(ProductionBindingError):
            adapter.invoke(
                binding=binding,
                claim=claim,
                journal_head_fingerprint=claim.prior_journal_head_fingerprint,
                transition_instance_fingerprint=transition,
                remaining_reverse_plan_fingerprint=plan,
            )

    def test_evidence_adapter_returns_validated_publication_outcome(self):
        binding, composition, review, scope = _evidence_context()
        self.addCleanup(scope.close)
        claim = _claim(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint=review.observation_fingerprint,
        )
        adapter = EvidenceProductionAdapterV1.create(
            binding=binding,
            composition=composition,
            review_receipt=review,
        )

        outcome = adapter.invoke(binding=binding, claim=claim)

        self.assertEqual(
            outcome.reviewed_evidence_fingerprint,
            review.observation_fingerprint,
        )
        self.assertEqual(outcome.manifest_fingerprint, review.receipt_fingerprint)
        self.assertEqual(outcome.created, 1)
        self.assertEqual(outcome.provider_attempts, 0)


if __name__ == "__main__":
    unittest.main()


_FINAL_COMMIT = "4dd5183c7cb2731f519b0516516d9c0eb4490804"
_OBSERVED_AT = 1_900_000_000


def _preflight_context():
    final_master = FinalMasterBindingV1.create(
        final_commit_oid=_FINAL_COMMIT,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )
    binding = build_production_binding_candidate_v1(
        final_master_binding=final_master,
    )
    profile_body = valid_profile_body()
    profile_body["governing_master_commit"] = _FINAL_COMMIT
    profile_body["operator_fingerprint"] = operator_subject_fingerprint_v1(
        final_master
    )
    profile = CutoverProfileV1.create(profile_body)
    authorizations = tuple(
        TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=binding.operation_fingerprint,
            phase=phase,
            expires_at_epoch=_OBSERVED_AT + 300,
        )
        for _kind, _operation, phase in AUTHORIZATION_PHASES
    )
    sequence: AuthorizationSequenceV1 = _create_test_authorization_sequence(
        profile=profile,
        operation_fingerprint=binding.operation_fingerprint,
        authorizations=authorizations,
        observed_at_epoch=_OBSERVED_AT,
    )
    composition_binding = CompositionBindingV1.create(
        profile=profile,
        operation_fingerprint=binding.operation_fingerprint,
        authorization_sequence=sequence,
    )

    def role(stage, index):
        return lambda prior: stage_receipt(
            composition_binding,
            stage,
            prior,
            index,
        )

    roles = RealHostPreflightRolesV1(
        binding_fingerprint=composition_binding.binding_fingerprint,
        current_topology=role(CompositionStage.CURRENT_TOPOLOGY, 1),
        host_baseline=role(CompositionStage.HOST_BASELINE, 2),
        evidence_review=role(CompositionStage.EVIDENCE_REVIEW, 3),
        evidence_verification=role(CompositionStage.EVIDENCE_VERIFICATION, 5),
        final_audit_readiness=role(CompositionStage.FINAL_AUDIT_READINESS, 6),
        recovery_inspection=role(CompositionStage.RECOVERY_INSPECTION, 18),
    )
    scope = TestOwnedCompositionScopeV1.create()
    composition = bind_test_preflight(
        scope=scope,
        binding=composition_binding,
        authorization_sequence=sequence,
        roles=roles,
        observed_at_epoch=_OBSERVED_AT,
    )
    return binding, composition, scope


def _claim(
    binding,
    command,
    *,
    subject_fingerprint=None,
    journal_owner="3" * 64,
):
    action_factory = None
    if command in {
        ProductionCommandV2.EXECUTE,
        ProductionCommandV2.RESUME,
        ProductionCommandV2.ROLLBACK,
    }:
        action_factory = lambda head: _transaction_action_fingerprint(
            binding,
            command,
            journal_head_fingerprint=head,
            transition_instance_fingerprint="5" * 64,
            remaining_reverse_plan_fingerprint="0" * 64,
        )
    return appended_execution_claim(
        binding,
        command=command,
        subject_fingerprint=subject_fingerprint,
        action_factory=action_factory,
        journal_owner=journal_owner,
    )


def _evidence_context():
    final_master = FinalMasterBindingV1.create(
        final_commit_oid=_FINAL_COMMIT,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )
    binding = build_production_binding_candidate_v1(
        final_master_binding=final_master,
    )
    profile_body = valid_profile_body()
    profile_body["governing_master_commit"] = _FINAL_COMMIT
    profile_body["operator_fingerprint"] = operator_subject_fingerprint_v1(
        final_master
    )
    profile = CutoverProfileV1.create(profile_body)
    authorizations = tuple(
        TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=binding.operation_fingerprint,
            phase=phase,
            expires_at_epoch=_OBSERVED_AT + 300,
        )
        for _kind, _operation, phase in AUTHORIZATION_PHASES
    )
    sequence = _create_test_authorization_sequence(
        profile=profile,
        operation_fingerprint=binding.operation_fingerprint,
        authorizations=authorizations,
        observed_at_epoch=_OBSERVED_AT,
    )
    composition_binding = CompositionBindingV1.create(
        profile=profile,
        operation_fingerprint=binding.operation_fingerprint,
        authorization_sequence=sequence,
    )
    review = stage_receipt(
        composition_binding,
        CompositionStage.EVIDENCE_REVIEW,
        None,
        3,
    )

    def publish(prior):
        return stage_receipt(
            composition_binding,
            CompositionStage.EVIDENCE_PUBLICATION,
            prior,
            4,
        )

    scope = TestOwnedCompositionScopeV1.create()
    composition = bind_test_publication(
        scope=scope,
        binding=composition_binding,
        authorization_sequence=sequence,
        roles=MigrationEvidencePublicationRolesV1(
            binding_fingerprint=composition_binding.binding_fingerprint,
            publish_confirmed_review=publish,
        ),
        confirmed_review_fingerprint=review.observation_fingerprint,
        observed_at_epoch=_OBSERVED_AT,
    )
    return binding, composition, review, scope


_PREFLIGHT_STAGES = (
    CompositionStage.CURRENT_TOPOLOGY,
    CompositionStage.HOST_BASELINE,
    CompositionStage.EVIDENCE_REVIEW,
    CompositionStage.EVIDENCE_PUBLICATION,
    CompositionStage.EVIDENCE_VERIFICATION,
    CompositionStage.FINAL_AUDIT_READINESS,
)
_EXECUTION_STAGES = (
    CompositionStage.ACL_BASELINE,
    CompositionStage.PRE_MUTATION_GATE,
    CompositionStage.ACL_PUBLICATION,
    CompositionStage.REPOSITORY_TRANSACTION,
    CompositionStage.RUNTIME_PUBLICATION,
    CompositionStage.DATABASE_PUBLICATION,
    CompositionStage.ARTIFACT_PUBLICATION,
    CompositionStage.CONFIG_PUBLICATION,
    CompositionStage.ACTIVATION,
    CompositionStage.FINAL_AUDIT,
)


def _transaction_context():
    binding, composition_binding, sequence = _candidate_composition_binding()
    initial = _chain(composition_binding, _PREFLIGHT_STAGES)

    def role(stage, index, *, valid_until_epoch=0):
        return lambda prior: stage_receipt(
            composition_binding,
            stage,
            prior,
            index,
            journal_bound=stage
            not in {CompositionStage.ACL_BASELINE, CompositionStage.PRE_MUTATION_GATE},
            valid_until_epoch=valid_until_epoch,
        )

    by_stage = {
        stage: role(
            stage,
            10 + index,
            valid_until_epoch=(
                _OBSERVED_AT + 60
                if stage is CompositionStage.PRE_MUTATION_GATE
                else 0
            ),
        )
        for index, stage in enumerate(_EXECUTION_STAGES)
    }
    blocked = lambda _value: (_ for _ in ()).throw(ValueError())
    roles = CutoverTransactionRolesV1(
        binding_fingerprint=composition_binding.binding_fingerprint,
        acl_baseline=by_stage[CompositionStage.ACL_BASELINE],
        pre_mutation_gate=by_stage[CompositionStage.PRE_MUTATION_GATE],
        acl_publication=by_stage[CompositionStage.ACL_PUBLICATION],
        repository_transaction=by_stage[CompositionStage.REPOSITORY_TRANSACTION],
        runtime_publication=by_stage[CompositionStage.RUNTIME_PUBLICATION],
        database_publication=by_stage[CompositionStage.DATABASE_PUBLICATION],
        artifact_publication=by_stage[CompositionStage.ARTIFACT_PUBLICATION],
        config_publication=by_stage[CompositionStage.CONFIG_PUBLICATION],
        activation=by_stage[CompositionStage.ACTIVATION],
        final_audit=by_stage[CompositionStage.FINAL_AUDIT],
        cutover_success=role(CompositionStage.CUTOVER_SUCCESS, 20),
        recovery_inspection=blocked,
        failed_container_preservation=blocked,
        rollback_restoration=blocked,
        legacy_health=blocked,
        resume_committed=blocked,
    )
    owner = JournalOwnerV1(
        owner_fingerprint=JOURNAL_OWNER,
        verify_head=lambda receipt: receipt.journal_head_fingerprint,
        claim_gate=lambda receipt: receipt.receipt_fingerprint,
        now_epoch=lambda: _OBSERVED_AT,
    )
    scope = TestOwnedCompositionScopeV1.create()
    composition = bind_test_transaction(
        scope=scope,
        binding=composition_binding,
        authorization_sequence=sequence,
        roles=roles,
        journal_owner=owner,
        initial_chain=initial,
        observed_at_epoch=_OBSERVED_AT,
    )
    return binding, composition, initial, scope


def _candidate_composition_binding():
    final_master = FinalMasterBindingV1.create(
        final_commit_oid=_FINAL_COMMIT,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )
    binding = build_production_binding_candidate_v1(
        final_master_binding=final_master,
    )
    body = valid_profile_body()
    body["governing_master_commit"] = _FINAL_COMMIT
    body["operator_fingerprint"] = operator_subject_fingerprint_v1(final_master)
    profile = CutoverProfileV1.create(body)
    authorizations = tuple(
        TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=binding.operation_fingerprint,
            phase=phase,
            expires_at_epoch=_OBSERVED_AT + 300,
        )
        for _kind, _operation, phase in AUTHORIZATION_PHASES
    )
    sequence = _create_test_authorization_sequence(
        profile=profile,
        operation_fingerprint=binding.operation_fingerprint,
        authorizations=authorizations,
        observed_at_epoch=_OBSERVED_AT,
    )
    composition_binding = CompositionBindingV1.create(
        profile=profile,
        operation_fingerprint=binding.operation_fingerprint,
        authorization_sequence=sequence,
    )
    return binding, composition_binding, sequence


def _chain(binding, stages):
    receipts = []
    prior = None
    for index, stage in enumerate(stages):
        receipt = stage_receipt(binding, stage, prior, index)
        receipts.append(receipt)
        prior = receipt
    return ProjectContainerReceiptChainV1.create(
        receipts=tuple(receipts),
        observed_at_epoch=_OBSERVED_AT,
    )


def _transaction_action_fingerprint(
    binding,
    command,
    *,
    journal_head_fingerprint,
    transition_instance_fingerprint,
    remaining_reverse_plan_fingerprint,
):
    subject = fingerprint(
        "r2-transaction-action-subject-v2",
        {
            "journal_head_fingerprint": journal_head_fingerprint,
            "transition_instance_fingerprint": transition_instance_fingerprint,
            "remaining_reverse_plan_fingerprint": (
                remaining_reverse_plan_fingerprint
            ),
        },
    )
    return production_action_fingerprint_v2(
        binding,
        command,
        subject_fingerprint=subject,
    )
