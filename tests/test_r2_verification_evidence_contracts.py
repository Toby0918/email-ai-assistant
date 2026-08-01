"""Fresh R2 criteria, matrix, script, bundle, and package fingerprints."""

from __future__ import annotations

import unittest
from pathlib import Path

from backend.r2_verification_evidence import (
    R2VerificationBundleV1,
    build_verification_evidence,
    semantic_gap_matrix,
)


ROOT = Path(__file__).resolve().parents[1]
CRITERIA = ROOT / "docs" / "operations" / "r2_synthetic_verification_criteria.md"
SCRIPT = ROOT / "scripts" / "verify_r2_synthetic_topology.py"
EVIDENCE = ROOT / "docs" / "operations" / "r2_synthetic_verification_evidence.md"


class R2VerificationEvidenceContractTests(unittest.TestCase):
    def test_matrix_is_exact_complete_forward_and_reverse_vocabulary(self):
        matrix = semantic_gap_matrix()
        self.assertEqual(len(matrix), 70)
        self.assertEqual(len(set(matrix)), 70)
        self.assertEqual({item.direction for item in matrix}, {"forward", "reverse"})
        self.assertEqual(
            {item.semantic for item in matrix},
            {
                "acl_scan",
                "staging",
                "publication",
                "service",
                "audit_append",
                "recovery",
                "final_seal",
            },
        )

    def test_all_five_fingerprints_are_distinct_deterministic_and_content_free(self):
        bundle = _bundle()
        first = build_verification_evidence(
            criteria_bytes=CRITERIA.read_bytes(),
            script_bytes=SCRIPT.read_bytes(),
            bundle=bundle,
            r2_surface_fingerprint="a" * 64,
        )
        second = build_verification_evidence(
            criteria_bytes=CRITERIA.read_bytes(),
            script_bytes=SCRIPT.read_bytes(),
            bundle=bundle,
            r2_surface_fingerprint="a" * 64,
        )
        observed = (
            first.criteria_fingerprint,
            first.matrix_fingerprint,
            first.script_fingerprint,
            first.bundle_fingerprint,
            first.package_fingerprint,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(set(observed)), 5)
        self.assertTrue(all(len(item) == 64 for item in observed))
        public = repr(first)
        for forbidden in ("D:\\", "email", "provider", "private", "path"):
            self.assertNotIn(forbidden, public.lower())

    def test_accepted_prototype_is_non_authorizing_prior_art_only(self):
        text = CRITERIA.read_text(encoding="utf-8")
        self.assertIn(
            "2923d0940a609b8bb2f9112ba1c1708511de44bd8ecf8611b45603fcbbe49af1",
            text,
        )
        self.assertIn("non-authorizing feasibility prior art only", text)
        self.assertNotIn("authorizes Issue #39", text)

    def test_recorded_fingerprints_match_fresh_verifier_evidence(self):
        evidence = EVIDENCE.read_text(encoding="utf-8")
        expected = (
            "82f7520f14b7ca6b88f2f5759edbe5c4a78ae1c5f7b346182320b660ad679d34",
            "627fa92e43112543f6721da25bea4a509b795f7bd01ec662d6c415c7c5280544",
            "5c595e2413163ba2d502b177775a9bd88a60255f96a84d57803890b6cbb20a8f",
            "5c82158257a4791ee472464f309264c12930fe01d68f243cf41653e8495d9a38",
            "e6e911e6ead5b8cc4fffd84d22fe03961f64a3e50620050e7fa2066272b57063",
            "7ef79199a1ca915548f2cbdc056ecb182e16f86c459ee367b5661d337e49f3d2",
        )
        for fingerprint in expected:
            with self.subTest(fingerprint=fingerprint):
                self.assertIn(fingerprint, evidence)


def _bundle():
    return R2VerificationBundleV1.create(
        {
            "schema_version": 1,
            "windows_ntfs": True,
            "process_type_count": 3,
            "authorization_domain_count": 4,
            "real_tty_channel_count": 3,
            "independent_audit_process_count": 2,
            "project_container_zone_count": 9,
            "repository_count": 1,
            "worktree_count": 11,
            "managed_unit_count": 4,
            "semantic_gap_case_count": 70,
            "rule_fallback_result_count": 1,
            "persisted_row_count": 1,
            "provider_attempt_count": 0,
            "public_leakage_count": 0,
            "real_host_operation_count": 0,
            "terminal_status": "CUTOVER_SUCCESS",
        }
    )


if __name__ == "__main__":
    unittest.main()
