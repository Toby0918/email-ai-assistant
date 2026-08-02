"""Mechanical capability-boundary tests for Issue #58."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import unittest
from pathlib import Path

import backend.cutover_service_lifecycle as lifecycle_package
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
EXPECTED_PUBLIC = {
    "ActivationFailureKind",
    "CommittedRollbackPlanV1",
    "FailedContainerPublicationReceiptV1",
    "JournalDrivenRollbackAdapter",
    "LegacyPrerequisiteEvidenceV1",
    "LegacyRecoveryConfigV1",
    "LegacyServiceAdapter",
    "LifecycleConstructorResult",
    "LifecycleConstructorStatus",
    "LifecycleResultV1",
    "LifecycleStatus",
    "NewServiceActivationReceiptV1",
    "NewServiceAdapter",
    "NewServiceStartRequestV1",
    "ProviderDisabledLifecycleTransaction",
    "ProviderDisabledServiceAdapters",
    "ProviderDisabledServiceController",
    "RollbackRestoreEvidenceV1",
    "RollbackStage",
    "RollbackStageEvidenceV1",
    "ServiceBoundaryFailure",
    "ServiceHealthEvidenceV1",
    "ServiceLifecycleError",
    "ServiceRole",
    "ServiceStartEvidenceV1",
    "ServiceStopEvidenceV1",
    "SyntheticActivationEvidenceV1",
    "SyntheticActivationRequestV1",
    "SyntheticRowEvidenceV1",
    "locked_real_service_lifecycle_constructor",
}
EXPECTED_IMPORTS = {
    "__init__.py": {
        ".activation_contracts", ".adapters", ".contracts", ".controller",
        ".errors", ".failures", ".lifecycle", ".real_lock",
        ".rollback_adapters", ".rollback_contracts",
    },
    "activation_contracts.py": {
        "__future__", "dataclasses", ".canonical",
    },
    "activation_validation.py": {
        "__future__", "uuid", "backend.cutover_managed_activation",
        ".activation_contracts", ".canonical", ".failures",
    },
    "adapters.py": {"__future__", "dataclasses", "typing"},
    "canonical.py": {
        "__future__", "hashlib", "json", "re", "uuid", ".errors",
    },
    "contracts.py": {
        "__future__", "dataclasses", "enum", ".canonical",
    },
    "controller.py": {
        "__future__", ".activation_contracts", ".activation_validation",
        ".adapters", ".canonical", ".contracts", ".failures",
        ".legacy_contracts", ".legacy_recovery",
    },
    "errors.py": set(),
    "failures.py": {"__future__", "enum", ".errors"},
    "legacy_contracts.py": {
        "__future__", "dataclasses", ".canonical", ".contracts",
        ".rollback_contracts",
    },
    "legacy_recovery.py": {
        "__future__", "uuid", ".canonical", ".contracts",
        ".legacy_contracts", ".rollback_contracts",
    },
    "lifecycle.py": {
        "__future__", "dataclasses", "enum",
        "backend.cutover_managed_activation", ".canonical", ".controller",
        ".failures", ".lifecycle_binding", ".rollback_contracts",
        ".rollback_validation",
    },
    "lifecycle_binding.py": {
        "__future__", "backend.cutover_managed_activation", ".canonical",
        ".controller", ".rollback_adapters", ".rollback_contracts",
    },
    "real_lock.py": {
        "__future__", "dataclasses", "enum", "backend.cutover_contracts",
        ".canonical",
    },
    "rollback_adapters.py": {"__future__", "dataclasses", "typing"},
    "rollback_contracts.py": {
        "__future__", "dataclasses", "enum", ".canonical",
    },
    "rollback_validation.py": {
        "__future__", "backend.cutover_contracts", ".canonical",
        ".rollback_contracts",
    },
}
EXPECTED_FROM_SYMBOL_DIGESTS = {
    "__init__.py": "002448276d31b65f3c3591f4b8b84e34bee84ce48c36422eda5a3ce791c3c9b6",
    "activation_contracts.py": "97cbaa37b1b5b552595dc3f5bf089cee583179ce85faff865fd7e910eaa45890",
    "activation_validation.py": "e18e6962d3c90450f5548adbe93a69600246893416cfba0cefae50c1cfb3c7fa",
    "adapters.py": "925fd593095b57be0ef4107088ce1dc9572c957e3422ef241385acaa81cb476b",
    "canonical.py": "be97fef6f996f2576ca22a16703eb343024097e86ea13d620b115570ae17c2fe",
    "contracts.py": "62e39e9bfad31b3c3fbab940916f9f48a686c298a5f89c9e2c4e5df187f6ae26",
    "controller.py": "1ea7fc45c7f0331410a8c65d146ae5fe1eb8228828fa4e514cdedd00dea0ffcf",
    "errors.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "failures.py": "ae45eb002afa65854d0de631dbd187cca801a8386b3cde832ee14a3a6fa2dff6",
    "legacy_contracts.py": "e58909a50271c80a0ad86b851cae8211c3322a6edbfbb5ff25511fe2f24360e2",
    "legacy_recovery.py": "d2de5bf62099d465ec7ec06b3e302c125fff42da1bf9d8ec59882771ff716999",
    "lifecycle.py": "28d49f5524bad6731de10d81a8a96160ab8e4312f4aed7fd8595493437e27579",
    "lifecycle_binding.py": "21d0428022148246b2edb993e320c7fe352988c44802fc04f1750b2faaf36f03",
    "real_lock.py": "1d6f0afbdc563d3ea9d26e12046e757399d6788efd53f2c9d673f0e451dd0598",
    "rollback_adapters.py": "925fd593095b57be0ef4107088ce1dc9572c957e3422ef241385acaa81cb476b",
    "rollback_contracts.py": "21d6bb3b340db8347525b0f99b905a8012a7688281ef6f142c7c7fd140ea13d3",
    "rollback_validation.py": "ad7b1a7b5f29e05679d99d831eb1832504887d4be85ad4cd6bdb8b52eb872f87",
}


class ServiceLifecycleArchitectureTests(unittest.TestCase):
    def test_public_exports_and_imports_are_exact(self) -> None:
        self.assertEqual(set(lifecycle_package.__all__), EXPECTED_PUBLIC)
        observed = {}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text("utf-8"), filename=str(path))
            observed[path.name] = _exact_imports(tree)
        self.assertEqual(observed, EXPECTED_IMPORTS)
        self.assertEqual(
            {
                path.name: _from_symbol_digest(
                    ast.parse(path.read_text("utf-8"), filename=str(path))
                )
                for path in PACKAGE.glob("*.py")
            },
            EXPECTED_FROM_SYMBOL_DIGESTS,
        )

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

    def test_every_non_test_consumer_is_rejected(self):
        consumers = (ROOT / "backend", ROOT / "frontend", ROOT / "scripts")
        approved_composition = ROOT / "backend" / "r2_validation_lifecycle"
        findings = []
        for root in consumers:
            for path in root.rglob("*"):
                if PACKAGE in path.parents or path == PACKAGE:
                    continue
                if approved_composition in path.parents:
                    continue
                if path.suffix in {".py", ".js", ".html"}:
                    text = path.read_text("utf-8")
                    if path.suffix == ".py":
                        tree = ast.parse(text, filename=str(path))
                        consumed = _imports_lifecycle(tree)
                    else:
                        consumed = "cutover_service_lifecycle" in text
                    if consumed:
                        findings.append(str(path.relative_to(ROOT)))
        for path in (ROOT / ".github" / "workflows").glob("*.y*ml"):
            if "cutover_service_lifecycle" in path.read_text("utf-8"):
                findings.append(str(path.relative_to(ROOT)))
        self.assertEqual(findings, [])

    def test_import_guards_cover_nested_alias_and_rebinding_forms(self):
        nested = ast.parse("def load_value():\n    import random\n")
        self.assertEqual(_exact_imports(nested), {"random"})
        for source in (
            "from importlib import import_module as load\nload(target)\n",
            "import importlib\nload = importlib.import_module\nload(target)\n",
            "alias = __import__\nalias(target)\n",
        ):
            with self.subTest(source=source):
                self.assertTrue(_imports_lifecycle(ast.parse(source)))
        allowed = ast.parse(
            "from backend.cutover_managed_activation "
            "import ManagedActivationReceiptSetV1\n"
        )
        expanded = ast.parse(
            "from backend.cutover_managed_activation import "
            "ManagedActivationReceiptSetV1, LockedRuntimeBuilder\n"
        )
        self.assertNotEqual(
            _from_symbol_digest(allowed),
            _from_symbol_digest(expanded),
        )


def _imports(tree: ast.AST) -> set[str]:
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def _exact_imports(tree: ast.Module) -> set[str]:
    result = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.add("." * node.level + (node.module or ""))
    return result


def _from_symbol_digest(tree: ast.AST) -> str:
    values = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = "." * node.level + (node.module or "")
        values.extend(
            f"{module}|{item.name}|{item.asname or ''}"
            for item in node.names
        )
    payload = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _imports_lifecycle(tree: ast.AST) -> bool:
    prefix = "backend.cutover_service_lifecycle"
    if any(
        name == prefix or name.startswith(prefix + ".")
        for name in _imports(tree)
    ):
        return True
    aliases = _dynamic_import_aliases(tree)
    return any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in aliases
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        )
        for node in ast.walk(tree)
    )


def _dynamic_import_aliases(tree: ast.AST) -> set[str]:
    aliases = {"__import__", "import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            aliases.update(
                item.asname or item.name
                for item in node.names
                if item.name == "import_module"
            )
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)
            ):
                continue
            value = node.value
            dynamic = (
                isinstance(value, ast.Name) and value.id in aliases
            ) or (
                isinstance(value, ast.Attribute)
                and value.attr == "import_module"
            )
            if not dynamic:
                continue
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else (node.target,)
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases


if __name__ == "__main__":
    unittest.main()
