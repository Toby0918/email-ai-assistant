"""Capability and architecture guards for Issue #98 retention."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

import backend.r2_retention_ledger_v2 as package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_retention_ledger_v2"
GRAPH_PACKAGES = (
    "r2_transaction_journal_v2",
    "r2_foundation_publication_v2",
    "r2_managed_unit_publication_v2",
    "r2_two_start_validation_v2",
    "r2_rollback_recovery_v2",
    "r2_retention_ledger_v2",
)


class R2RetentionLedgerV2ArchitectureTests(unittest.TestCase):
    def test_exact_files_exports_and_no_entry(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {"__init__.py", "errors.py", "ledger.py", "proof.py"},
        )
        self.assertFalse((PACKAGE / "__main__.py").exists())
        self.assertEqual(
            set(package.__all__),
            {
                "R2RetentionEntryV2",
                "R2RetentionLedgerV2",
                "R2RetentionProofV2",
                "RetentionLedgerError",
                "RetentionLedgerStageV2",
                "RetentionObjectKindV2",
            },
        )

    def test_production_graph_has_zero_destructive_or_expiry_capability(self):
        forbidden_imports = {
            "os", "pathlib", "sched", "shutil", "sqlite3", "subprocess", "time"
        }
        forbidden_calls = {
            "expire", "prune", "remove", "replace", "rmdir", "rmtree",
            "schedule", "timer", "unlink",
        }
        findings = []
        for name in GRAPH_PACKAGES:
            for path in (ROOT / "backend" / name).glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        findings.extend(alias.name for alias in node.names if alias.name.split(".")[0] in forbidden_imports)
                    elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in forbidden_imports:
                        findings.append(node.module)
                    elif isinstance(node, ast.Call):
                        name_value = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                        if name_value in forbidden_calls:
                            findings.append(name_value)
        self.assertEqual(findings, [])

    def test_retention_package_is_content_free_and_has_no_adjacent_capability(self):
        forbidden = {
            "provider", "mailbox", "vault", "private_data", "credential",
            "filesystem", "network", "cleanup", "callback", "issuer",
        }
        source = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")).lower()
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_module_and_function_size_limits(self):
        for path in PACKAGE.glob("*.py"):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path.name)
            for node in ast.walk(ast.parse("\n".join(lines))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    self.assertLessEqual(end - node.lineno + 1, 50, f"{path.name}:{node.name}")

    def test_no_normal_runtime_or_script_consumer(self):
        consumers = []
        for root_name in ("backend", "frontend", "scripts"):
            for path in (ROOT / root_name).rglob("*.py"):
                if PACKAGE in path.parents:
                    continue
                if "r2_retention_ledger_v2" in path.read_text(encoding="utf-8"):
                    consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            sorted(consumers),
            [
                "backend/r2_operator_runbook_v2/receipt.py",
                "backend/r2_operator_runbook_v2/state_machine.py",
            ],
        )


if __name__ == "__main__":
    unittest.main()
