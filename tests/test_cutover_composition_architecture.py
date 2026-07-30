"""Mechanical isolation guards for the three Issue #59 operator roots."""

from __future__ import annotations

import ast
import importlib
import inspect
import unittest
from pathlib import Path

from backend.cutover_composition_contracts import CompositionContractError
from tests.cutover_composition_binders import TestOwnedCompositionScopeV1


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
PACKAGES = {
    "cutover_composition_contracts": {
        "__init__.py",
        "authorization_sequence.py",
        "binding.py",
        "canonical.py",
        "chain.py",
        "errors.py",
        "receipts.py",
    },
    "real_host_preflight_composition": {
        "__init__.py",
        "composition.py",
        "contracts_bridge.py",
        "operator_entry.py",
        "roles.py",
    },
    "migration_evidence_publication_composition": {
        "__init__.py",
        "composition.py",
        "contracts_bridge.py",
        "operator_entry.py",
        "roles.py",
    },
    "cutover_transaction_composition": {
        "__init__.py",
        "composition.py",
        "contracts_bridge.py",
        "operator_entry.py",
        "roles.py",
        "state.py",
    },
}
ROOT_PACKAGES = tuple(name for name in PACKAGES if name != "cutover_composition_contracts")
EXPECTED_EXPORTS = {
    "real_host_preflight_composition": {
        "RealHostPreflightComposition",
        "RealHostPreflightRolesV1",
        "locked_current_topology_entry",
        "locked_evidence_review_entry",
        "locked_evidence_verification_entry",
        "locked_final_audit_readiness_entry",
        "locked_host_baseline_entry",
        "locked_real_host_preflight_composition_constructor",
        "locked_recovery_inspection_entry",
    },
    "migration_evidence_publication_composition": {
        "MigrationEvidencePublicationComposition",
        "MigrationEvidencePublicationRolesV1",
        "locked_evidence_publication_entry",
        "locked_migration_evidence_publication_composition_constructor",
    },
    "cutover_transaction_composition": {
        "CutoverTransactionComposition",
        "CutoverTransactionRolesV1",
        "JournalOwnerV1",
        "locked_cutover_transaction_composition_constructor",
        "locked_execute_entry",
        "locked_resume_entry",
        "locked_rollback_entry",
    },
}
FORBIDDEN_STDLIB = {
    "ctypes",
    "importlib",
    "logging",
    "os",
    "pathlib",
    "shutil",
    "socket",
    "sqlite3",
    "subprocess",
}
FORBIDDEN_PUBLIC_PARAMETERS = {
    "source",
    "target",
    "worktree",
    "database",
    "runtime",
    "artifact",
    "config",
    "acl",
    "rollback",
    "shell",
    "powershell",
    "git",
    "git_command",
    "command",
}
FORBIDDEN_PREFLIGHT_IMPORTS = {
    "backend.cutover_host_mutation",
    "backend.cutover_managed_activation",
    "backend.cutover_repository_transaction",
    "backend.cutover_service_lifecycle",
}
CONSUMER_ROOTS = (
    REPOSITORY_ROOT / "frontend",
    REPOSITORY_ROOT / "scripts",
    REPOSITORY_ROOT / ".github",
    BACKEND_ROOT / "email_agent",
)


