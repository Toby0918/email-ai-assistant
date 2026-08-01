"""Capability and isolation guards for the Issue #74 tracer."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_main_publication"


class R2MainPublicationArchitectureTests(unittest.TestCase):
    def test_native_writer_has_only_dacl_mutation_capability(self) -> None:
        source = (PACKAGE / "windows_dacl.py").read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertNotIn("sacl_security_information", lowered)
        self.assertNotIn("setnamedsecurityinfo", lowered)
        self.assertNotIn("treesetnamedsecurityinfo", lowered)
        tree = ast.parse(source)
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "SetSecurityInfo"
        ]
        self.assertEqual(len(calls), 1)
        self.assertTrue(
            all(
                isinstance(calls[0].args[index], ast.Constant)
                and calls[0].args[index].value is None
                for index in (3, 4, 6)
            )
        )

    def test_tracer_has_no_delete_copy_replace_or_real_entry_surface(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in (
            "shutil",
            "copyfile",
            "copytree",
            "rmtree",
            "unlink(",
            "replace(",
            "subprocess",
            "powershell",
            "cmd.exe",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)
        self.assertNotIn("def main(", source)
        self.assertNotIn("sys.argv", source)

    def test_real_operator_roots_do_not_import_the_synthetic_tracer(self) -> None:
        for package in (
            "r2_preflight_process",
            "r2_evidence_process",
            "r2_transaction_process",
        ):
            source = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (ROOT / "backend" / package).glob("*.py")
            )
            self.assertNotIn("r2_main_publication", source)


if __name__ == "__main__":
    unittest.main()
