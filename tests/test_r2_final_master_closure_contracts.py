"""Finite final-master closure vocabulary and evidence contracts."""

from __future__ import annotations

import unittest

from backend.r2_final_master_closure import (
    ClosureGate,
    ClosureGap,
    FinalMasterBindingV1,
    FinalMasterClosureError,
    FinalMasterClosureStatus,
    FindingClassification,
    R2ClosureGateReceiptV1,
    R2ClosureGapProofV1,
    R2FinalMasterClosureReceiptV1,
    closure_gate_registry,
    closure_gap_registry,
    closure_map_fingerprint,
    finding_classification_registry,
)


class R2FinalMasterClosureContractTests(unittest.TestCase):
    def test_closure_gap_registry_is_exact_finite_and_dependency_ordered(self):
        registry = closure_gap_registry()

        self.assertEqual(
            tuple(item.gap for item in registry),
            (
                ClosureGap.TERMINAL_CONTRACT,
                ClosureGap.PRODUCTION_COMPOSITION,
                ClosureGap.GIT_BYTE_REPRODUCIBILITY,
                ClosureGap.CRASH_RECOVERY,
                ClosureGap.RETENTION_NO_DELETION,
                ClosureGap.RUNBOOK_SEMANTIC_CLOSURE,
                ClosureGap.WINDOWS_CI_PROVENANCE,
                ClosureGap.GLOBAL_GATES,
            ),
        )
        self.assertEqual(len(set(registry)), 8)
        self.assertEqual(registry[0].blocked_by, ())
        self.assertEqual(
            tuple(item.blocked_by for item in registry[1:]),
            tuple((registry[index].gap,) for index in range(7)),
        )
        self.assertEqual(
            tuple(item.owning_issues for item in registry),
            (
                (86,),
                (87, 88, 89, 90, 91, 94, 95, 96),
                (92,),
                (93, 94, 95, 96, 97),
                (98,),
                (99,),
                (100,),
                (101, 102),
            ),
        )
        self.assertEqual(
            tuple(item.decision_ids for item in registry),
            (
                ("D-R2-CLOSURE-1", "D-R2-FINITE-MAP-1"),
                ("D-R2-COMPOSITION-1",),
                ("D-R2-GIT-BYTES-1",),
                ("D-R2-CRASH-RECOVERY-1",),
                ("D-R2-RETENTION-1",),
                ("D-R2-RUNBOOK-DRIFT-1",),
                ("D-R2-CI-PROVENANCE-1",),
                ("D-R2-GLOBAL-GATES-1",),
            ),
        )

    def test_global_gate_registry_is_exactly_fourteen_kinds(self):
        self.assertEqual(
            closure_gate_registry(),
            (
                ClosureGate.FINAL_MASTER_BINDING,
                ClosureGate.CLOSURE_SURFACE_COMPLETENESS,
                ClosureGate.PRODUCTION_COMPOSITION,
                ClosureGate.GIT_BYTES,
                ClosureGate.DEPENDENCY_ACTION_PROVENANCE,
                ClosureGate.WINDOWS_NATIVE,
                ClosureGate.PORTABLE_FULL_SUITE,
                ClosureGate.RUNBOOK_SEMANTICS,
                ClosureGate.CRASH_RECOVERY,
                ClosureGate.RETENTION_NO_DELETION,
                ClosureGate.DOCUMENTATION,
                ClosureGate.MECHANICAL_ARCHITECTURE,
                ClosureGate.LEAKAGE,
                ClosureGate.MAINTENANCE_SCOPE,
            ),
        )

    def test_finding_classification_registry_is_closed(self):
        self.assertEqual(
            finding_classification_registry(),
            (
                FindingClassification.EXISTING_GAP_INSTANCE,
                FindingClassification.SURFACE_COMPLETENESS_DEFECT,
                FindingClassification.EVIDENCE_DEFECT,
                FindingClassification.EXTERNAL_AUTHORITY_OR_STATE,
                FindingClassification.OUT_OF_SCOPE_NONBLOCKING,
                FindingClassification.SECURITY_INCIDENT,
                FindingClassification.DECISION_CONTRADICTION,
                FindingClassification.DUPLICATE_OR_HISTORICAL,
            ),
        )

    def test_final_master_binding_is_canonical_and_commits_the_closure_map(self):
        binding = _binding()

        self.assertEqual(
            binding.closure_map_fingerprint,
            closure_map_fingerprint(),
        )
        self.assertEqual(
            FinalMasterBindingV1.from_json(binding.to_canonical_json()),
            binding,
        )
        self.assertNotIn("authority", repr(binding).lower())
        self.assertNotIn("path", repr(binding).lower())

    def test_gap_proof_is_complete_content_free_and_bound_to_final_master(self):
        binding = _binding()
        proof = R2ClosureGapProofV1.create(
            binding=binding,
            gap=ClosureGap.TERMINAL_CONTRACT,
            evidence_fingerprint="f" * 64,
        )

        self.assertEqual(proof.binding_fingerprint, binding.binding_fingerprint)
        self.assertEqual(
            R2ClosureGapProofV1.from_json(
                proof.to_canonical_json(),
                binding=binding,
            ),
            proof,
        )
        self.assertEqual(
            {
                name: proof.to_mapping()[name]
                for name in (
                    "completed",
                    "open_findings",
                    "surface_omissions",
                    "required_skips",
                    "unclassified_skips",
                    "leakage_findings",
                    "cleanup_operations",
                    "provider_attempts",
                    "real_host_operations",
                    "issue39_code_changes_required",
                )
            },
            {
                "completed": 1,
                "open_findings": 0,
                "surface_omissions": 0,
                "required_skips": 0,
                "unclassified_skips": 0,
                "leakage_findings": 0,
                "cleanup_operations": 0,
                "provider_attempts": 0,
                "real_host_operations": 0,
                "issue39_code_changes_required": 0,
            },
        )

    def test_gate_receipt_is_verified_non_self_certified_and_same_bound(self):
        binding = _binding()
        receipt = R2ClosureGateReceiptV1.create(
            binding=binding,
            gate=ClosureGate.FINAL_MASTER_BINDING,
            evidence_fingerprint="1" * 64,
            producer_fingerprint="2" * 64,
        )

        self.assertEqual(receipt.binding_fingerprint, binding.binding_fingerprint)
        self.assertEqual(
            R2ClosureGateReceiptV1.from_json(
                receipt.to_canonical_json(),
                binding=binding,
            ),
            receipt,
        )
        self.assertEqual(receipt.verified, 1)
        self.assertEqual(receipt.self_certified, 0)
        self.assertEqual(receipt.required_skips, 0)
        self.assertEqual(receipt.unclassified_skips, 0)
        self.assertEqual(receipt.leakage_findings, 0)

    def test_terminal_receipt_binds_all_gaps_and_gates_to_one_final_master(self):
        binding = _binding()
        gap_proofs = tuple(
            R2ClosureGapProofV1.create(
                binding=binding,
                gap=item.gap,
                evidence_fingerprint=f"{index + 1:064x}",
            )
            for index, item in enumerate(closure_gap_registry())
        )
        gate_receipts = tuple(
            R2ClosureGateReceiptV1.create(
                binding=binding,
                gate=gate,
                evidence_fingerprint=f"{index + 20:064x}",
                producer_fingerprint=f"{index + 40:064x}",
            )
            for index, gate in enumerate(closure_gate_registry())
        )

        receipt = R2FinalMasterClosureReceiptV1.create(
            binding=binding,
            gap_proofs=gap_proofs,
            gate_receipts=gate_receipts,
        )

        self.assertIs(
            receipt.terminal_status,
            FinalMasterClosureStatus.ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW,
        )
        self.assertEqual(receipt.final_commit_oid, binding.final_commit_oid)
        self.assertEqual(receipt.final_tree_oid, binding.final_tree_oid)
        self.assertEqual(
            receipt.source_package_fingerprint,
            binding.source_package_fingerprint,
        )
        self.assertEqual(receipt.gap_proof_count, 8)
        self.assertEqual(receipt.gate_receipt_count, 14)
        self.assertEqual(receipt.issue39_code_changes_required, 0)
        self.assertEqual(
            R2FinalMasterClosureReceiptV1.from_json(
                receipt.to_canonical_json(),
                binding=binding,
                gap_proofs=gap_proofs,
                gate_receipts=gate_receipts,
            ),
            receipt,
        )
        self.assertNotIn("authority", receipt.to_canonical_json().decode("ascii"))

    def test_terminal_receipt_rejects_missing_duplicate_and_mixed_evidence(self):
        binding = _binding()
        gap_proofs = tuple(
            R2ClosureGapProofV1.create(
                binding=binding,
                gap=item.gap,
                evidence_fingerprint=f"{index + 1:064x}",
            )
            for index, item in enumerate(closure_gap_registry())
        )
        gate_receipts = tuple(
            R2ClosureGateReceiptV1.create(
                binding=binding,
                gate=gate,
                evidence_fingerprint=f"{index + 20:064x}",
                producer_fingerprint=f"{index + 40:064x}",
            )
            for index, gate in enumerate(closure_gate_registry())
        )
        other_binding = FinalMasterBindingV1.create(
            final_commit_oid="9" * 40,
            final_tree_oid="8" * 40,
            source_package_fingerprint="7" * 64,
            runbook_fingerprint="6" * 64,
            workflow_fingerprint="5" * 64,
        )
        mixed = (
            R2ClosureGapProofV1.create(
                binding=other_binding,
                gap=ClosureGap.TERMINAL_CONTRACT,
                evidence_fingerprint="4" * 64,
            ),
            *gap_proofs[1:],
        )

        invalid_sets = (
            (gap_proofs[:-1], gate_receipts),
            ((gap_proofs[0], *gap_proofs[:-1]), gate_receipts),
            (mixed, gate_receipts),
            (gap_proofs, gate_receipts[:-1]),
            (gap_proofs, (gate_receipts[0], *gate_receipts[:-1])),
        )
        for invalid_gaps, invalid_gates in invalid_sets:
            with self.subTest(
                gaps=len(invalid_gaps),
                gates=len(invalid_gates),
            ):
                with self.assertRaisesRegex(
                    FinalMasterClosureError,
                    "R2_FINAL_MASTER_CLOSURE_INVALID",
                ):
                    R2FinalMasterClosureReceiptV1.create(
                        binding=binding,
                        gap_proofs=invalid_gaps,
                        gate_receipts=invalid_gates,
                    )

    def test_binding_rejects_noncanonical_or_tampered_identity(self):
        with self.assertRaisesRegex(
            FinalMasterClosureError,
            "R2_FINAL_MASTER_CLOSURE_INVALID",
        ):
            FinalMasterBindingV1.create(
                final_commit_oid="A" * 40,
                final_tree_oid="b" * 40,
                source_package_fingerprint="c" * 64,
                runbook_fingerprint="d" * 64,
                workflow_fingerprint="e" * 64,
            )

        binding = _binding()
        duplicate = (
            binding.to_canonical_json()[:-1]
            + b',"binding_type":"FinalMasterBindingV1"}'
        )
        with self.assertRaisesRegex(
            FinalMasterClosureError,
            "R2_FINAL_MASTER_CLOSURE_INVALID",
        ):
            FinalMasterBindingV1.from_json(duplicate)


def _binding() -> FinalMasterBindingV1:
    return FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


if __name__ == "__main__":
    unittest.main()
