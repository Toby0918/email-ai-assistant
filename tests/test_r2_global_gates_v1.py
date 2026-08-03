"""Signed same-binding fourteen-gate coordinator contracts for Issue #101."""

from pathlib import Path
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_final_master_closure import (
    FinalMasterBindingV1,
    FinalMasterClosureError,
    GlobalGateStatusV1,
    R2GlobalGateCoordinatorV1,
    R2GlobalGateEvidenceV1,
    ReviewDomainV1,
    closure_gate_registry,
    gate_evidence_registry,
)
from backend.r2_final_master_closure._canonical import canonical_json, fingerprint
from backend.r2_final_master_closure.global_gate_evidence import ZERO_GATE_FIELDS
from backend.r2_final_master_closure.global_gate_registry import GateEvidenceRegistrationV1


class R2GlobalGatesV1Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.keys = tuple(Ed25519PrivateKey.generate() for _ in range(14))
        self.registry = tuple(
            GateEvidenceRegistrationV1(
                item.gate, item.producer, item.review_domain,
                key.public_key().public_bytes_raw(),
            )
            for item, key in zip(gate_evidence_registry(), self.keys, strict=True)
        )
        with self._registry_patch():
            self.evidence = _evidence(self.binding, self.registry, self.keys)

    def _registry_patch(self):
        return patch(
            "backend.r2_final_master_closure.global_gate_evidence.gate_evidence_registry",
            return_value=self.registry,
        )

    def test_registry_maps_all_fourteen_gates_to_independent_fixed_public_keys(self):
        registry = gate_evidence_registry()
        self.assertEqual(tuple(item.gate for item in registry), closure_gate_registry())
        self.assertEqual(len(registry), 14)
        self.assertEqual(len({item.producer for item in registry}), 14)
        self.assertEqual(len({item.verification_public_key for item in registry}), 14)
        self.assertTrue(all(len(item.verification_public_key) == 32 for item in registry))
        self.assertEqual({item.review_domain for item in registry}, set(ReviewDomainV1))

    def test_registry_uses_reviewed_production_trust_anchors(self):
        expected = {
            "final_master_verifier": "9cb7cd1c4efdd4908f7af2a9b3bf450bf8072482b2d0398e1f904929d305beee",
            "spec_review": "609df0856a9fc70e7b09bb6c47337c649894826db7f144b84754cfb7b9c538d1",
            "security_review": "c3c1f440f8706f1c18f71ac05c510f5296b05b77921dda59465a744cffdf2873",
            "git_byte_verifier": "c72347def07454e1d27b16deba6bd0c533b9612b258921ebbf900d77709acc8b",
            "ci_provenance_reconciler": "79ba03a98f33e786429ffbfc384708dd4d4db002843d03b39cdfb18d805965aa",
            "windows_native_verifier": "473a3115d49d25a462fca247495faf15e9e95214ea78044abbee49e9d0efeb58",
            "portable_suite_verifier": "c9db5d551b43bfb81d9d46adfa00061067ecd70067f405da1624e36033914633",
            "operator_runbook_review": "4dac025e27c1ec0a1e0493b014079009dc90a0f0271ae2bf20b700ffcc84e14c",
            "crash_recovery_verifier": "cee003c822ff18da86b79f448a79d0a3d8037340d42c23bb0402590419298b03",
            "retention_verifier": "1c43993142ba36e3db23a17969c8636bb345e03518d0110b04f1c812bd3d5fdf",
            "documentation_review": "9c0a4374ee55a7762486f6dbc2400644ffbc2c4e1a9fb74118a3a85211b2f6a5",
            "standards_review": "6a398607d471583890c7040e4f653043221d312089566ce079168e8c98fbbbc5",
            "leakage_scanner": "c07e985530416b1027ec2bc19dd648a8b366838cd1439133193cbcbf47ed09c8",
            "maintenance_review": "ecf1302df9f6a3086d4f57ccf3cdff4b9ed13b2bfbd4991bab22c97434b1a3e0",
        }
        actual = {
            item.producer.value: item.verification_public_key.hex()
            for item in gate_evidence_registry()
        }
        self.assertEqual(actual, expected)

    def test_signed_evidence_derives_exact_non_self_certified_receipts(self):
        coordinator = R2GlobalGateCoordinatorV1.create(
            binding=self.binding, evidence=self.evidence
        )
        self.assertIs(coordinator.status, GlobalGateStatusV1.GLOBAL_GATES_VERIFIED)
        self.assertEqual(coordinator.gate_receipt_count, 14)
        self.assertEqual(coordinator.independent_producer_count, 14)
        self.assertEqual(coordinator.review_domain_count, 7)
        self.assertTrue(all(item.self_certified == 0 for item in coordinator.gate_receipts))
        self.assertEqual(
            R2GlobalGateCoordinatorV1.from_json(
                coordinator.to_canonical_json(),
                binding=self.binding,
                evidence=self.evidence,
            ),
            coordinator,
        )

    def test_arbitrary_fingerprints_cannot_mint_verified_evidence(self):
        registration = self.registry[0]
        body = _body(self.binding, registration, "7" * 64)
        forged = canonical_json({**body, "signature_hex": "8" * 128})
        with self._registry_patch(), self.assertRaisesRegex(
            FinalMasterClosureError, "R2_FINAL_MASTER_CLOSURE_INVALID"
        ):
            R2GlobalGateEvidenceV1.from_signed_json(forged, binding=self.binding)
        self.assertFalse(hasattr(R2GlobalGateEvidenceV1, "create"))

    def test_tamper_wrong_key_missing_duplicate_and_mixed_binding_fail(self):
        payload = self.evidence[0].to_canonical_json()
        tampered = payload.replace(b'"verified":1', b'"verified":0')
        with self._registry_patch(), self.assertRaises(FinalMasterClosureError):
            R2GlobalGateEvidenceV1.from_signed_json(tampered, binding=self.binding)
        other = _binding(commit="9" * 40)
        invalid = (self.evidence[:-1], (self.evidence[0], *self.evidence[:-1]))
        for evidence in invalid:
            with self.assertRaises(FinalMasterClosureError):
                R2GlobalGateCoordinatorV1.create(binding=self.binding, evidence=evidence)
        with self.assertRaises(FinalMasterClosureError):
            R2GlobalGateCoordinatorV1.create(binding=other, evidence=self.evidence)

    def test_normative_docs_define_external_signed_non_authorizing_gates(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "docs/constraints/architecture_constraints.md": "receipt-to-authority",
            "docs/constraints/linter_constraints.md": "seven-domain",
            "docs/constraints/mechanical_rule_translation.md": "derive gate receipts",
            "docs/security/project_container_cutover_contracts.md": "GLOBAL_GATES_VERIFIED",
        }
        for relative, phrase in expected.items():
            self.assertIn(phrase, (root / relative).read_text(encoding="utf-8"))


