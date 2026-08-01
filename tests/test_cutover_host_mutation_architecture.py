"""Mechanical capability and leakage guards for Issue #55."""

from __future__ import annotations

import ast
import inspect
import types
import unittest
from pathlib import Path

import backend.cutover_host_mutation as contracts
from backend.cutover_host_mutation.windows_acl import WindowsAclAdapter


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "cutover_host_mutation"
EXPECTED_PUBLIC = {
    "AclApplyReceiptV1",
    "AclBaselineReceiptV1",
    "AclCompatibilityObservationV1",
    "AclCompatibilityPolicyV1",
    "AclCompatibilityReceiptV1",
    "AclDescriptorObservationV1",
    "AclFailureCode",
    "AclPostVerifyReceiptV1",
    "AclReceiptStatus",
    "AclRole",
    "FilesystemMutationExpectationV1",
    "FilesystemMutationKind",
    "FilesystemMutationObservationV1",
}
FORBIDDEN_TEXT = {
    "icacls",
    "powershell",
    "cmd.exe",
    "subprocess",
    "shell=true",
    "convertsddl",
    "convertstringsecuritydescriptortosecuritydescriptor",
    "setnamedsecurityinfo",
    "setfilesecurity",
}


class CutoverHostMutationArchitectureTests(unittest.TestCase):
    def test_public_surface_is_portable_contracts_only(self) -> None:
        self.assertEqual(set(contracts.__all__), EXPECTED_PUBLIC)
        self.assertEqual(
            {
                name
                for name, value in vars(contracts).items()
                if not name.startswith("_")
                and not isinstance(value, types.ModuleType)
            },
            EXPECTED_PUBLIC,
        )
        source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("windows_", source)
        self.assertNotIn("operator_entry", source)

    def test_acl_adapter_has_only_the_four_fixed_operations(self) -> None:
        public = {
            name
            for name, value in vars(WindowsAclAdapter).items()
            if not name.startswith("_") and callable(value)
        }
        self.assertEqual(
            public,
            {
                "apply_new_container_policy",
                "capture",
                "compare",
                "verify_fixed_zone_inheritance",
            },
        )
        self.assertEqual(
            tuple(
                inspect.signature(WindowsAclAdapter.capture).parameters
            ),
            ("self", "role"),
        )

    def test_acl_apply_uses_one_direct_dacl_only_security_call(self) -> None:
        sources = {
            path.name: path.read_text(encoding="utf-8")
            for path in PACKAGE.glob("*.py")
        }
        callers = [
            name
            for name, source in sources.items()
            if "SetSecurityInfo(" in source
        ]
        self.assertEqual(callers, ["windows_acl_apply.py"])
        apply_source = sources["windows_acl_apply.py"]
        self.assertIn("SetEntriesInAclW", apply_source)
        self.assertIn("CreateWellKnownSid", apply_source)
        self.assertIn(
            "_DACL_SECURITY_INFORMATION"
            " | _PROTECTED_DACL_SECURITY_INFORMATION",
            apply_source.replace("\n", " "),
        )
        call = _named_call(apply_source, "SetSecurityInfo")
        self.assertEqual(len(call.args), 7)
        self.assertTrue(
            all(
                isinstance(call.args[index], ast.Constant)
                and call.args[index].value is None
                for index in (3, 4, 6)
            )
        )

    def test_no_command_acl_transcript_or_replace_surface_exists(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in FORBIDDEN_TEXT:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)
        self.assertNotIn("movefile", source)
        self.assertIn("ntsetinformationfile", source)
        self.assertIn("replace_if_exists = 0", source)

    def test_directory_create_is_handle_relative_and_atomic_no_replace(
        self,
    ) -> None:
        directory = _source("windows_directory.py")
        native = _source("windows_directory_native.py")
        bindings = _source("windows_native_bindings.py")

        self.assertIn("create_directory_relative", directory)
        self.assertNotIn("CreateDirectoryW", directory)
        self.assertIn("NtCreateFile", native)
        self.assertIn("root_directory=parent_handle", native)
        self.assertIn("_FILE_CREATE", native)
        self.assertIn("NtCreateFile", bindings)

    def test_no_runtime_script_frontend_or_workflow_consumer_exists(
        self,
    ) -> None:
        allowed_consumers = {
            "backend/cutover_repository_transaction/git_runner.py",
            "backend/cutover_repository_transaction/issue52_bridge.py",
            "backend/cutover_repository_transaction/mutation_executor.py",
            "backend/cutover_repository_transaction/real_lock.py",
            "backend/cutover_repository_transaction/stable_observation.py",
            "backend/cutover_repository_transaction/windows_identity.py",
            "backend/r2_main_publication/host_effects.py",
            "backend/r2_main_publication/permit.py",
            "backend/r2_main_publication/testing.py",
            "backend/r2_main_publication/windows_dacl.py",
            "backend/r2_repository_manifest/host.py",
            "backend/r2_repository_manifest/testing.py",
        }
        violations = []
        roots = (
            ROOT / "backend",
            ROOT / "scripts",
            ROOT / "frontend",
            ROOT / ".github" / "workflows",
        )
        status_generator = (
            ROOT / "scripts" / "generate_project_status.py"
        ).resolve()
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if (
                    not path.is_file()
                    or PACKAGE in path.parents
                    or path.resolve() == status_generator
                    or path.suffix not in {".py", ".js", ".html", ".yml", ".yaml"}
                ):
                    continue
                source = path.read_text(encoding="utf-8", errors="ignore")
                if (
                    "backend.cutover_host_mutation" in source
                    or "backend/cutover_host_mutation" in source
                ):
                    violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(set(violations), allowed_consumers)

    def test_package_has_no_print_logging_or_environment_reads(self) -> None:
        forbidden_calls = {"getenv", "print", "system"}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = {
                node.func.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
            }
            attributes = {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
            }
            with self.subTest(path=path.name):
                self.assertFalse(forbidden_calls & (calls | attributes))


def _named_call(source: str, name: str) -> ast.Call:
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == name
    ]
    if len(calls) != 1:
        raise AssertionError(f"expected one {name} call")
    return calls[0]


def _source(name: str) -> str:
    return (PACKAGE / name).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
