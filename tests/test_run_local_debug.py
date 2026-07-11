"""Tests for the local debug server entry script."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_local_debug.py"


class RunLocalDebugTests(unittest.TestCase):
    def test_script_help_runs_from_project_root(self) -> None:
        # The documented command is `python scripts/run_local_debug.py`.
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--host", result.stdout)
        self.assertIn("--port", result.stdout)

    def test_script_rejects_non_loopback_host_before_bind(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--host", "0.0.0.0", "--port", "0"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supported loopback address", result.stderr)
        self.assertNotIn("0.0.0.0", result.stderr)


if __name__ == "__main__":
    unittest.main()
