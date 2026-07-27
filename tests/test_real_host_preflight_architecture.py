"""Capability, bridge, and content-free guards for Issue #53."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import backend.real_host_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "real_host_preflight"
EXPECTED_FILES = {
    "__init__.py",
    "audit_bridge.py",
    "audit_types.py",
    "authorization_gate.py",
    "baseline.py",
    "baseline_bridge.py",
    "baseline_evidence.py",
    "callbacks.py",
    "canonical.py",
    "collection.py",
    "composition.py",
    "contracts.py",
    "contracts_bridge.py",
    "errors.py",
    "evidence.py",
    "mutation_gate.py",
    "operator_entry.py",
    "receipts.py",
    "sandbox_validation.py",
    "topology.py",
    "topology_evidence.py",
    "windows_api.py",
    "windows_chain.py",
    "windows_observation.py",
    "windows_paths.py",
    "windows_projection.py",
}
EXPECTED_PUBLIC = {
    "AclBaselineObservationV1",
    "BaselineAclRole",
    "BoundAuditCallbackV1",
    "CurrentTopologyCallbacks",
    "CurrentTopologyObservationV1",
    "CurrentTopologyPreflightReceiptV1",
    "FinalAuditCallbacksV1",
    "FinalAuditCompositionReadyReceiptV1",
    "FinalAuditCompositionV1",
    "HostCheckKind",
    "HostObjectKind",
    "HostObjectObservationV1",
    "MissingHostObjectObservationV1",
    "OpaqueHostCheckV1",
    "OperatorSidObservationV1",
    "PreMutationGate",
    "PreMutationGateReceiptV1",
    "RealHostBaselineCallbacks",
    "RealHostBaselineCollector",
    "RealHostPreflightError",
    "TestSandboxScopeV1",
    "VolumeObservationV1",
    "WindowsReadOnlyObserver",
    "prepare_final_audit_composition",
    "prove_final_audit_composition_ready",
    "real_host_preflight_operator_entry",
    "run_current_topology_preflight",
}
ALLOWED_ABSOLUTE_IMPORTS = {
    "backend.container_audit",
    "backend.container_audit.policy",
    "backend.cutover_contracts",
    "backend.migration_evidence",
}
FORBIDDEN_IMPORT_ROOTS = {
    "argparse",
    "logging",
    "os",
    "shutil",
    "socket",
    "sqlite3",
    "subprocess",
    "tempfile",
}
FORBIDDEN_CALL_NAMES = {
    "__import__",
    "eval",
    "exec",
    "getattr",
    "input",
    "open",
    "print",
    "setattr",
}
FORBIDDEN_CALL_ATTRIBUTES = {
    "Popen",
    "chmod",
    "connect",
    "copy",
    "copy2",
    "getenv",
    "mkdir",
    "move",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "rmtree",
    "run",
    "start",
    "touch",
    "unlink",
    "write",
    "write_bytes",
    "write_text",
}
ALLOWED_WINDOWS_APIS = {
    "CloseHandle",
    "CreateFileW",
    "GetFileInformationByHandleEx",
    "GetFileType",
    "GetDriveTypeW",
    "GetFinalPathNameByHandleW",
    "GetVolumeInformationByHandleW",
    "POINTER",
    "Structure",
    "WinDLL",
}
FORBIDDEN_NATIVE_MARKERS = {
    "ControlService",
    "CopyFile",
    "CreateProcess",
    "DeleteFile",
    "MoveFile",
    "OpenSCManager",
    "ReplaceFile",
    "SetFileInformationByHandle",
    "SetSecurityInfo",
    "StartService",
}


class RealHostPreflightArchitectureTests(unittest.TestCase):
    def test_package_and_public_surface_are_exact(self) -> None:
        files = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.relative_to(PACKAGE).parts
        }
        self.assertEqual(files, EXPECTED_FILES)
        self.assertEqual(set(preflight.__all__), EXPECTED_PUBLIC)

    def test_files_and_functions_remain_bounded(self) -> None:
        for path in sorted(PACKAGE.glob("*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path)
            tree = ast.parse("\n".join(lines), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    length = (node.end_lineno or node.lineno) - node.lineno + 1
                    self.assertLessEqual(
                        length,
                        50,
                        (path.name, node.name, length),
                    )

    def test_only_exact_bridge_modules_import_prior_layers(self) -> None:
        expected = {
            "audit_bridge.py": {
                "backend.container_audit",
                "backend.container_audit.policy",
            },
            "baseline_bridge.py": {"backend.migration_evidence"},
            "contracts_bridge.py": {"backend.cutover_contracts"},
        }
        for path in sorted(PACKAGE.glob("*.py")):
            absolute = _absolute_imports(path)
            prior_layers = absolute & ALLOWED_ABSOLUTE_IMPORTS
            self.assertEqual(prior_layers, expected.get(path.name, set()), path)
            self.assertFalse(
                {
                    item
                    for item in absolute
                    if item.startswith("backend.")
                    and item not in ALLOWED_ABSOLUTE_IMPORTS
                },
                path,
            )

    def test_package_has_no_mutation_or_ambient_host_capability(self) -> None:
        for path in sorted(PACKAGE.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = _absolute_imports(path)
            roots = {item.split(".", 1)[0] for item in imports}
            self.assertTrue(
                roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS),
                (path.name, sorted(roots & FORBIDDEN_IMPORT_ROOTS)),
            )
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, FORBIDDEN_CALL_NAMES, path)
                elif isinstance(node.func, ast.Attribute):
                    self.assertNotIn(
                        node.func.attr,
                        FORBIDDEN_CALL_ATTRIBUTES,
                        (path.name, node.func.attr),
                    )

    def test_windows_native_surface_is_read_only_and_closed(self) -> None:
        source = (PACKAGE / "windows_api.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        referenced = {
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr[:1].isupper()
        }
        self.assertLessEqual(referenced, ALLOWED_WINDOWS_APIS)
        for marker in FORBIDDEN_NATIVE_MARKERS:
            self.assertNotIn(marker, source)

    def test_normal_runtime_and_operator_surfaces_do_not_consume_package(
        self,
    ) -> None:
        candidates = [
            path
            for path in (ROOT / "backend").rglob("*.py")
            if PACKAGE.resolve() not in path.resolve().parents
        ]
        candidates.extend((ROOT / "scripts").rglob("*.py"))
        candidates.extend(
            path
            for path in (ROOT / "frontend").rglob("*")
            if path.is_file() and path.suffix in {".js", ".html"}
        )
        workflows = ROOT / ".github" / "workflows"
        if workflows.exists():
            candidates.extend(path for path in workflows.rglob("*") if path.is_file())
        violations = [
            path.relative_to(ROOT).as_posix()
            for path in candidates
            if "real_host_preflight" in path.read_text(
                encoding="utf-8", errors="ignore"
            )
            and path.resolve()
            != (ROOT / "scripts" / "generate_project_status.py").resolve()
        ]
        self.assertEqual(violations, [])
        self.assertEqual(
            tuple(
                inspect.signature(
                    preflight.real_host_preflight_operator_entry
                ).parameters
            ),
            (),
        )


def _absolute_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.add(node.module)
    return imports


if __name__ == "__main__":
    unittest.main()
