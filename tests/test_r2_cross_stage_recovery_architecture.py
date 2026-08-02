"""Read-only restart and no-cleanup recovery guards for Issue #82."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_cross_stage_recovery"


class R2CrossStageRecoveryArchitectureTests(unittest.TestCase):
    def test_exact_dormant_package_and_cross_stage_contract_dependencies(self):
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "adapters.py",
                "contracts.py",
                "receipt_links.py",
                "state_machine.py",
            },
        )
        source = "\n".join(
            item.read_text(encoding="utf-8") for item in PACKAGE.glob("*.py")
        )
        self.assertIn("r2_validation_lifecycle", source)
        self.assertIn("r2_independent_audits", source)

    def test_restart_inspection_has_no_mutation_or_repeat_capability(self):
        source = (PACKAGE / "state_machine.py").read_text(encoding="utf-8")
        inspect_source = source[
            source.index("    def inspect(") : source.index("    def recover(")
        ]
        self.assertIn("self._inspect_pending()", inspect_source)
        for forbidden in (
            "reverse_boundary",
            "append_cutover_success",
            "authority_factory",
            "retry",
            "repeat",
        ):
            self.assertNotIn(forbidden, inspect_source)

    def test_package_has_no_host_cleanup_or_arbitrary_capability(self):
        source = "\n".join(
            item.read_text(encoding="utf-8") for item in PACKAGE.glob("*.py")
        ).lower()
        for forbidden in (
            "subprocess",
            "sqlite3",
            "pathlib",
            "shutil",
            "open(",
            "os.environ",
            "remove(",
            "unlink",
            "rmtree",
            "cleanup(",
            "replace(",
            "mailbox",
            "provider",
            "private_knowledge",
            "migration_evidence",
            "__main__",
            "argparse",
        ):
            self.assertNotIn(forbidden, source)

    def test_production_modules_and_functions_stay_bounded(self):
        for item in PACKAGE.glob("*.py"):
            source = item.read_text(encoding="utf-8")
            self.assertLessEqual(len(source.splitlines()), 300, item.name)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertLessEqual(
                        node.end_lineno - node.lineno + 1, 50, node.name
                    )


if __name__ == "__main__":
    unittest.main()
