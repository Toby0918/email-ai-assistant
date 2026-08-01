"""One fresh physical NTFS sandbox across the highest R2 seams."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_r2_synthetic_topology.py"


@unittest.skipUnless(sys.platform == "win32", "Windows NTFS/TTY/process proof")
class R2FullTopologyWindowsTests(unittest.TestCase):
    def test_fixed_script_proves_complete_topology_without_public_leakage(self):
        completed = subprocess.run(
            (sys.executable, "-B", str(SCRIPT)),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        value = json.loads(completed.stdout)
        self.assertEqual(value["status"], "R2_SYNTHETIC_VERIFICATION_COMPLETE")
        self.assertEqual(
            value["counts"],
            {
                "authorization_domains": 4,
                "independent_audits": 2,
                "managed_units": 4,
                "process_types": 3,
                "project_container_zones": 9,
                "repositories": 1,
                "semantic_gap_cases": 70,
                "worktrees": 11,
            },
        )
        self.assertEqual(value["terminal_status"], "CUTOVER_SUCCESS")
        self.assertEqual(value["provider_attempts"], 0)
        self.assertEqual(value["public_leakage"], 0)
        self.assertEqual(value["real_host_operations"], 0)
        self.assertEqual(len(set(value["fingerprints"].values())), 6)
        for forbidden in ("D:\\", "C:\\", "AppData", "email", "private"):
            self.assertNotIn(forbidden.lower(), completed.stdout.lower())

    def test_portable_contract_makes_no_windows_claim(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertIn('@unittest.skipUnless(sys.platform == "win32"', source)
        portable = (
            ROOT / "tests" / "test_r2_verification_evidence_contracts.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("NTFS", "Windows ACL", "real TTY", "process isolation"):
            self.assertNotIn(forbidden, portable)


if __name__ == "__main__":
    unittest.main()
