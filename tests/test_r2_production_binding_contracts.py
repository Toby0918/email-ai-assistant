"""Reviewed final-master binding V2 and durable authority claim contracts."""

from __future__ import annotations

import unittest

from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    AuthorityClaimError,
    AuthorityDomainV2,
    DurableAuthorityClaimV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    ProductionBindingError,
    PublicKeyRoleV2,
    authority_domain_for_command_v2,
    validate_new_authority_claim,
)
from backend.r2_final_master_closure import FinalMasterBindingV1


class R2ProductionBindingContractTests(unittest.TestCase):
    def test_command_domain_and_role_vocabularies_are_exact_and_closed(self):
        expected_domains = {
            ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT: AuthorityDomainV2.PREFLIGHT,
            ProductionCommandV2.HOST_BASELINE: AuthorityDomainV2.PREFLIGHT,
            ProductionCommandV2.EVIDENCE_REVIEW: AuthorityDomainV2.PREFLIGHT,
            ProductionCommandV2.EVIDENCE_VERIFICATION: AuthorityDomainV2.PREFLIGHT,
            ProductionCommandV2.FINAL_AUDIT_READINESS: AuthorityDomainV2.PREFLIGHT,
            ProductionCommandV2.RECOVERY_INSPECTION: AuthorityDomainV2.PREFLIGHT,
            ProductionCommandV2.EVIDENCE_PUBLICATION: AuthorityDomainV2.EVIDENCE,
            ProductionCommandV2.EXECUTE: AuthorityDomainV2.EXECUTION,
            ProductionCommandV2.RESUME: AuthorityDomainV2.EXECUTION,
            ProductionCommandV2.ROLLBACK: AuthorityDomainV2.RECOVERY,
        }

        self.assertEqual(
            {command: authority_domain_for_command_v2(command) for command in ProductionCommandV2},
            expected_domains,
        )
        self.assertEqual(
            tuple(OperatorRoleV2),
            (
                OperatorRoleV2.PREFLIGHT_OPERATOR,
                OperatorRoleV2.EVIDENCE_OPERATOR,
                OperatorRoleV2.EXECUTION_OPERATOR,
                OperatorRoleV2.RECOVERY_OPERATOR,
            ),
        )
        self.assertEqual(
            tuple(PublicKeyRoleV2),
            (
                PublicKeyRoleV2.PREFLIGHT_VERIFICATION,
                PublicKeyRoleV2.EVIDENCE_VERIFICATION,
                PublicKeyRoleV2.EXECUTION_VERIFICATION,
                PublicKeyRoleV2.RECOVERY_VERIFICATION,
            ),
        )
        self.assertEqual(
            tuple(ProductionRoleV2),
            (
                ProductionRoleV2.LEGACY_SOURCE_ANCHOR,
                ProductionRoleV2.PROJECT_CONTAINER,
                ProductionRoleV2.MANAGED_MAIN,
                ProductionRoleV2.REPOSITORY_ROOT,
                ProductionRoleV2.GIT_COMMON_STATE,
                ProductionRoleV2.WORKTREE_TOPOLOGY,
                ProductionRoleV2.RUNTIME,
                ProductionRoleV2.DATABASE,
                ProductionRoleV2.CRX,
                ProductionRoleV2.CONFIG,
                ProductionRoleV2.TRANSACTION_JOURNAL,
                ProductionRoleV2.EVIDENCE_PACKAGE,
                ProductionRoleV2.FAILED_CONTAINER,
                ProductionRoleV2.LEGACY_SERVICE,
                ProductionRoleV2.MANAGED_SERVICE,
                ProductionRoleV2.STOPPED_LAYOUT_AUDIT,
                ProductionRoleV2.FINAL_RUNNING_AUDIT,
                ProductionRoleV2.RETENTION_LEDGER,
            ),
        )
        self.assertIsNone(authority_domain_for_command_v2("execute"))

    def test_reviewed_binding_v2_binds_final_master_roles_keys_and_freshness(self):
        final_master = _final_master_binding()
        binding = _approved_binding(final_master)

        self.assertEqual(
            binding.final_master_binding_fingerprint,
            final_master.binding_fingerprint,
        )
        self.assertEqual(binding.operation, "r2_project_container_cutover")
        self.assertEqual(binding.authority_domain_count, 4)
        self.assertEqual(binding.preflight_verb_count, 6)
        self.assertEqual(binding.process_root_count, 3)
        self.assertEqual(binding.local_ref_count, 14)
        self.assertEqual(binding.worktree_count, 11)
        self.assertEqual(binding.managed_unit_count, 4)
        self.assertEqual(binding.max_authority_validity_seconds, 300)
        self.assertEqual(
            ApprovedCutoverBindingV2.from_json(
                binding.to_canonical_json(),
                final_master_binding=final_master,
            ),
            binding,
        )
        self.assertNotIn("private", repr(binding).lower())
        self.assertNotIn("path", repr(binding).lower())

    def test_durable_claim_reconstruction_preserves_single_use_across_processes(self):
        binding = _approved_binding(_final_master_binding())
        first = _claim(
            binding,
            sequence=1,
            authority_fingerprint="1" * 64,
            envelope_nonce="2" * 64,
            prior_head="3" * 64,
        )
        validate_new_authority_claim(
            binding=binding,
            candidate=first,
            durable_claims=(),
            observed_at_epoch=102,
            expected_prior_journal_head_fingerprint="3" * 64,
        )
        reconstructed = DurableAuthorityClaimV2.from_json(
            first.to_canonical_json(),
            binding=binding,
        )
        second = _claim(
            binding,
            sequence=2,
            authority_fingerprint="4" * 64,
            envelope_nonce="5" * 64,
            prior_head="6" * 64,
        )

        self.assertIs(
            validate_new_authority_claim(
                binding=binding,
                candidate=second,
                durable_claims=(reconstructed,),
                observed_at_epoch=102,
                expected_prior_journal_head_fingerprint="6" * 64,
            ),
            second,
        )
        self.assertIs(second.domain, AuthorityDomainV2.EXECUTION)
        self.assertEqual(second.single_use, 1)

    def test_binding_and_claim_fail_closed_on_omission_replay_or_staleness(self):
        final_master = _final_master_binding()
        with self.assertRaisesRegex(
            ProductionBindingError,
            "R2_PRODUCTION_BINDING_INVALID",
        ):
            ApprovedCutoverBindingV2.create(
                final_master_binding=final_master,
                operation_fingerprint="f" * 64,
                operator_role_fingerprints={
                    role: f"{index + 10:064x}"
                    for index, role in enumerate(OperatorRoleV2)
                    if role is not OperatorRoleV2.RECOVERY_OPERATOR
                },
                verification_public_keys={
                    role: bytes([index + 1]) * 32
                    for index, role in enumerate(PublicKeyRoleV2)
                },
                production_role_fingerprints={
                    role: f"{index + 30:064x}"
                    for index, role in enumerate(ProductionRoleV2)
                },
            )

        binding = _approved_binding(final_master)
        first = _claim(
            binding,
            sequence=1,
            authority_fingerprint="1" * 64,
            envelope_nonce="2" * 64,
            prior_head="3" * 64,
        )
        replay = _claim(
            binding,
            sequence=2,
            authority_fingerprint="1" * 64,
            envelope_nonce="4" * 64,
            prior_head="5" * 64,
        )
        for observed, head in ((103, "5" * 64), (102, "6" * 64)):
            with self.subTest(observed=observed, head=head):
                with self.assertRaisesRegex(
                    AuthorityClaimError,
                    "R2_AUTHORITY_CLAIM_INVALID",
                ):
                    validate_new_authority_claim(
                        binding=binding,
                        candidate=replay,
                        durable_claims=(first,),
                        observed_at_epoch=observed,
                        expected_prior_journal_head_fingerprint=head,
                    )
        with self.assertRaisesRegex(
            AuthorityClaimError,
            "R2_AUTHORITY_CLAIM_INVALID",
        ):
            DurableAuthorityClaimV2.create(
                binding=binding,
                command=ProductionCommandV2.EXECUTE,
                action_fingerprint="7" * 64,
                authority_fingerprint="8" * 64,
                envelope_nonce="9" * 64,
                journal_owner_fingerprint="a" * 64,
                prior_journal_head_fingerprint="b" * 64,
                claim_sequence=1,
                issued_at_epoch=100,
                not_before_epoch=101,
                expires_at_epoch=102,
                claimed_at_epoch=102,
            )


