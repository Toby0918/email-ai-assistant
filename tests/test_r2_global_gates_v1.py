"""Same-binding fourteen-gate coordinator contracts for Issue #101."""

from __future__ import annotations

import unittest
from pathlib import Path

from backend.r2_final_master_closure import (
    ClosureGate,
    FinalMasterBindingV1,
    FinalMasterClosureError,
    GateEvidenceProducerV1,
    GlobalGateStatusV1,
    R2GlobalGateCoordinatorV1,
    R2GlobalGateEvidenceV1,
    ReviewDomainV1,
    closure_gate_registry,
    gate_evidence_registry,
)


class R2GlobalGatesV1Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.evidence = _evidence(self.binding)

    def test_registry_maps_all_fourteen_gates_to_independent_review_sources(self):
        registry = gate_evidence_registry()
        self.assertEqual(tuple(item.gate for item in registry), closure_gate_registry())
        self.assertEqual(len(registry), 14)
        self.assertEqual(len({item.producer for item in registry}), 14)
        self.assertEqual(
            {item.review_domain for item in registry},
            set(ReviewDomainV1),
        )
        self.assertIn(GateEvidenceProducerV1.STANDARDS_REVIEW, {
            item.producer for item in registry
        })
        self.assertIn(GateEvidenceProducerV1.SPEC_REVIEW, {
            item.producer for item in registry
        })
        self.assertIn(GateEvidenceProducerV1.SECURITY_REVIEW, {
            item.producer for item in registry
        })

    def test_coordinator_derives_exact_non_self_certified_same_binding_receipts(self):
        coordinator = self._coordinator()
        self.assertIs(coordinator.status, GlobalGateStatusV1.GLOBAL_GATES_VERIFIED)
        self.assertEqual(coordinator.gate_receipt_count, 14)
        self.assertEqual(coordinator.independent_producer_count, 14)
        self.assertEqual(coordinator.review_domain_count, 7)
        self.assertEqual(tuple(item.gate for item in coordinator.gate_receipts),
                         closure_gate_registry())
        self.assertTrue(all(item.binding_fingerprint == self.binding.binding_fingerprint
                            for item in coordinator.gate_receipts))
        self.assertTrue(all(item.self_certified == 0 for item in coordinator.gate_receipts))
        self.assertEqual(
            (
                coordinator.missing_gate_count,
                coordinator.duplicate_gate_count,
                coordinator.stale_binding_count,
                coordinator.self_certified_count,
                coordinator.required_skip_count,
                coordinator.unclassified_skip_count,
                coordinator.platform_divergence_count,
                coordinator.leakage_finding_count,
                coordinator.private_data_access_count,
                coordinator.real_host_operation_count,
                coordinator.provider_attempt_count,
                coordinator.issue39_code_change_count,
            ),
            (0,) * 12,
        )

    def test_canonical_round_trip_recomputes_receipts_from_independent_evidence(self):
        coordinator = self._coordinator()
        restored = R2GlobalGateCoordinatorV1.from_json(
            coordinator.to_canonical_json(),
            binding=self.binding,
            coordinator_fingerprint="f" * 64,
            evidence=self.evidence,
        )
        self.assertEqual(restored, coordinator)
        self.assertNotIn("authority", coordinator.to_canonical_json().decode("ascii"))
        self.assertNotIn("private", repr(coordinator).lower())

    def test_missing_duplicate_mixed_and_self_certified_evidence_fail_closed(self):
        other = _binding(commit="9" * 40)
        mixed = (
            R2GlobalGateEvidenceV1.create(
                binding=other,
                gate=self.evidence[0].gate,
                producer=self.evidence[0].producer,
                review_domain=self.evidence[0].review_domain,
                evidence_fingerprint="8" * 64,
                producer_fingerprint="7" * 64,
            ),
            *self.evidence[1:],
        )
        invalid = (
            self.evidence[:-1],
            (self.evidence[0], *self.evidence[:-1]),
            mixed,
        )
        for evidence in invalid:
            with self.subTest(count=len(evidence)):
                with self.assertRaisesRegex(
                    FinalMasterClosureError, "R2_FINAL_MASTER_CLOSURE_INVALID"
                ):
                    R2GlobalGateCoordinatorV1.create(
                        binding=self.binding,
                        coordinator_fingerprint="f" * 64,
                        evidence=evidence,
                    )
        with self.assertRaisesRegex(
            FinalMasterClosureError, "R2_FINAL_MASTER_CLOSURE_INVALID"
        ):
            R2GlobalGateCoordinatorV1.create(
                binding=self.binding,
                coordinator_fingerprint=self.evidence[0].producer_fingerprint,
                evidence=self.evidence,
            )

    def test_wrong_gate_producer_domain_skip_and_leakage_injection_fail(self):
        registration = gate_evidence_registry()[0]
        for change in (
            {"producer": gate_evidence_registry()[1].producer},
            {"review_domain": gate_evidence_registry()[2].review_domain},
            {"producer_fingerprint": "1" * 64,
             "evidence_fingerprint": "1" * 64},
        ):
            values = {
                "binding": self.binding,
                "gate": registration.gate,
                "producer": registration.producer,
                "review_domain": registration.review_domain,
                "producer_fingerprint": "2" * 64,
                "evidence_fingerprint": "3" * 64,
            }
            with self.subTest(change=change):
                with self.assertRaisesRegex(
                    FinalMasterClosureError, "R2_FINAL_MASTER_CLOSURE_INVALID"
                ):
                    R2GlobalGateEvidenceV1.create(**{**values, **change})

        coordinator = self._coordinator()
        payload = coordinator.to_canonical_json()
        for replacement in (
            payload.replace(b'"required_skip_count":0', b'"required_skip_count":1'),
            payload.replace(b'"leakage_finding_count":0', b'"leakage_finding_count":1'),
            payload[:-1] + b',"unknown":0}',
        ):
            with self.subTest(payload=replacement[-30:]):
                with self.assertRaisesRegex(
                    FinalMasterClosureError, "R2_FINAL_MASTER_CLOSURE_INVALID"
                ):
                    R2GlobalGateCoordinatorV1.from_json(
                        replacement,
                        binding=self.binding,
                        coordinator_fingerprint="f" * 64,
                        evidence=self.evidence,
                    )

    def test_normative_docs_define_independent_non_authorizing_gates(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "docs/constraints/architecture_constraints.md": (
                "Issue #101 same-binding global-gate architecture",
                "receipt-to-authority",
            ),
            "docs/constraints/linter_constraints.md": (
                "R2 Issue #101 global-gate guards",
                "seven-domain",
            ),
            "docs/constraints/mechanical_rule_translation.md": (
                "Issue #101 fourteen same-binding global-gate rules",
                "derive gate receipts",
            ),
            "docs/security/project_container_cutover_contracts.md": (
                "Issue #101 independent global-gate coordinator",
                "GLOBAL_GATES_VERIFIED",
            ),
            "docs/operations/project_structure.md": (
                "global_gate_registry.py",
                "global_gate_evidence.py",
            ),
            "docs/operations/testing_checklist.md": (
                "test_r2_global_gates_v1.py",
                "fourteen unique producers",
            ),
        }
        for relative, phrases in expected.items():
            text = (root / relative).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(relative=relative, phrase=phrase):
                    self.assertIn(phrase, text)

    def _coordinator(self):
        return R2GlobalGateCoordinatorV1.create(
            binding=self.binding,
            coordinator_fingerprint="f" * 64,
            evidence=self.evidence,
        )


def _binding(commit="a" * 40):
    return FinalMasterBindingV1.create(
        final_commit_oid=commit,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


def _evidence(binding):
    return tuple(
        R2GlobalGateEvidenceV1.create(
            binding=binding,
            gate=item.gate,
            producer=item.producer,
            review_domain=item.review_domain,
            evidence_fingerprint=f"{index + 10:064x}",
            producer_fingerprint=f"{index + 40:064x}",
        )
        for index, item in enumerate(gate_evidence_registry())
    )


if __name__ == "__main__":
    unittest.main()
