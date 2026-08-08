"""Windows fresh-process proof that Issue #110 production stays dormant."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.r2_synthetic_topology_support import _surface_source_paths


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    (
        "backend.r2_preflight_process",
        ("current-topology", "host-baseline", "evidence-review", "evidence-verification", "final-audit-readiness", "recovery-inspection"),
        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 read_operations=0\n",
    ),
    (
        "backend.r2_evidence_process",
        ("publish",),
        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 published=0\n",
    ),
    (
        "backend.r2_transaction_process",
        ("execute", "resume", "rollback"),
        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 mutations=0\n",
    ),
)


@unittest.skipUnless(sys.platform == "win32", "Windows process proof")
class R2FullTopologyWindowsTests(unittest.TestCase):
    def test_all_ten_fixed_verbs_ignore_terminal_environment_and_artifacts(self):
        environment = dict(os.environ)
        environment.update(
            {
                "R2_ISSUE39_APPROVED": "1",
                "R2_EXECUTION_CONFIRMATION": "synthetic-unlock-attempt",
                "R2_CLOSURE_ARTIFACT": "synthetic-unlock-attempt",
            }
        )
        for module, verbs, expected in CASES:
            for verb in verbs:
                completed = subprocess.run(
                    (sys.executable, "-B", "-m", module, verb),
                    cwd=ROOT,
                    env=environment,
                    input="synthetic-unlock-attempt\n",
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                with self.subTest(module=module, verb=verb):
                    self.assertEqual(completed.returncode, 0)
                    self.assertEqual(completed.stderr, "")
                    self.assertEqual(completed.stdout, expected)

    def test_poison_bootstrap_workers_remain_dormant(self):
        cases = (
            ("tests.r2_preflight_process_worker", "current-topology", CASES[0][2]),
            ("tests.r2_evidence_process_worker", "publish", CASES[1][2]),
            ("tests.r2_transaction_process_worker", "execute", CASES[2][2]),
        )
        for module, verb, expected in cases:
            completed = subprocess.run(
                (sys.executable, "-B", "-m", module, verb),
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            with self.subTest(module=module):
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(completed.stderr, "")
                self.assertEqual(completed.stdout, expected)

    def test_surface_closure_uses_new_dormant_roots_not_removed_ingress(self):
        observed = {
            path.relative_to(ROOT).as_posix()
            for path in _surface_source_paths(ROOT)
        }
        required = {
            "backend/r2_preflight_process/production_v2.py",
            "backend/r2_evidence_process/production_v2.py",
            "backend/r2_transaction_process/production_v2.py",
            "tests/r2_preflight_process_worker.py",
            "tests/r2_evidence_process_worker.py",
            "tests/r2_transaction_process_worker.py",
            "tests/windows_synthetic_tty_host.py",
        }
        removed = {
            "backend/r2_operator_process/dormant_context.py",
            "backend/r2_operator_process/envelope.py",
            "backend/r2_preflight_process/entry.py",
            "backend/r2_evidence_process/entry.py",
            "backend/r2_transaction_process/entry.py",
        }
        self.assertEqual(required - observed, set())
        self.assertEqual(removed & observed, set())

    def test_portable_contract_makes_no_windows_process_claim(self):
        portable = (
            ROOT / "tests" / "test_r2_verification_evidence_contracts.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("NTFS", "Windows ACL", "real TTY", "process isolation"):
            self.assertNotIn(forbidden, portable)


if __name__ == "__main__":
    unittest.main()
