"""ApprovedCutoverBindingV3 closed production-binding contracts."""

from __future__ import annotations

import json
import unittest

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionBindingError,
    ProductionCommandV2,
    ProductionRoleV2,
    authority_domain_for_command_v2,
    production_action_fingerprint_v2,
    require_reviewed_production_binding_v3,
)
from tests.r2_execution_confirmation_fixture import (
    final_master_binding,
    production_binding,
)


_BINDING_FIELDS = {
    "binding_type",
    "final_master_binding_fingerprint",
    "final_commit_oid",
    "final_tree_oid",
    "closure_map_fingerprint",
    "source_package_fingerprint",
    "runbook_fingerprint",
    "workflow_fingerprint",
    "operation_fingerprint",
    "operator_role_registry_fingerprint",
    "command_domain_registry_fingerprint",
    "production_role_registry_fingerprint",
    "execution_confirmation_policy",
    "execution_confirmation_policy_fingerprint",
    "operator_role_count",
    "command_count",
    "command_domain_count",
    "production_role_count",
    "max_execution_confirmation_validity_seconds",
    "operator_role_fingerprints",
    "command_domains",
    "production_role_fingerprints",
    "assurance_model",
    "operator_count",
    "independent_reviewer_count",
    "external_signer_count",
    "issue39_authority_count",
    "binding_fingerprint",
}


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
            {
                command: authority_domain_for_command_v2(command)
                for command in ProductionCommandV2
            },
            expected_domains,
        )
        self.assertEqual(len(tuple(OperatorRoleV2)), 4)
        self.assertEqual(len(tuple(ProductionCommandV2)), 10)
        self.assertEqual(len(tuple(AuthorityDomainV2)), 4)
        self.assertEqual(len(tuple(ProductionRoleV2)), 18)
        self.assertIsNone(authority_domain_for_command_v2("execute"))

    def test_binding_v3_exactly_binds_solo_policy_without_keys_or_signatures(self):
        final_master = final_master_binding()
        binding = production_binding()
        mapping = binding.to_mapping()

        self.assertEqual(set(mapping), _BINDING_FIELDS)
        self.assertEqual(mapping["binding_type"], "ApprovedCutoverBindingV3")
        self.assertEqual(
            binding.final_master_binding_fingerprint,
            final_master.binding_fingerprint,
        )
        self.assertEqual(
            binding.execution_confirmation_policy,
            "SOLE_MAINTAINER_FRESH_TTY_CONFIRMATION_V1",
        )
        self.assertEqual(
            (
                binding.operator_role_count,
                binding.command_count,
                binding.command_domain_count,
                binding.production_role_count,
                binding.max_execution_confirmation_validity_seconds,
            ),
            (4, 10, 4, 18, 300),
        )
        self.assertEqual(
            (
                binding.assurance_model,
                binding.operator_count,
                binding.independent_reviewer_count,
                binding.external_signer_count,
                binding.issue39_authority_count,
            ),
            ("SOLE_MAINTAINER_SELF_REVIEW", 1, 0, 0, 0),
        )
        serialized = binding.to_canonical_json()
        for forbidden in (b"public_key", b"signature", b"envelope"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual(
            ApprovedCutoverBindingV3.from_json(
                serialized,
                final_master_binding=final_master,
            ),
            binding,
        )
        self.assertIs(
            require_reviewed_production_binding_v3(final_master, binding),
            binding,
        )

    def test_binding_parser_rejects_v2_extra_missing_or_noncanonical_payload(self):
        final_master = final_master_binding()
        binding = production_binding()
        mapping = binding.to_mapping()
        extra = {**mapping, "verification_public_keys": []}
        missing = dict(mapping)
        missing.pop("issue39_authority_count")
        v2 = dict(mapping)
        v2["binding_type"] = "ApprovedCutoverBindingV2"
        payloads = (
            json.dumps(mapping).encode("ascii"),
            json.dumps(extra, sort_keys=True, separators=(",", ":")).encode("ascii"),
            json.dumps(missing, sort_keys=True, separators=(",", ":")).encode("ascii"),
            json.dumps(v2, sort_keys=True, separators=(",", ":")).encode("ascii"),
            b'{"binding_type":"ApprovedCutoverBindingV3",'
            b'"binding_type":"ApprovedCutoverBindingV3"}',
        )

        for payload in payloads:
            with self.subTest(payload=payload[:48]):
                with self.assertRaisesRegex(
                    ProductionBindingError,
                    "R2_PRODUCTION_BINDING_INVALID",
                ):
                    ApprovedCutoverBindingV3.from_json(
                        payload,
                        final_master_binding=final_master,
                    )

    def test_action_fingerprint_is_binding_command_and_subject_bound(self):
        binding = production_binding()
        execute = production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EXECUTE,
        )
        resume = production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.RESUME,
        )
        subject = production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EXECUTE,
            subject_fingerprint="f" * 64,
        )

        self.assertEqual(len(execute), 64)
        self.assertNotEqual(execute, resume)
        self.assertNotEqual(execute, subject)


if __name__ == "__main__":
    unittest.main()
