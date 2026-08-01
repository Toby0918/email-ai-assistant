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
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "print",
    "setattr",
    "vars",
}
FORBIDDEN_LOAD_NAMES = FORBIDDEN_CALL_NAMES | {"__builtins__"}
FORBIDDEN_CALL_ATTRIBUTES = {
    "connect",
    "getenv",
    "now",
    "run",
    "system",
    "time",
    "token_bytes",
    "utcnow",
    "uuid4",
}
FORBIDDEN_ISSUER_NAMES = {"generate", "issue", "mint", "sign"}
ALLOWED_CREATE_FUNCTIONS = {
    ("profile.py", "CutoverProfileV1.create"),
    ("receipt.py", "ReceiptEnvelopeV1.create"),
    (
        "authorization_validation.py",
        "TestSandboxAuthorizationV1.create",
    ),
}
PACKAGE_MODULES = {
    Path(name).stem
    for name in EXPECTED_FILES
}
ALLOWED_CONSUMERS = {
    "backend/cutover_composition_contracts/approved_binding.py": {
        "CutoverProfileV1",
    },
    "backend/cutover_composition_contracts/authorization_sequence.py": {
        "AuthorizationValidationStatus",
        "CutoverExecutionAuthorizationV1",
        "CutoverProfileV1",
        "EvidencePublicationAuthorizationV1",
        "RealPreflightAuthorizationV1",
        "RecoveryAuthorizationV1",
        "TestSandboxAuthorizationV1",
        "validate_real_host_authorization",
    },
    "backend/cutover_composition_contracts/binding.py": {
        "AuthorizationValidationStatus",
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
        "validate_real_host_authorization",
    },
    "backend/real_host_preflight_composition/contracts_bridge.py": {
        "RealPreflightAuthorizationV1",
    },
    "backend/migration_evidence_publication_composition/contracts_bridge.py": {
        "EvidencePublicationAuthorizationV1",
    },
    "backend/cutover_transaction_composition/contracts_bridge.py": {
        "CutoverExecutionAuthorizationV1",
        "RecoveryAuthorizationV1",
    },
    "backend/cutover_host_mutation/operator_entry.py": {
        "AuthorizationValidationStatus",
        "CutoverExecutionAuthorizationV1",
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
        "validate_real_host_authorization",
    },
    "backend/cutover_host_mutation/windows_acl_factory.py": {
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_host_mutation/windows_directory_factory.py": {
        "CutoverProfileV1",
    },
    "backend/cutover_host_mutation/windows_filesystem_common.py": {
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_journal/contracts_bridge.py": {
        "AuthorizationValidationStatus",
        "CutoverExecutionAuthorizationV1",
        "CutoverProfileV1",
        "RecoveryAuthorizationV1",
        "validate_real_host_authorization",
    },
    "backend/cutover_repository_transaction/scope_models.py": {
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_repository_transaction/synthetic_scope.py": {
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_managed_activation/real_lock.py": {
        "AuthorizationValidationStatus",
        "CutoverExecutionAuthorizationV1",
        "TestSandboxAuthorizationV1",
        "validate_real_host_authorization",
    },
    "backend/cutover_managed_activation/scope_models.py": {
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_managed_activation/synthetic_scope.py": {
        "CutoverProfileV1",
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_service_lifecycle/rollback_validation.py": {
        "TestSandboxAuthorizationV1",
    },
    "backend/cutover_service_lifecycle/real_lock.py": {
        "AuthorizationValidationStatus",
        "CutoverExecutionAuthorizationV1",
        "CutoverProfileV1",
        "RecoveryAuthorizationV1",
        "TestSandboxAuthorizationV1",
        "validate_real_host_authorization",
    },
    "backend/real_host_preflight/contracts_bridge.py": {
        "AuthorizationValidationStatus",
        "CutoverProfileV1",
        "RealPreflightAuthorizationV1",
        "ReceiptEnvelopeV1",
        "TestSandboxAuthorizationV1",
        "default_operator_entry",
        "validate_real_host_authorization",
    },
    "backend/migration_evidence_publication/contracts_bridge.py": {
        "AuthorizationValidationStatus",
        "CutoverProfileV1",
        "EvidencePublicationAuthorizationV1",
        "RealPreflightAuthorizationV1",
        "TestSandboxAuthorizationV1",
        "validate_real_host_authorization",
    },
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


def _contains_forbidden_load(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in FORBIDDEN_LOAD_NAMES
        for node in ast.walk(tree)
    )


def _is_allowed_package_relative_path(relative_path: str) -> bool:
    return relative_path in EXPECTED_FILES


def _package_python_paths() -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in PACKAGE.rglob("*.py")
            if "__pycache__" not in path.relative_to(PACKAGE).parts
        )
    )


def _dynamic_import_aliases(tree: ast.AST) -> set[str]:
    aliases = {"__import__", "import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "import_module"
            )
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                continue
            value = node.value
            is_dynamic = (
                isinstance(value, ast.Name) and value.id in aliases
            ) or (
                isinstance(value, ast.Attribute)
                and value.attr == "import_module"
            )
            if not is_dynamic:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases


def _imports_cutover_contracts(source: str) -> bool:
    if "backend.cutover_contracts" in source:
        return True
    tree = ast.parse(source)
    for node in ast.walk(tree):
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
    dynamic_aliases = _dynamic_import_aliases(tree)
    dynamic_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in dynamic_aliases
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        )
    ]
    if dynamic_calls:
        return True
    return False


