"""Issue #51 pure-contract capability and default-lock guards."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import backend.cutover_contracts as contracts
from backend.cutover_contracts import (
    OperatorEntryStatus,
    default_operator_entry,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "cutover_contracts"
EXPECTED_FILES = {
    "__init__.py",
    "_canonical.py",
    "authorization.py",
    "authorization_schema.py",
    "authorization_validation.py",
    "errors.py",
    "operator_entry.py",
    "profile.py",
    "profile_schema.py",
    "receipt.py",
    "receipt_matrix.py",
    "receipt_schema.py",
    "receipt_types.py",
}
EXPECTED_PUBLIC = {
    "AuthorizationValidationResult",
    "AuthorizationValidationStatus",
    "CutoverContractError",
    "CutoverExecutionAuthorizationV1",
    "CutoverProfileV1",
    "EvidencePublicationAuthorizationV1",
    "OperatorEntryCounts",
    "OperatorEntryResult",
    "OperatorEntryStatus",
    "RealPreflightAuthorizationV1",
    "ReceiptEnvelopeV1",
    "ReceiptInputRole",
    "ReceiptOperation",
    "ReceiptProducer",
    "ReceiptStatus",
    "ReceiptSubjectRole",
    "ReceiptType",
    "RecoveryAuthorizationV1",
    "TestSandboxAuthorizationV1",
    "default_operator_entry",
    "validate_real_host_authorization",
}
ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "dataclasses",
    "enum",
    "hashlib",
    "json",
    "typing",
}
ALLOWED_IMPORT_FROM = {
    "__future__": {"annotations"},
    "dataclasses": {"dataclass", "field"},
    "enum": {"Enum"},
    "typing": {"ClassVar"},
}
FORBIDDEN_CALL_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "input",
    "open",
}
FORBIDDEN_CALL_ATTRIBUTES = {
    "connect",
    "getenv",
    "now",
    "run",
    "system",
    "time",
    "utcnow",
    "uuid4",
}
PACKAGE_MODULES = {
    Path(name).stem
    for name in EXPECTED_FILES
}


def _is_allowed_package_import_from(node: ast.ImportFrom) -> bool:
    if node.level == 0:
        allowed_names = ALLOWED_IMPORT_FROM.get(node.module or "", set())
        return all(alias.name in allowed_names for alias in node.names)
    return (
        node.level == 1
        and node.module in PACKAGE_MODULES
        and all(alias.name != "*" for alias in node.names)
    )


def _is_allowed_package_import(node: ast.Import) -> bool:
    return all(alias.name in ALLOWED_IMPORT_ROOTS for alias in node.names)


def _is_forbidden_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in FORBIDDEN_CALL_NAMES
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in FORBIDDEN_CALL_ATTRIBUTES
    return False


def _imports_cutover_contracts(source: str) -> bool:
    if "backend.cutover_contracts" in source:
        return True
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(
                alias.name == "backend.cutover_contracts"
                or alias.name.startswith("backend.cutover_contracts.")
                for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and module == "backend":
                if any(alias.name == "cutover_contracts" for alias in node.names):
                    return True
            elif node.level > 0 and (
                module == "cutover_contracts"
                or module.startswith("cutover_contracts.")
                or any(alias.name == "cutover_contracts" for alias in node.names)
            ):
                return True
    return False


class CutoverContractArchitectureTests(unittest.TestCase):
    def test_package_import_guard_rejects_parent_and_unknown_modules(self) -> None:
        cases = (
            ("from dataclasses import dataclass", True),
            ("from .errors import CutoverContractError", True),
            ("from pathlib import Path", False),
            ("from json.tool import main", False),
            ("from json import tool", False),
            ("from ..container_audit import run_audit", False),
            ("from .unknown_module import capability", False),
        )
        for source, expected in cases:
            node = ast.parse(source).body[0]
            with self.subTest(source=source):
                self.assertEqual(
                    _is_allowed_package_import_from(node),
                    expected,
                )

    def test_package_import_guard_rejects_dotted_absolute_modules(self) -> None:
        cases = (
            ("import json", True),
            ("import hashlib", True),
            ("import json.tool", False),
            ("import typing.io", False),
        )
        for source, expected in cases:
            node = ast.parse(source).body[0]
            with self.subTest(source=source):
                self.assertEqual(_is_allowed_package_import(node), expected)

    def test_call_guard_rejects_stdin_and_host_io(self) -> None:
        cases = (
            ("input()", True),
            ("open('synthetic')", True),
            ("json.dumps({})", False),
        )
        for source, expected in cases:
            node = next(
                item
                for item in ast.walk(ast.parse(source))
                if isinstance(item, ast.Call)
            )
            with self.subTest(source=source):
                self.assertEqual(_is_forbidden_call(node), expected)

    def test_consumer_guard_recognizes_equivalent_python_imports(self) -> None:
        cases = (
            ("import backend.cutover_contracts", True),
            ("import backend.cutover_contracts.profile", True),
            ("from backend.cutover_contracts import CutoverProfileV1", True),
            ("from backend import cutover_contracts", True),
            ("from . import cutover_contracts", True),
            ("from ..cutover_contracts import ReceiptEnvelopeV1", True),
            ("from backend import email_agent", False),
            ("from .errors import CutoverContractError", False),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    _imports_cutover_contracts(source),
                    expected,
                )

    def test_default_operator_entry_is_zero_argument_and_always_blocked(
        self,
    ) -> None:
        self.assertEqual(tuple(inspect.signature(default_operator_entry).parameters), ())

        result = default_operator_entry()

        self.assertIs(
            result.status,
            OperatorEntryStatus.BLOCKED_NO_APPROVED_COMMAND,
        )
        self.assertEqual((result.counts.blocked, result.counts.executed), (1, 0))
        self.assertFalse(hasattr(result, "__dict__"))

    def test_package_files_and_public_surface_are_exact(self) -> None:
        files = {
            path.name
            for path in PACKAGE.iterdir()
            if path.is_file() and path.suffix == ".py"
        }
        self.assertEqual(files, EXPECTED_FILES)
        self.assertEqual(set(contracts.__all__), EXPECTED_PUBLIC)

    def test_package_imports_only_pure_standard_library_values(self) -> None:
        for path in sorted(PACKAGE.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(
                        _is_allowed_package_import(node),
                        (path, ast.unparse(node)),
                    )
                elif isinstance(node, ast.ImportFrom):
                    self.assertTrue(
                        _is_allowed_package_import_from(node),
                        (path, ast.unparse(node)),
                    )

    def test_package_has_no_host_io_or_ambient_authority_calls(self) -> None:
        for path in sorted(PACKAGE.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                self.assertFalse(
                    _is_forbidden_call(node),
                    (path, ast.unparse(node)),
                )

    def test_real_authorization_module_has_no_issuer_or_clock(self) -> None:
        path = PACKAGE / "authorization.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }

        self.assertTrue(
            {"create", "issue", "mint", "generate", "sign"}.isdisjoint(names)
        )
        self.assertTrue(
            {"uuid4", "now", "utcnow", "time", "token_bytes"}.isdisjoint(calls)
        )

    def test_no_runtime_or_operator_surface_consumes_the_package(self) -> None:
        roots = (
            ROOT / "backend",
            ROOT / "scripts",
            ROOT / "frontend",
        )
        violations = []
        for root in roots:
            for path in root.rglob("*"):
                if (
                    not path.is_file()
                    or path.suffix not in {".py", ".js"}
                    or PACKAGE in path.parents
                ):
                    continue
                source = path.read_text(encoding="utf-8")
                imports_contracts = (
                    _imports_cutover_contracts(source)
                    if path.suffix == ".py"
                    else (
                        "backend.cutover_contracts" in source
                        or "backend/cutover_contracts" in source
                    )
                )
                if imports_contracts:
                    violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])

    def test_backend_files_and_functions_remain_bounded(self) -> None:
        for path in sorted(PACKAGE.glob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path)
            tree = ast.parse("\n".join(lines), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = node.end_lineno or node.lineno
                    self.assertLessEqual(end - node.lineno + 1, 50, (path, node.name))


if __name__ == "__main__":
    unittest.main()
