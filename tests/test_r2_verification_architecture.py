"""Synthetic verifier isolation, fixed script, and documentation gates."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_verification_evidence"
SCRIPT = ROOT / "scripts" / "verify_r2_synthetic_topology.py"


class R2VerificationArchitectureTests(unittest.TestCase):
    def test_pure_evidence_package_and_fixed_no_argument_script_exist(self):
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {"__init__.py", "contracts.py", "matrix.py"},
        )
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("len(sys.argv) != 1", source)
        self.assertNotIn("argparse", source)
        self.assertNotIn("--path", source)
        self.assertNotIn("--force", source)

    def test_normal_runtime_frontend_and_workflows_do_not_import_verifier(self):
        needle = "r2_verification_evidence"
        consumers = []
        for root_name in ("backend", "frontend", ".github"):
            root = ROOT / root_name
            for item in root.rglob("*") if root.exists() else ():
                if (
                    item.is_file()
                    and item.suffix in {".py", ".js", ".yml", ".yaml"}
                    and PACKAGE not in item.parents
                    and needle in item.read_text(encoding="utf-8")
                ):
                    consumers.append(item.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])

    def test_new_markdown_has_required_front_matter(self):
        criteria = (
            ROOT / "docs" / "operations" / "r2_synthetic_verification_criteria.md"
        ).read_text(encoding="utf-8")
        self.assertTrue(criteria.startswith("---\n"))
        for field in ("last_update:", "status:", "owner:", "review_cycle:", "source_type:"):
            self.assertIn(field, criteria.split("---", 2)[1])


if __name__ == "__main__":
    unittest.main()
