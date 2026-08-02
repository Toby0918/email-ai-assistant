"""Architecture and real-entry locks for Issue #81."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_validation_lifecycle"


class R2ValidationLifecycleArchitectureTests(unittest.TestCase):
    def test_exact_dormant_package_and_approved_slice_dependencies(self):
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {"__init__.py", "adapters.py", "contracts.py", "lifecycle.py"},
        )
        source = "\n".join(
            item.read_text(encoding="utf-8") for item in PACKAGE.glob("*.py")
        )
        for required in (
            "r2_evidence_process",
            "r2_repository_manifest",
            "r2_runtime_publication",
            "r2_crx_publication",
            "r2_config_publication",
            "r2_database_publication",
            "r2_independent_audits",
            "cutover_service_lifecycle",
        ):
            self.assertIn(required, source)

    def test_no_host_provider_private_or_executable_capability(self):
        source = "\n".join(
            item.read_text(encoding="utf-8") for item in PACKAGE.glob("*.py")
        ).lower()
        for forbidden in (
            "subprocess",
            "socket",
            "pathlib",
            "sqlite3",
            "open(",
            "os.environ",
            "dotenv",
            "openai",
            "deepseek",
            "mailbox_ingest",
            "private_knowledge",
            "migration_evidence",
            "__main__",
            "argparse",
            "powershell",
            "cleanup",
            "delete",
        ):
            self.assertNotIn(forbidden, source)

    def test_normal_runtime_has_no_validation_lifecycle_consumer(self):
        needle = "backend.r2_validation_lifecycle"
        approved_recovery = ROOT / "backend" / "r2_cross_stage_recovery"
        approved_verifier = ROOT / "scripts" / "r2_synthetic_topology_support.py"
        approved_matrix = {
            ROOT / "scripts" / "r2_semantic_gap_support.py",
            ROOT / "scripts" / "r2_semantic_owning_effects.py",
        }
        consumers = []
        for root_name in ("backend", "frontend", "scripts", ".github"):
            root = ROOT / root_name
            for item in root.rglob("*") if root.exists() else ():
                if (
                    item.is_file()
                    and item.suffix in {".py", ".js", ".yml", ".yaml"}
                    and PACKAGE not in item.parents
                    and approved_recovery not in item.parents
                    and item != approved_verifier
                    and item not in approved_matrix
                    and needle in item.read_text(encoding="utf-8")
                ):
                    consumers.append(item.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])

    def test_functions_and_modules_are_bounded(self) -> None:
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
