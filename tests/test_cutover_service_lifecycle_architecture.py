"""Mechanical capability-boundary tests for Issue #58."""

from __future__ import annotations

import ast
import dataclasses
import unittest
from pathlib import Path

from backend.cutover_service_lifecycle import (
    LegacyServiceAdapter,
    NewServiceAdapter,
    ProviderDisabledServiceAdapters,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "cutover_service_lifecycle"
FORBIDDEN_IMPORTS = {
    "asyncio",
    "backend.email_agent",
    "backend.cutover_repository_transaction",
    "ctypes",
    "dotenv",
    "http",
    "logging",
    "os",
    "pathlib",
    "shutil",
    "socket",
    "sqlite3",
    "subprocess",
    "urllib",
}
FORBIDDEN_CALLS = {"eval", "exec", "open", "__import__"}


class ServiceLifecycleArchitectureTests(unittest.TestCase):
    def test_service_adapters_are_exact_fixed_roles(self) -> None:
        self.assertEqual(
            tuple(item.name for item in dataclasses.fields(
                ProviderDisabledServiceAdapters
            )),
            ("new_service", "legacy_service"),
        )
        self.assertEqual(
            tuple(item.name for item in dataclasses.fields(NewServiceAdapter)),
            (
                "start_provider_disabled",
                "read_health",
                "analyze_fixed_synthetic",
                "observe_synthetic_row",
                "stop_exact",
            ),
        )
        self.assertEqual(
            tuple(item.name for item in dataclasses.fields(
                LegacyServiceAdapter
            )),
            (
                "start_provider_disabled_recovery",
                "read_health",
                "stop_exact",
            ),
        )

    def test_package_has_no_host_or_arbitrary_command_capability(self):
        for path in PACKAGE.glob("*.py"):
            with self.subTest(path=path.name):
                tree = ast.parse(path.read_text("utf-8"))
                imports = _imports(tree)
                calls = {
                    node.func.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                }
                self.assertFalse(
                    any(
                        imported == forbidden
                        or imported.startswith(forbidden + ".")
                        for imported in imports
                        for forbidden in FORBIDDEN_IMPORTS
                    ),
                    imports,
                )
                self.assertFalse(calls & FORBIDDEN_CALLS)

    def test_production_modules_stay_bounded(self) -> None:
        oversized = {
            path.name: len(path.read_text("utf-8").splitlines())
            for path in PACKAGE.glob("*.py")
            if len(path.read_text("utf-8").splitlines()) > 300
        }
        self.assertEqual(oversized, {})

    def test_normal_runtime_and_scripts_do_not_import_lifecycle(self):
        consumers = (
            ROOT / "backend" / "email_agent",
            ROOT / "frontend",
            ROOT / "scripts",
        )
        findings = []
        for root in consumers:
            for path in root.rglob("*"):
                if path.suffix in {".py", ".js", ".html"}:
                    text = path.read_text("utf-8")
                    if path.suffix == ".py":
                        imports = _imports(ast.parse(text, filename=str(path)))
                        consumed = any(
                            name == "backend.cutover_service_lifecycle"
                            or name.startswith("backend.cutover_service_lifecycle.")
                            for name in imports
                        )
                    else:
                        consumed = "cutover_service_lifecycle" in text
                    if consumed:
                        findings.append(str(path.relative_to(ROOT)))
        self.assertEqual(findings, [])


def _imports(tree: ast.AST) -> set[str]:
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


if __name__ == "__main__":
    unittest.main()
