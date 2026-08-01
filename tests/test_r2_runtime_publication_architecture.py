"""Static architecture guards for the independent Issue #77 Runtime unit."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import backend.r2_runtime_publication as contracts


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_runtime_publication"


class R2RuntimePublicationArchitectureTests(unittest.TestCase):
    def test_public_surface_is_closed_and_pathless(self) -> None:
        self.assertEqual(
            set(contracts.__all__),
            {
                "PYTHON_VERSION",
                "SQLITE_VERSION",
                "RuntimeCrashGap",
                "RuntimeFaultSelectorV1",
                "RuntimePendingClassification",
                "RuntimePublicationPrerequisiteV1",
                "RuntimePublicationReceiptV1",
                "RuntimePublicationStatus",
                "RuntimeVerificationAuthority",
            },
        )
        root = (PACKAGE / "__init__.py").read_text("utf-8")
        self.assertNotIn("testing", root)
        self.assertNotIn("Path", root)

    def test_no_second_authority_or_forbidden_runtime_surface(self) -> None:
        source = "\n".join(
            path.read_text("utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in (
            "pip check",
            "pip_check",
            "urllib",
            "requests",
            "socket",
            "systempython",
            "usersite",
            "site-packages from",
            "retry",
            "rmtree",
            "unlink(",
            "replace(",
            "def main(",
            "sys.argv",
            "shell=true",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_only_reviewed_managed_runtime_modules_are_reused(self) -> None:
        allowed = {
            "backend.cutover_managed_activation.runtime_capture",
            "backend.cutover_managed_activation.runtime_execution",
            "backend.cutover_managed_activation.runtime_policy",
            "backend.cutover_managed_activation.runtime_tree",
            "backend.cutover_managed_activation.runtime_verification",
        }
        observed = set()
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text("utf-8"))
            observed.update(
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("backend.cutover_managed_activation")
            )
        self.assertTrue(observed)
        self.assertTrue(observed <= allowed)

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
