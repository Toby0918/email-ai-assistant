"""Architecture guards for generated Issue #99 runbook semantics."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

import backend.r2_operator_runbook_v2 as package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_operator_runbook_v2"
BINDING = ROOT / "backend" / "r2_production_binding"


class R2OperatorRunbookV2ArchitectureTests(unittest.TestCase):
    def test_exact_files_exports_and_generated_document(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {"__init__.py", "errors.py", "state_machine.py", "render.py", "receipt.py"},
        )
        self.assertIn("catalog.py", {path.name for path in BINDING.glob("*.py")})
        self.assertFalse((PACKAGE / "__main__.py").exists())
        self.assertEqual(
            set(package.__all__),
            {
                "OperatorCommandEffectV2", "OperatorPhaseV2", "OperatorSurfaceV2",
                "R2OperatorCommandV2", "R2OperatorPhaseRuleV2",
                "R2OperatorRunbookReceiptV2", "RunbookVerificationStatusV2",
                "OperatorRunbookError", "command_catalog_v2",
                "executable_verb_map_v2", "operator_package_semantics_fingerprint_v2",
                "operator_state_machine_v2", "render_r2_operator_runbook_v2",
                "resolve_operator_command_v2", "runbook_document_fingerprint_v2",
            },
        )

    def test_package_has_no_executable_host_or_dynamic_document_input(self):
        forbidden_imports = {"os", "pathlib", "shutil", "subprocess", "socket", "sqlite3"}
        forbidden_calls = {"open", "print", "exec", "eval", "compile", "__import__"}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {
                (node.module or "").split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.level == 0
            }
            imports.update(alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
            calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
            self.assertTrue(imports.isdisjoint(forbidden_imports), path.name)
            self.assertTrue(calls.isdisjoint(forbidden_calls), path.name)

    def test_only_three_dispatchers_consume_executable_catalog(self):
        consumers = []
        for path in sorted((ROOT / "backend").rglob("*.py")):
            if path == BINDING / "catalog.py" or PACKAGE in path.parents:
                continue
            if "r2_production_binding.catalog" in path.read_text(encoding="utf-8"):
                consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            consumers,
            [
                "backend/r2_evidence_process/production_v2.py",
                "backend/r2_preflight_process/production_v2.py",
                "backend/r2_transaction_process/production_v2.py",
            ],
        )

    def test_module_and_function_size_limits(self):
        for path in (*PACKAGE.glob("*.py"), BINDING / "catalog.py"):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path.name)
            for node in ast.walk(ast.parse("\n".join(lines))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    self.assertLessEqual(end - node.lineno + 1, 50, f"{path.name}:{node.name}")

    def test_no_frontend_script_workflow_or_normal_runtime_consumer(self):
        consumers = []
        for root_name in ("frontend", "scripts"):
            for path in (ROOT / root_name).rglob("*"):
                if path.is_file() and "r2_operator_runbook_v2" in path.read_text(encoding="utf-8", errors="ignore"):
                    consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
