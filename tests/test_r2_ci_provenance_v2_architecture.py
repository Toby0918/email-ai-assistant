"""Architecture boundary for the fixed Issue #100 adapter."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_ci_provenance_v2"


class R2CiProvenanceV2ArchitectureTests(unittest.TestCase):
    def test_contract_package_has_no_host_or_mutation_capability(self):
        forbidden = {"argparse", "os", "pathlib", "subprocess", "shutil", "socket"}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names
            }
            with self.subTest(path=path.name):
                self.assertTrue(imports.isdisjoint(forbidden))

    def test_entry_scripts_have_fixed_no_argument_surface(self):
        for name in (
            "verify_r2_ci_provenance.py",
            "reconcile_r2_ci_provenance.py",
        ):
            source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertNotIn("argparse", source)
                self.assertNotIn("sys.argv[", source)
                self.assertNotIn("input(", source)
                self.assertNotIn("requests", source)
                self.assertNotIn("urllib", source)


if __name__ == "__main__":
    unittest.main()
