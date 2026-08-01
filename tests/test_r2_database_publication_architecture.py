"""Static capability guards for the dormant Issue #76 slice."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import backend.r2_database_publication as contracts


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_database_publication"


class R2DatabasePublicationArchitectureTests(unittest.TestCase):
    def test_public_surface_is_closed_and_pathless(self) -> None:
        self.assertEqual(
            set(contracts.__all__),
            {
                "DatabaseCheckpoint",
                "DatabaseCrashGap",
                "DatabaseFaultSelectorV1",
                "DatabaseTransactionResultV1",
                "DatabaseTransactionStatus",
                "LegacyDatabaseCopyLeaseV1",
                "QuiescencePrerequisitesV1",
                "StoppedServiceReceiptV1",
            },
        )
        source = (PACKAGE / "__init__.py").read_text("utf-8")
        self.assertNotIn("testing", source)
        self.assertNotIn("Path", source)

    def test_no_real_entry_cleanup_or_adjacent_runtime_capability(self) -> None:
        source = "\n".join(
            path.read_text("utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in (
            "def main(",
            "sys.argv",
            "subprocess",
            "shell=true",
            "powershell",
            "sqlite3",
            "truncate(",
            "unlink(",
            "remove(",
            "rmtree(",
            "backend.email_agent",
            "backend.mailbox_ingest",
            "backend.cutover_managed_activation",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_source_handle_share_mask_is_read_only(self) -> None:
        source = (PACKAGE / "windows_handle.py").read_text("utf-8")
        self.assertIn("_FILE_SHARE_READ", source)
        self.assertNotIn("_FILE_SHARE_WRITE", source)
        self.assertNotIn("_FILE_SHARE_DELETE", source)
        self.assertIn("CreateFileW", source)
        lease = (PACKAGE / "lease.py").read_text("utf-8")
        self.assertEqual(lease.count("handle.read_all"), 1)
        self.assertEqual(lease.count("handle.hash_all"), 2)

    def test_files_and_functions_remain_bounded(self) -> None:
        for path in PACKAGE.glob("*.py"):
            source = path.read_text("utf-8")
            with self.subTest(path=path.name):
                self.assertLessEqual(len(source.splitlines()), 300)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    with self.subTest(path=path.name, function=node.name):
                        lines = node.end_lineno - node.lineno + 1
                        self.assertLessEqual(lines, 50)


if __name__ == "__main__":
    unittest.main()
