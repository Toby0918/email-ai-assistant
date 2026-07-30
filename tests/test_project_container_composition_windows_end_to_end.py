"""Complete Issue #59 composition in test-owned Windows sandboxes only."""

from __future__ import annotations

import sys
import unittest

from backend.cutover_composition_contracts import (
    CompositionContractError,
    CompositionStage,
    ReceiptChainState,
)
from backend.cutover_transaction_composition import (
    CutoverTransactionRolesV1,
    JournalOwnerV1,
)
from backend.migration_evidence_publication_composition import (
    MigrationEvidencePublicationRolesV1,
)
from backend.real_host_preflight_composition import (
    RealHostPreflightRolesV1,
)
from tests.cutover_composition_binders import (
    TestOwnedCompositionScopeV1,
    bind_test_preflight,
    bind_test_publication,
    bind_test_transaction,
)
from tests.cutover_composition_fixtures import (
    JOURNAL_OWNER,
    OBSERVED_AT,
    synthetic_context,
)
from tests.project_container_composition_windows_fixtures import (
    WindowsCompositionFixture,
)


@unittest.skipUnless(
    sys.platform == "win32",
    "Windows sandbox evidence only; no Linux NTFS or ACL claim",
)
class ProjectContainerCompositionWindowsEndToEndTests(unittest.TestCase):
    def test_full_failed_cutover_recovers_legacy_through_three_roots(
        self,
    ) -> None:
        _profile, sequence, binding = synthetic_context()
        scope = TestOwnedCompositionScopeV1.create()
        self.addCleanup(scope.close)
        fixture = WindowsCompositionFixture(binding, scope)
        self.addCleanup(fixture.close)
        preflight = bind_test_preflight(
            scope=scope,
            binding=binding,
            authorization_sequence=sequence,
            roles=_preflight_roles(binding, fixture),
            observed_at_epoch=OBSERVED_AT,
        )

        preflight.run_current_topology()
        preflight.collect_host_baseline()
        review = preflight.review_evidence()
        publication = bind_test_publication(
            scope=scope,
            binding=binding,
            authorization_sequence=sequence,
            roles=MigrationEvidencePublicationRolesV1(
                binding_fingerprint=binding.binding_fingerprint,
                publish_confirmed_review=fixture.evidence_publication,
            ),
            confirmed_review_fingerprint=review.observation_fingerprint,
            observed_at_epoch=OBSERVED_AT,
        ).publish(review)
        preflight.verify_evidence(publication)
        preflight.prove_final_audit_readiness()
        ready = preflight.receipt_chain()

        owner = _journal_owner()
        forward = bind_test_transaction(
            scope=scope,
            binding=binding,
            authorization_sequence=sequence,
            roles=_transaction_roles(binding, fixture),
            journal_owner=owner,
            initial_chain=ready,
            observed_at_epoch=OBSERVED_AT,
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^CUTOVER_TRANSACTION_COMPOSITION_REJECTED$",
        ):
            forward.execute()

        failed_activation = fixture.failed_activation_chain(ready)
        transaction = bind_test_transaction(
            scope=scope,
            binding=binding,
            authorization_sequence=sequence,
            roles=_transaction_roles(binding, fixture),
            journal_owner=owner,
            initial_chain=failed_activation,
            observed_at_epoch=OBSERVED_AT,
        )
        recovered = transaction.rollback()

        self.assertIs(ready.state, ReceiptChainState.PREFLIGHT_READY)
        self.assertIs(
            failed_activation.state,
            ReceiptChainState.IN_PROGRESS,
        )
        self.assertIs(recovered.state, ReceiptChainState.LEGACY_RECOVERED)
        self.assertEqual(recovered.operation_fingerprint, binding.operation_fingerprint)
        self.assertEqual(recovered.profile_fingerprint, binding.profile_fingerprint)
        self.assertEqual(
            recovered.governing_master_fingerprint,
            binding.governing_master_fingerprint,
        )
        self.assertEqual(
            recovered.authorization_sequence_fingerprint,
            sequence.sequence_fingerprint,
        )
        self.assertEqual(recovered.journal_owner_fingerprint, JOURNAL_OWNER)
        self.assertEqual(recovered.receipts[-2].worktrees, 11)
        self.assertEqual(recovered.receipts[-1].worktrees, 11)
        self.assertEqual(
            sum(item.provider_attempts for item in recovered.receipts),
            0,
        )
        self.assertTrue(fixture.evidence.target.is_file())
        self.assertTrue(fixture.managed.runtime_target.is_dir())
        self.assertTrue(fixture.managed.database_target.is_file())
        self.assertTrue(fixture.managed.crx_target.is_file())
        self.assertTrue(fixture.managed.config_target.is_file())
        self.assertEqual(
            fixture.consumed_publication_fingerprint,
            fixture.receipt_set.receipt_set_fingerprint,
        )
        self.assertEqual(
            fixture.service.new_start.data_role_fingerprint,
            fixture.receipt_set.receipts[1].receipt_fingerprint,
        )
        self.assertEqual(
            fixture.repository_profile.to_mapping()["acl_policy"][
                "policy_fingerprint"
            ],
            fixture.acl_applied.policy_fingerprint,
        )


def _preflight_roles(binding, fixture):
    return RealHostPreflightRolesV1(
        binding_fingerprint=binding.binding_fingerprint,
        current_topology=fixture.current_topology,
        host_baseline=fixture.host_baseline,
        evidence_review=fixture.evidence_review,
        evidence_verification=fixture.evidence_verification,
        final_audit_readiness=fixture.final_audit_readiness,
        recovery_inspection=fixture.recovery_inspection,
    )


def _transaction_roles(binding, fixture):
    def unused(_prior):
        raise RuntimeError("unused synthetic role")

    return CutoverTransactionRolesV1(
        binding_fingerprint=binding.binding_fingerprint,
        acl_baseline=fixture.acl_baseline,
        pre_mutation_gate=fixture.pre_mutation_gate,
        acl_publication=fixture.acl_publication,
        repository_transaction=fixture.repository_transaction,
        runtime_publication=fixture.runtime_publication,
        database_publication=fixture.database_publication,
        artifact_publication=fixture.artifact_publication,
        config_publication=fixture.config_publication,
        activation=fixture.activation,
        final_audit=fixture.final_audit,
        cutover_success=fixture.cutover_success,
        recovery_inspection=fixture.recovery_inspection,
        failed_container_preservation=fixture.failed_container_preservation,
        rollback_restoration=fixture.rollback_restoration,
        legacy_health=fixture.legacy_health,
        resume_committed=unused,
    )


def _journal_owner():
    claimed = set()

    def claim_gate(receipt):
        fingerprint = receipt.receipt_fingerprint
        if fingerprint in claimed:
            raise ValueError
        claimed.add(fingerprint)
        return fingerprint

    return JournalOwnerV1(
        owner_fingerprint=JOURNAL_OWNER,
        verify_head=lambda receipt: receipt.journal_head_fingerprint,
        claim_gate=claim_gate,
        now_epoch=lambda: OBSERVED_AT,
    )


if __name__ == "__main__":
    unittest.main()
