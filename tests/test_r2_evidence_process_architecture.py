"""Physical package and capability guards for Issue #72."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_evidence_process"


class R2EvidenceProcessArchitectureTests(unittest.TestCase):
    def test_exact_physical_package_is_separate(self) -> None:
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "__main__.py",
                "contracts.py",
                "entry.py",
                "terminal.py",
                "testing.py",
            },
        )
        imports = set()
        for item in PACKAGE.glob("*.py"):
            tree = ast.parse(item.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
        self.assertFalse(
            {
                "backend.r2_preflight_process",
                "backend.cutover_transaction_composition",
                "backend.r2_transaction_process",
                "backend.migration_evidence_verifier",
            }
            & imports
        )

    def test_command_is_one_publish_verb_without_selection_surface(self) -> None:
        contracts = (PACKAGE / "contracts.py").read_text(encoding="utf-8")
        entry = (PACKAGE / "entry.py").read_text(encoding="utf-8")
        source = "\n".join(
            item.read_text(encoding="utf-8")
            for item in PACKAGE.glob("*.py")
        )
        self.assertIn(
            'EVIDENCE_VERBS = {"publish": "evidence_publication"}',
            contracts,
        )
        self.assertIn("argv=tuple(sys.argv[1:])", entry)
        self.assertIn('if argv != ("publish",)', entry)
        for forbidden in (
            "argparse",
            "--target",
            "--source",
            "--profile",
            "--journal",
            "--recovery",
            "--force",
            "os.environ",
            "subprocess",
            "verify_package_in_separate_process",
        ):
            self.assertNotIn(forbidden, source)

    def test_publication_capability_exists_only_in_test_binder(self) -> None:
        source = {
            item.name: item.read_text(encoding="utf-8")
            for item in PACKAGE.glob("*.py")
        }
        for name, value in source.items():
            if name == "testing.py":
                continue
            self.assertNotIn("publish_confirmed_review", value)
            self.assertNotIn("open(", value)
            self.assertNotIn("Path(", value)
        self.assertIn("publish_confirmed_review", source["testing.py"])

    def test_no_normal_consumer_imports_synthetic_process(self) -> None:
        needle = "backend.r2_evidence_process.testing"
        consumers = []
        for root_name in ("backend", "frontend", "scripts", ".github"):
            root = ROOT / root_name
            if not root.exists():
                continue
            for item in root.rglob("*"):
                if not item.is_file() or item.suffix not in {
                    ".py",
                    ".js",
                    ".yml",
                    ".yaml",
                }:
                    continue
                if needle in item.read_text(encoding="utf-8"):
                    consumers.append(item.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
