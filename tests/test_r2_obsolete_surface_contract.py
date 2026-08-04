"""R2 reachability contraction and real-entry locks for Issue #83."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R2_PACKAGES = tuple((ROOT / "backend").glob("r2_*"))
PRODUCTION_TRANSACTION_ADAPTER = (
    ROOT / "backend" / "r2_production_composition" / "transaction.py"
)


class R2ObsoleteSurfaceContractTests(unittest.TestCase):
    def test_r2_surface_has_no_obsolete_batch_or_success_semantics(self):
        sources = {
            item: item.read_text(encoding="utf-8")
            for package in R2_PACKAGES
            for item in package.glob("*.py")
        }
        source = "\n".join(sources.values())
        for forbidden in (
            "ManagedActivationReceiptSetV1",
            "ManagedActivationPhase",
            "deterministic_rules",
            "pip check",
            "from backend.cutover_service_lifecycle import",
        ):
            self.assertNotIn(forbidden, source)
        for reviewed_adapter_term in (
            "CUTOVER_SUCCEEDED",
            "cutover_transaction_composition",
        ):
            locations = tuple(
                path
                for path, content in sources.items()
                if reviewed_adapter_term in content
            )
            self.assertEqual(locations, (PRODUCTION_TRANSACTION_ADAPTER,))

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

    def test_all_three_v2_roots_are_dormant_without_an_external_issuer(self):
        cases = (
            (
                "backend.r2_preflight_process",
                "current-topology",
                "DORMANT_NO_EXTERNAL_ISSUER accepted=0 rejected=0 read_operations=0\n",
            ),
            (
                "backend.r2_evidence_process",
                "publish",
                "DORMANT_NO_EXTERNAL_ISSUER accepted=0 rejected=0 published=0\n",
            ),
            (
                "backend.r2_transaction_process",
                "execute",
                "DORMANT_NO_EXTERNAL_ISSUER accepted=0 rejected=0 mutations=0\n",
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
                self.assertEqual((completed.returncode, completed.stderr), (0, ""))
                self.assertEqual(completed.stdout, expected)


if __name__ == "__main__":
    unittest.main()
