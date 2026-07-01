"""Tests for scripts/maintenance_scan.py.

Run:
    python -m unittest discover -s tests -p "test_maintenance_scan.py"
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "maintenance_scan.py"


class MaintenanceScanTests(unittest.TestCase):
    def test_script_exists(self) -> None:
        # The cleanup automation depends on this script staying runnable.
        self.assertTrue(SCRIPT.exists(), "scripts/maintenance_scan.py should exist")

    def test_report_rendering(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan")
        report = module.render_report([])
        self.assertIn("# Cleanup Agent Report", report)
        self.assertIn("No cleanup findings detected.", report)

    def test_front_matter_parser_accepts_required_fields(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan")
        text = """---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Example
"""
        self.assertTrue(module.has_required_front_matter(text))

    def test_front_matter_parser_accepts_bom_and_crlf(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan")
        text = "\ufeff---\r\nlast_update: 2026-06-29\r\nstatus: active\r\nowner: \"@tobyWang\"\r\nreview_cycle: monthly\r\nsource_type: operation_guide\r\n---\r\n"
        self.assertTrue(module.has_required_front_matter(text))

    def test_script_runs_directly(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Cleanup Agent Report", result.stdout)


if __name__ == "__main__":
    unittest.main()
