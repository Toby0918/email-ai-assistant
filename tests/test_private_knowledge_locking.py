"""Cross-process kernel-lock probes for private ciphertext mutations."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from backend.private_knowledge.atomic_ciphertext import exclusive_lock
from backend.private_knowledge.errors import PrivateKnowledgeError


class PrivateKnowledgeLockingTests(unittest.TestCase):
    def test_contention_is_fixed_and_abrupt_owner_exit_releases_lock(self) -> None:
        script = (
            "import sys,time\n"
            "from pathlib import Path\n"
            "from backend.private_knowledge.atomic_ciphertext import exclusive_lock\n"
            "root=Path(sys.argv[1]); ready=Path(sys.argv[2])\n"
            "with exclusive_lock(root,'.authority.lock',error_code='repository_locked'):\n"
            " ready.write_text('ready',encoding='ascii')\n"
            " time.sleep(60)\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            ready = root / "child-ready"
            process = subprocess.Popen(
                [sys.executable, "-B", "-c", script, str(root), str(ready)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 5
                while (not ready.exists() and process.poll() is None
                       and time.monotonic() < deadline):
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "child lock did not start")

                with self.assertRaisesRegex(
                    PrivateKnowledgeError, "repository_locked"
                ):
                    with exclusive_lock(
                        root, ".authority.lock", error_code="repository_locked"
                    ):
                        self.fail("concurrent mutation entered")

                process.kill()
                process.wait(timeout=5)
                with exclusive_lock(
                    root, ".authority.lock", error_code="repository_locked"
                ):
                    pass
                self.assertTrue((root / ".authority.lock").is_file())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