def _binding(commit="a" * 40):
    return FinalMasterBindingV1.create(
        final_commit_oid=commit,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


def _body(binding, registration, evidence_fingerprint):
    producer = fingerprint("r2-gate-producer-v1", {
        "producer": registration.producer.value,
        "verification_public_key_hex": registration.verification_public_key.hex(),
    })
    return {
        "evidence_type": "R2SignedGlobalGateEvidenceV1",
        "binding_fingerprint": binding.binding_fingerprint,
        "gate": registration.gate.value,
        "producer": registration.producer.value,
        "review_domain": registration.review_domain.value,
        "evidence_fingerprint": evidence_fingerprint,
        "producer_fingerprint": producer,
        "verified": 1,
        "self_certified": 0,
        **{name: 0 for name in ZERO_GATE_FIELDS},
    }


def _evidence(binding, registry, keys):
    result = []
    for index, (registration, key) in enumerate(zip(registry, keys, strict=True)):
        body = _body(binding, registration, f"{index + 10:064x}")
        payload = canonical_json({
            **body,
            "signature_hex": key.sign(canonical_json(body)).hex(),
        })
        result.append(R2GlobalGateEvidenceV1.from_signed_json(payload, binding=binding))
    return tuple(result)


if __name__ == "__main__":
    unittest.main()
