"""Static capability guards for the Issue #78 CRX unit."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import backend.r2_crx_publication as contracts


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_crx_publication"


class R2CrxPublicationArchitectureTests(unittest.TestCase):
    def test_public_surface_is_closed_and_pathless(self) -> None:
        self.assertEqual(
            set(contracts.__all__),
            {
                "CrxCrashGap",
                "CrxFaultSelectorV1",
                "CrxPendingState",
                "CrxPublicationPrerequisiteV1",
                "CrxPublicationReceiptV1",
                "CrxPublicationStatus",
            },
        )
        source = (PACKAGE / "__init__.py").read_text("utf-8")
        self.assertNotIn("testing", source)
        self.assertNotIn("Path", source)

    def test_no_browser_signing_build_install_or_cleanup_capability(self) -> None:
        source = "\n".join(
            path.read_text("utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in (
            "zipfile",
            "webbrowser",
            "browser_profile",
            "winreg",
            "cryptography",
            "private_key",
            "sign(",
            "subprocess",
            "shell=true",
            "shutil",
            "unlink(",
            "remove(",
            "replace(",
            "rmtree",
            "def main(",
            "sys.argv",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_only_fixed_source_handle_capability_is_reused(self) -> None:
        imports = set()
        for path in PACKAGE.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text("utf-8"))):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("backend.")
                ):
                    imports.add(node.module)
        self.assertEqual(
            imports,
            {"backend.r2_database_publication.windows_handle"},
        )

    def test_files_and_functions_remain_bounded(self) -> None:
        for path in PACKAGE.glob("*.py"):
            source = path.read_text("utf-8")
            with self.subTest(path=path.name):
                self.assertLessEqual(len(source.splitlines()), 300)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    with self.subTest(path=path.name, function=node.name):
                        self.assertLessEqual(node.end_lineno - node.lineno + 1, 50)


if __name__ == "__main__":
    unittest.main()
