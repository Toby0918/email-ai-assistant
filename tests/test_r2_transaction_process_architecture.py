"""Physical and capability guards for the dormant transaction root."""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_transaction_process"


class R2TransactionProcessArchitectureTests(unittest.TestCase):
    def test_exact_physical_package_has_no_entry_surface(self):
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "__main__.py",
                "contracts.py",
                "terminal.py",
                "testing.py",
                "bootstrap_v2.py",
                "production_v2.py",
                "_production_v2_canonical.py",
            },
        )

    def test_package_does_not_import_other_roots_or_live_capabilities(self):
        source = "\n".join(
            item.read_text(encoding="utf-8") for item in PACKAGE.glob("*.py")
        )
        imports = {
            node.module
            for item in PACKAGE.glob("*.py")
            for node in ast.walk(ast.parse(item.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertTrue(
            {"backend.r2_preflight_process", "backend.r2_evidence_process"}.isdisjoint(
                imports
            )
        )
        for forbidden in ("open(", "Path(", "os.environ", ".invoke(", "append_"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
