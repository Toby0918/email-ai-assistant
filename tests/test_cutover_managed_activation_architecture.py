from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_managed_activation import (
    ArtifactPublicationAdapter,
    ConfigPublicationAdapter,
    DatabasePublicationAdapter,
    ManagedActivationAdapters,
    ManagedConfigV1,
    RuntimePublicationAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "cutover_managed_activation"
EXPECTED_PACKAGE_FILES = {
    "__init__.py",
    "adapters.py",
    "artifact_publisher.py",
    "canonical.py",
    "config_contract.py",
    "config_publisher.py",
    "database_copier.py",
    "errors.py",
    "phase.py",
    "publication_scope.py",
    "real_lock.py",
    "receipts.py",
    "runtime_builder.py",
    "runtime_archive.py",
    "runtime_capture.py",
    "runtime_execution.py",
    "runtime_limits.py",
    "runtime_policy.py",
    "runtime_source_tree.py",
    "runtime_startup_archive.py",
    "runtime_tree.py",
    "runtime_verification.py",
    "scope_models.py",
    "scope_paths.py",
    "scope_profile.py",
    "stopped_service.py",
    "synthetic_scope.py",
    "windows_file_handles.py",
    "windows_directory_monitor.py",
    "windows_publication_io.py",
    "windows_streams.py",
}
EXPECTED_EXPORTS = {
    "ArtifactPublicationAdapter",
    "ArtifactPublisher",
    "ConfigPublicationAdapter",
    "ConfigPublicationReceiptV1",
    "ConfigPublisher",
    "CrxPublicationReceiptV1",
    "DatabasePublicationAdapter",
    "LockedRuntimeBuilder",
    "ManagedActivationAdapters",
    "ManagedActivationError",
    "ManagedActivationPhase",
    "ManagedActivationReceiptSetV1",
    "ManagedConfigV1",
    "ManagedRuntimeReceiptV1",
    "RuntimePublicationAdapter",
    "StoppedDatabaseCopier",
    "StoppedDatabaseCopyReceiptV1",
    "StoppedServiceReceiptV1",
    "locked_real_artifact_publisher_constructor",
    "locked_real_config_publisher_constructor",
    "locked_real_database_copier_constructor",
    "locked_real_runtime_builder_constructor",
}


class ManagedActivationArchitectureTests(unittest.TestCase):
    def test_package_and_exports_are_exact(self) -> None:
        package_files = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.relative_to(PACKAGE).parts
        }
        self.assertEqual(package_files, EXPECTED_PACKAGE_FILES)

        module = __import__(
            "backend.cutover_managed_activation",
            fromlist=["__all__"],
        )
        self.assertEqual(set(module.__all__), EXPECTED_EXPORTS)
        self.assertEqual(len(module.__all__), len(EXPECTED_EXPORTS))

    def test_normal_runtime_has_no_managed_activation_consumer(self) -> None:
        allowed_consumers = {
            "backend/cutover_service_lifecycle/activation_validation.py",
            "backend/cutover_service_lifecycle/lifecycle.py",
            "backend/cutover_service_lifecycle/lifecycle_binding.py",
            "backend/r2_issue39_orchestrator/input_identity.py",
            "backend/r2_issue39_orchestrator/production_acl.py",
            "backend/r2_issue39_orchestrator/production_anchor_package.py",
            "backend/r2_issue39_orchestrator/production_audit.py",
            "backend/r2_issue39_orchestrator/production_database.py",
            "backend/r2_issue39_orchestrator/production_evidence.py",
            "backend/r2_issue39_orchestrator/production_inputs.py",
            "backend/r2_issue39_orchestrator/production_managed.py",
            "backend/r2_issue39_orchestrator/production_native.py",
            "backend/r2_issue39_orchestrator/production_repository.py",
            "backend/r2_issue39_orchestrator/production_repository_review.py",
            "backend/r2_issue39_orchestrator/production_runtime_review.py",
            "backend/r2_issue39_orchestrator/production_service.py",
            "backend/r2_issue39_orchestrator/restart_anchor.py",
            "backend/r2_runtime_publication/__init__.py",
            "backend/r2_runtime_publication/builder.py",
            "backend/r2_runtime_publication/contracts.py",
        }
        findings = set()
        for directory in ("backend", "scripts", "frontend"):
            for path in (ROOT / directory).rglob("*.py"):
                if PACKAGE in path.parents:
                    continue
                if _imports_managed_activation(path.read_text("utf-8")):
                    findings.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(findings, allowed_consumers)

    def test_consumer_guard_covers_equivalent_and_dynamic_imports(self) -> None:
        sources = (
            "from backend import cutover_managed_activation",
            "from . import cutover_managed_activation",
            "import backend.cutover_managed_activation.runtime_builder",
            "from importlib import import_module as load\n"
            "load('backend.cutover_managed_activation')",
            "import importlib as loader\n"
            "loader.import_module('backend.cutover_managed_activation')",
            "import importlib\n"
            "load = importlib.import_module\n"
            "load('backend.cutover_managed_activation')",
            "__import__('backend.cutover_managed_activation')",
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertTrue(_imports_managed_activation(source))

    def test_package_files_and_functions_remain_bounded(self) -> None:
        for path in PACKAGE.rglob("*.py"):
            source = path.read_text("utf-8")
            with self.subTest(path=path.name):
                self.assertLessEqual(len(source.splitlines()), 300)
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    with self.subTest(path=path.name, function=node.name):
                        self.assertLessEqual(
                            node.end_lineno - node.lineno + 1,
                            50,
                        )

    def test_phase_adapter_bundle_has_only_four_narrow_capabilities(self) -> None:
        self.assertEqual(
            tuple(ManagedActivationAdapters.__dataclass_fields__),
            ("runtime", "database", "artifact", "config"),
        )
        self.assertEqual(
            tuple(RuntimePublicationAdapter.__dataclass_fields__),
            ("publish_runtime",),
        )
        self.assertEqual(
            tuple(DatabasePublicationAdapter.__dataclass_fields__),
            ("copy_stopped_database",),
        )
        self.assertEqual(
            tuple(ArtifactPublicationAdapter.__dataclass_fields__),
            ("publish_crx",),
        )
        self.assertEqual(
            tuple(ConfigPublicationAdapter.__dataclass_fields__),
            ("publish_config",),
        )

    def test_package_does_not_import_adjacent_host_capabilities(self) -> None:
        forbidden = (
            "backend.cutover_host_mutation",
            "backend.cutover_repository_transaction",
            "backend.email_agent",
            "backend.mailbox_ingest",
            "backend.private_knowledge",
            "backend.private_evaluation",
            "frontend",
        )
        findings = []
        for path in PACKAGE.rglob("*.py"):
            tree = ast.parse(path.read_text("utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = []
                if type(node) is ast.Import:
                    names = [alias.name for alias in node.names]
                elif type(node) is ast.ImportFrom and node.module:
                    names = [node.module]
                for name in names:
                    if name.startswith(forbidden):
                        findings.append(f"{path.name}:{name}")
        self.assertEqual(findings, [])

    def test_config_contract_has_no_dynamic_or_secret_reader(self) -> None:
        path = PACKAGE / "config_contract.py"
        source = path.read_text("utf-8")
        tree = ast.parse(source, filename=str(path))
        imports = {
            alias.name
            for node in ast.walk(tree)
            if type(node) is ast.Import
            for alias in node.names
        }
        self.assertTrue(
            imports.isdisjoint(
                {
                    "os",
                    "winreg",
                    "getpass",
                    "ctypes",
                    "subprocess",
                    "dotenv",
                    "keyring",
                }
            )
        )
        self.assertNotIn("environ", source)
        self.assertNotIn("clipboard", source.casefold())
        self.assertNotIn("credential", source.casefold())
        self.assertNotIn("hidden", source.casefold())

    def test_portable_config_contract_is_deterministic(self) -> None:
        mapping = {
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": [
                "example.test",
                "internal.example",
            ],
            "EMAIL_AGENT_LOG_LEVEL": "INFO",
        }
        first = ManagedConfigV1.from_mapping(mapping).to_canonical_bytes()
        second = ManagedConfigV1.from_mapping(mapping).to_canonical_bytes()
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            b'{"EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE":"conservative",'
            b'"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS":'
            b'["example.test","internal.example"],'
            b'"EMAIL_AGENT_LLM_PROVIDER":"disabled",'
            b'"EMAIL_AGENT_LOG_LEVEL":"INFO",'
            b'"EMAIL_AGENT_TEXT_FALLBACK_PROVIDER":"disabled",'
            b'"config_type":"managed-non-secret-config/v1"}',
        )

    def test_runtime_builder_has_no_resolution_or_system_python_fallback(
        self,
    ) -> None:
        paths = (
            PACKAGE / "runtime_builder.py",
            PACKAGE / "runtime_capture.py",
            PACKAGE / "runtime_execution.py",
            PACKAGE / "runtime_verification.py",
        )
        source = "\n".join(path.read_text("utf-8") for path in paths)
        tree = ast.parse(source, filename="managed_activation_runtime_modules")
        imports = {
            alias.name
            for node in ast.walk(tree)
            if type(node) is ast.Import
            for alias in node.names
        }
        self.assertNotIn("socket", imports)
        self.assertNotIn("urllib", imports)
        self.assertNotIn("pip", imports)
        host_executable_reads = [
            node
            for node in ast.walk(tree)
            if type(node) is ast.Attribute
            and node.attr == "executable"
            and type(node.value) is ast.Name
            and node.value.id == "sys"
        ]
        self.assertEqual(host_executable_reads, [])
        self.assertNotIn('"PATH"', source)
        self.assertIn('"PIP_NO_INDEX": "1"', source)
        self.assertIn("source.publish_into(tree)", source)
        self.assertGreaterEqual(source.count('"-S"'), 1)
        self.assertIn('"frozen_modules=on"', source)
        self.assertIn('"PYTHONNOUSERSITE": "1"', source)
        self.assertIn("shell=False", source)
        self.assertIn("stdin=subprocess.DEVNULL", source)
        self.assertIn("sys.addaudithook", source)
        self.assertNotIn("sys.path.insert", source)
        self.assertNotIn("importlib.import_module", source)
        self.assertIn("source.read(65536)", source)
        verification = paths[-1].read_text("utf-8")
        verification_tree = ast.parse(verification)
        helper_assignment = next(
            node
            for node in verification_tree.body
            if type(node) is ast.Assign
            and any(
                type(target) is ast.Name
                and target.id == "_SCRIPT_HELPERS"
                for target in node.targets
            )
        )
        helper_script = ast.literal_eval(helper_assignment.value)
        self.assertTrue(
            helper_script.startswith("import sys,nt,_sha2,_imp\n")
        )
        for shadowable in (
            "import hashlib",
            "import importlib",
            "import json",
            "import os",
            "import sqlite3",
        ):
            self.assertNotIn(shadowable, helper_script)
        self.assertIn("event == 'import'", helper_script)
        self.assertIn("_sqlite3.pyd", verification)
        self.assertIn("sqlite3.dll", verification)
        self.assertIn("managed-startup.zip", verification)
        tree_source = (PACKAGE / "runtime_tree.py").read_text("utf-8")
        self.assertNotIn("sorted(os.scandir", tree_source)

    def test_database_and_artifact_have_no_repair_or_private_reader(
        self,
    ) -> None:
        database = (PACKAGE / "database_copier.py").read_text("utf-8")
        artifact = (PACKAGE / "artifact_publisher.py").read_text("utf-8")
        executable_database = ast.parse(database)
        database_calls = {
            node.func.attr
            for node in ast.walk(executable_database)
            if type(node) is ast.Call and type(node.func) is ast.Attribute
        }
        self.assertTrue(
            database_calls.isdisjoint(
                {"unlink", "remove", "replace", "rename", "checkpoint"}
            )
        )
        self.assertNotIn("sqlite_master", database.casefold())
        self.assertNotIn("select ", database.casefold())
        self.assertIn("PRAGMA quick_check(1)", database)
        self.assertIn("deny_write=True", database)
        artifact_tree = ast.parse(artifact)
        artifact_imports = {
            alias.name
            for node in ast.walk(artifact_tree)
            if type(node) is ast.Import
            for alias in node.names
        }
        self.assertTrue(
            artifact_imports.isdisjoint(
                {"zipfile", "subprocess", "webbrowser", "winreg"}
            )
        )

    def test_no_publication_module_can_delete_or_repair_a_target(self) -> None:
        findings = []
        forbidden_calls = {"unlink", "remove", "rmdir", "rmtree", "rename"}
        for path in PACKAGE.rglob("*.py"):
            tree = ast.parse(path.read_text("utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if (
                    type(node) is ast.Call
                    and type(node.func) is ast.Attribute
                    and node.func.attr in forbidden_calls
                ):
                    findings.append(f"{path.name}:{node.func.attr}")
        self.assertEqual(findings, [])


def _imports_managed_activation(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "backend.cutover_managed_activation"
            or alias.name.startswith("backend.cutover_managed_activation.")
            for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (
                module == "backend.cutover_managed_activation"
                or module.startswith("backend.cutover_managed_activation.")
            ):
                return True
            if node.level == 0 and module == "backend" and any(
                alias.name == "cutover_managed_activation"
                for alias in node.names
            ):
                return True
            if node.level > 0 and (
                module == "cutover_managed_activation"
                or module.startswith("cutover_managed_activation.")
                or any(
                    alias.name == "cutover_managed_activation"
                    for alias in node.names
                )
            ):
                return True
    aliases, module_aliases = _dynamic_import_aliases(tree)
    return any(
        isinstance(node, ast.Call)
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and (
            node.args[0].value == "backend.cutover_managed_activation"
            or node.args[0].value.startswith(
                "backend.cutover_managed_activation."
            )
        )
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in aliases
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in {"import_module", "__import__"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_aliases
        )
        for node in ast.walk(tree)
    )


def _dynamic_import_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    aliases = {"__import__", "import_module"}
    module_aliases = {"importlib", "builtins"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"importlib", "builtins"}:
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in {
            "importlib",
            "builtins",
        }:
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in {"import_module", "__import__"}
            )
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                continue
            value = node.value
            dynamic = (
                isinstance(value, ast.Name) and value.id in aliases
            ) or (
                isinstance(value, ast.Attribute)
                and value.attr in {"import_module", "__import__"}
                and isinstance(value.value, ast.Name)
                and value.value.id in module_aliases
            )
            if not dynamic:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases, module_aliases


if __name__ == "__main__":
    unittest.main()