def _approved_binding(final_master: FinalMasterBindingV1) -> ApprovedCutoverBindingV2:
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final_master,
        operation_fingerprint="f" * 64,
        operator_role_fingerprints={
            role: f"{index + 10:064x}"
            for index, role in enumerate(OperatorRoleV2)
        },
        verification_public_keys={
            role: bytes([index + 1]) * 32
            for index, role in enumerate(PublicKeyRoleV2)
        },
        production_role_fingerprints={
            role: f"{index + 30:064x}"
            for index, role in enumerate(ProductionRoleV2)
        },
    )


def _claim(
    binding: ApprovedCutoverBindingV2,
    *,
    sequence: int,
    authority_fingerprint: str,
    envelope_nonce: str,
    prior_head: str,
) -> DurableAuthorityClaimV2:
    return DurableAuthorityClaimV2.create(
        binding=binding,
        command=ProductionCommandV2.EXECUTE,
        action_fingerprint=f"{sequence + 50:064x}",
        authority_fingerprint=authority_fingerprint,
        envelope_nonce=envelope_nonce,
        journal_owner_fingerprint="7" * 64,
        prior_journal_head_fingerprint=prior_head,
        claim_sequence=sequence,
        issued_at_epoch=100,
        not_before_epoch=101,
        expires_at_epoch=200,
        claimed_at_epoch=102,
    )


def _final_master_binding() -> FinalMasterBindingV1:
    return FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


if __name__ == "__main__":
    unittest.main()