class CutoverCompositionArchitectureTests(unittest.TestCase):
    def test_package_files_are_exact(self) -> None:
        for package, expected in PACKAGES.items():
            with self.subTest(package=package):
                actual = {
                    path.name
                    for path in (BACKEND_ROOT / package).glob("*.py")
                }
                self.assertEqual(actual, expected)

    def test_root_public_exports_are_exact(self) -> None:
        for package, expected in EXPECTED_EXPORTS.items():
            module = importlib.import_module(f"backend.{package}")
            with self.subTest(package=package):
                self.assertEqual(set(module.__all__), expected)

    def test_roots_are_mutually_isolated_and_capability_free(self) -> None:
        root_imports = {
            f"backend.{name}" for name in ROOT_PACKAGES
        }
        for package in ROOT_PACKAGES:
            other_roots = root_imports - {f"backend.{package}"}
            for path in sorted((BACKEND_ROOT / package).glob("*.py")):
                imports = _imports(path)
                with self.subTest(path=path.name):
                    self.assertFalse(imports & other_roots)
                    self.assertFalse(imports & FORBIDDEN_STDLIB)
                    if package == "real_host_preflight_composition":
                        self.assertFalse(
                            imports & FORBIDDEN_PREFLIGHT_IMPORTS
                        )

    def test_compositions_have_no_dynamic_capability_lookup(self) -> None:
        for package in ROOT_PACKAGES:
            path = BACKEND_ROOT / package / "composition.py"
            tree = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
            )
            calls = _called_names(tree)
            with self.subTest(package=package):
                self.assertFalse(
                    calls
                    & {
                        "__import__",
                        "eval",
                        "exec",
                        "getattr",
                        "import_module",
                        "setattr",
                    }
                )

    def test_executable_sandbox_assembly_exists_only_in_tests(self) -> None:
        for package in ROOT_PACKAGES:
            path = BACKEND_ROOT / package / "composition.py"
            tree = ast.parse(path.read_text(encoding="utf-8"))
            functions = {
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
            with self.subTest(package=package):
                self.assertFalse(
                    {
                        name
                        for name in functions
                        if name.startswith("_bind_test_sandbox")
                    }
                )

    def test_import_and_dynamic_lookup_guards_detect_equivalent_syntax(
        self,
    ) -> None:
        package = "backend.real_host_preflight_composition"
        tree = ast.parse(
            "from ..cutover_transaction_composition import "
            "CutoverTransactionComposition\n"
            "from backend import migration_evidence_publication_composition\n"
            "builtins.getattr(value, 'capability')\n"
        )

        imports = _imports_from_tree(tree, package)

        self.assertIn(
            "backend.cutover_transaction_composition",
            imports,
        )
        self.assertIn(
            "backend.migration_evidence_publication_composition",
            imports,
        )
        self.assertIn("getattr", _called_names(tree))

    def test_test_only_scope_cannot_select_or_outlive_its_owned_root(
        self,
    ) -> None:
        with self.assertRaises(TypeError):
            TestOwnedCompositionScopeV1.create(root=Path("D:/outside"))
        scope = TestOwnedCompositionScopeV1.create()
        scope.require_active()
        scope.close()
        with self.assertRaisesRegex(
            CompositionContractError,
            "^TEST_COMPOSITION_SCOPE_INVALID$",
        ):
            scope.require_active()

    def test_product_and_automation_consumers_cannot_import_roots(self) -> None:
        needles = tuple(
            f"backend.{package}" for package in ROOT_PACKAGES
        )
        offenders: list[str] = []
        for root in CONSUMER_ROOTS:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                if path.suffix not in {".py", ".js", ".json", ".yml", ".yaml"}:
                    continue
                if path.suffix == ".py":
                    consumes = bool(
                        _python_import_references(path) & set(needles)
                    )
                else:
                    text = path.read_text(encoding="utf-8")
                    consumes = any(needle in text for needle in needles)
                if consumes:
                    offenders.append(path.relative_to(REPOSITORY_ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_public_entry_signatures_have_no_arbitrary_inputs(self) -> None:
        for package in ROOT_PACKAGES:
            module = importlib.import_module(f"backend.{package}")
            for name in module.__all__:
                value = getattr(module, name)
                if not inspect.isfunction(value):
                    continue
                parameters = set(inspect.signature(value).parameters)
                kinds = {
                    parameter.kind
                    for parameter in inspect.signature(value).parameters.values()
                }
                with self.subTest(package=package, export=name):
                    self.assertFalse(
                        parameters & FORBIDDEN_PUBLIC_PARAMETERS
                    )
                    self.assertNotIn(
                        inspect.Parameter.VAR_POSITIONAL,
                        kinds,
                    )
                    self.assertNotIn(
                        inspect.Parameter.VAR_KEYWORD,
                        kinds,
                    )


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _imports_from_tree(tree, f"backend.{path.parent.name}")


def _imports_from_tree(tree: ast.AST, package: str) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative = "." * node.level + (node.module or "")
                imports.add(importlib.util.resolve_name(relative, package))
            elif node.module:
                imports.add(node.module)
            base = (
                importlib.util.resolve_name(
                    "." * node.level + (node.module or ""),
                    package,
                )
                if node.level
                else node.module
            )
            if base:
                imports.update(
                    f"{base}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
    return imports


def _called_names(tree: ast.AST) -> set[str]:
    return {
        (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }


def _python_import_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    references = _imports(path)
    dynamic_names = {"__import__", "import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            dynamic_names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "import_module"
            )
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        first = node.args[0]
        if (
            name in dynamic_names
            and isinstance(first, ast.Constant)
            and type(first.value) is str
        ):
            references.add(first.value)
    return references


if __name__ == "__main__":
    unittest.main()
