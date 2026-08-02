"""R2 reachability contraction and real-entry locks for Issue #83."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R2_PACKAGES = tuple((ROOT / "backend").glob("r2_*"))


class R2ObsoleteSurfaceContractTests(unittest.TestCase):
    def test_r2_surface_has_no_obsolete_batch_or_success_semantics(self):
        source = "\n".join(
            item.read_text(encoding="utf-8")
            for package in R2_PACKAGES
            for item in package.glob("*.py")
        )
        for forbidden in (
            "ManagedActivationReceiptSetV1",
            "ManagedActivationPhase",
            "CUTOVER_SUCCEEDED",
            "deterministic_rules",
            "pip check",
            "from backend.cutover_service_lifecycle import",
            "cutover_transaction_composition",
        ):
            self.assertNotIn(forbidden, source)

    def test_real_process_entries_never_import_synthetic_substitutes(self):
        for package_name in (
            "r2_preflight_process",
            "r2_evidence_process",
            "r2_transaction_process",
        ):
            entry = ROOT / "backend" / package_name / "entry.py"
            source = entry.read_text(encoding="utf-8")
            self.assertNotIn(".testing", source)
            self.assertNotIn("Synthetic", source)
            self.assertIn("BLOCKED_NO_APPROVED_COMMAND", source)

    def test_all_three_real_entries_reject_redirected_ingress_with_fixed_output(self):
        cases = (
            (
                "backend.r2_preflight_process",
                "current-topology",
                "BLOCKED_TTY accepted=0 rejected=1 host_operations=0\n",
            ),
            (
                "backend.r2_evidence_process",
                "publish",
                "BLOCKED_TTY accepted=0 rejected=1 published=0\n",
            ),
            (
                "backend.r2_transaction_process",
                "execute",
                "BLOCKED_TTY accepted=0 rejected=1 mutations=0\n",
            ),
        )
        for module, verb, expected in cases:
            with self.subTest(module=module):
                completed = subprocess.run(
                    (sys.executable, "-B", "-m", module, verb),
                    cwd=ROOT,
                    input="ignored\n",
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual((completed.returncode, completed.stderr), (3, ""))
                self.assertEqual(completed.stdout, expected)


if __name__ == "__main__":
    unittest.main()
