"""Exercise the shared browser renderer and page events with synthetic input."""

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrowserActionQueueTests(unittest.TestCase):
    def test_action_queue_and_page_lifecycle(self) -> None:
        if not shutil.which("node"):
            self.skipTest("Node.js is required for browser behavior tests")
        result = subprocess.run(
            ["node", "--test", "tests/browser/action_queue.test.cjs"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