def _qualified_function_names(
    nodes: list[ast.stmt],
    owners: tuple[str, ...] = (),
) -> set[str]:
    result: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            result.update(_qualified_function_names(node.body, (*owners, node.name)))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = ".".join((*owners, node.name))
            result.add(qualified)
            result.update(
                _qualified_function_names(node.body, (*owners, node.name))
            )
    return result


def _forbidden_issuer_functions(
    tree: ast.Module,
    filename: str,
) -> set[str]:
    result: set[str] = set()
    for qualified in _qualified_function_names(tree.body):
        name = qualified.rsplit(".", 1)[-1]
        if name in FORBIDDEN_ISSUER_NAMES:
            result.add(qualified)
        elif name == "create" and (
            filename,
            qualified,
        ) not in ALLOWED_CREATE_FUNCTIONS:
            result.add(qualified)
    return result


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

    def test_package_file_guard_rejects_nested_and_non_python_payloads(
        self,
    ) -> None:
        cases = (
            ("authorization.py", True),
            ("host/adapter.py", False),
            ("payload.exe", False),
            ("payload.pyc", False),
            ("nested/payload.ps1", False),
        )
        for relative_path, expected in cases:
            with self.subTest(relative_path=relative_path):
                self.assertEqual(
                    _is_allowed_package_relative_path(relative_path),
                    expected,
                )

    def test_call_guard_rejects_stdin_and_host_io(self) -> None:
        cases = (
            ("input()", True),
            ("open('synthetic')", True),
            ("breakpoint()", True),
            ("delattr(object(), 'synthetic')", True),
            ("setattr(object(), 'synthetic', None)", True),
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

    def test_load_guard_rejects_aliased_builtins_and_dynamic_access(self) -> None:
        cases = (
            ("reader = open", True),
            ("loader = __import__", True),
            ("debugger = breakpoint", True),
            ("deleter = delattr", True),
            ("writer = setattr", True),
            ("lookup = getattr", True),
            ("scope = globals", True),
            ("serializer = json.dumps", False),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    _contains_forbidden_load(ast.parse(source)),
                    expected,
                )

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
            (
                "import importlib\n"
                "importlib.import_module('backend.' + 'cutover_contracts')",
                True,
            ),
            (
                "from importlib import import_module as loader\n"
                "loader('backend.' + 'cutover_contracts')",
                True,
            ),
            (
                "loader = __import__\n"
                "module_name = 'backend.' + 'cutover_contracts'\n"
                "loader(module_name)",
                True,
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    _imports_cutover_contracts(source),
                    expected,
                )

    def test_issuer_guard_is_package_wide_and_create_is_allowlisted(self) -> None:
        cases = (
            (
                "profile.py",
                "class CutoverProfileV1:\n"
                "    def create(self):\n"
                "        return None\n",
                set(),
            ),
            (
                "authorization_validation.py",
                "def mint():\n"
                "    return None\n",
                {"mint"},
            ),
            (
                "host/issuer.py",
                "class HostIssuer:\n"
                "    def sign(self):\n"
                "        return None\n",
                {"HostIssuer.sign"},
            ),
            (
                "helper.py",
                "def create():\n"
                "    return None\n",
                {"create"},
            ),
        )
        for filename, source, expected in cases:
            with self.subTest(filename=filename):
                self.assertEqual(
                    _forbidden_issuer_functions(ast.parse(source), filename),
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
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.relative_to(PACKAGE).parts
        }
        self.assertEqual(files, EXPECTED_FILES)
        self.assertEqual(set(contracts.__all__), EXPECTED_PUBLIC)

    def test_package_imports_only_pure_standard_library_values(self) -> None:
        for path in _package_python_paths():
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
        for path in _package_python_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            self.assertFalse(_contains_forbidden_load(tree), path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                self.assertFalse(
                    _is_forbidden_call(node),
                    (path, ast.unparse(node)),
                )

    def test_package_has_no_real_authorization_issuer(self) -> None:
        violations = {}
        for path in _package_python_paths():
            relative = path.relative_to(PACKAGE).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            findings = _forbidden_issuer_functions(tree, relative)
            if findings:
                violations[relative] = findings
        self.assertEqual(violations, {})

    def test_only_exact_reviewed_bridges_consume_the_package(self) -> None:
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
                relative = path.relative_to(ROOT).as_posix()
                imports_contracts = (
                    _imports_cutover_contracts(source)
                    if path.suffix == ".py"
                    else (
                        "backend.cutover_contracts" in source
                        or "backend/cutover_contracts" in source
                    )
                )
                if imports_contracts:
                    violations.append(relative)
        self.assertEqual(sorted(violations), sorted(ALLOWED_CONSUMERS))

        for relative, expected_symbols in ALLOWED_CONSUMERS.items():
            bridge = ROOT / relative
            tree = ast.parse(bridge.read_text(encoding="utf-8"))
            imports = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == "backend.cutover_contracts"
            ]
            with self.subTest(bridge=relative):
                self.assertEqual(len(imports), 1)
                self.assertEqual(
                    {alias.name for alias in imports[0].names},
                    expected_symbols,
                )

    def test_backend_files_and_functions_remain_bounded(self) -> None:
        for path in _package_python_paths():
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path)
            tree = ast.parse("\n".join(lines), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = node.end_lineno or node.lineno
                    self.assertLessEqual(end - node.lineno + 1, 50, (path, node.name))


if __name__ == "__main__":
    unittest.main()
