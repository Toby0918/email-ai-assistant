"""Issue #110 removes legacy closure and command-authorization surfaces."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REMOVED_PATHS = (
    "backend/r2_final_master_closure",
    "backend/r2_external_artifacts_v1",
    "backend/r2_operator_process/envelope.py",
    "backend/r2_operator_process/dormant_context.py",
    "backend/r2_preflight_process/entry.py",
    "backend/r2_evidence_process/entry.py",
    "backend/r2_transaction_process/entry.py",
    "scripts/prepare_r2_external_artifacts.py",
    "tests/r2_preflight_process_fixture.py",
    "tests/r2_evidence_process_fixture.py",
    "tests/r2_transaction_process_fixture.py",
)


class R2ObsoleteSurfaceContractTests(unittest.TestCase):
    def test_removed_paths_are_physically_absent(self):
        observed = []
        for relative in REMOVED_PATHS:
            path = ROOT / relative
            if path.is_file() or (path.is_dir() and any(path.glob("*.py"))):
                observed.append(relative)
        self.assertEqual(observed, [])

    def test_process_graph_has_no_v1_v2_trust_compatibility(self):
        packages = (
            ROOT / "backend" / "r2_operator_process",
            ROOT / "backend" / "r2_preflight_process",
            ROOT / "backend" / "r2_evidence_process",
            ROOT / "backend" / "r2_transaction_process",
        )
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for package in packages
            for path in package.glob("*.py")
        )
        for forbidden in (
            "ApprovedCutoverBindingV2",
            "DurableAuthorityClaimV2",
            "PublicKeyRoleV2",
            "R2ProductionAuthorityEnvelopeV2",
            "verify_authorization_envelope",
            "verify_production_authority_v2",
            "DORMANT_NO_EXTERNAL_ISSUER",
        ):
            self.assertNotIn(forbidden, source)

    def test_all_three_module_roots_emit_exact_dormant_status(self):
        cases = (
            (
                "backend.r2_preflight_process",
                "current-topology",
                "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 read_operations=0\n",
            ),
            (
                "backend.r2_evidence_process",
                "publish",
                "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 published=0\n",
            ),
            (
                "backend.r2_transaction_process",
                "execute",
                "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 mutations=0\n",
            ),
        )
        for module, verb, expected in cases:
            completed = subprocess.run(
                (sys.executable, "-B", "-m", module, verb),
                cwd=ROOT,
                input="synthetic-unlock-attempt\n",
                capture_output=True,
                text=True,
                check=False,
            )
            with self.subTest(module=module):
                self.assertEqual((completed.returncode, completed.stderr), (0, ""))
                self.assertEqual(completed.stdout, expected)


if __name__ == "__main__":
    unittest.main()
