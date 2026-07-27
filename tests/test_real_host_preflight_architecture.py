"""Capability, bridge, and content-free guards for Issue #53."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import backend.real_host_preflight as preflight


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "real_host_preflight"
PACKAGE_MODULE = "backend.real_host_preflight"


def _internal_imports(*names: str) -> set[str]:
    return {f"{PACKAGE_MODULE}.{name}" for name in names}


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
    "integrity.py",
    "mutation_gate.py",
    "operator_entry.py",
    "profile_snapshot.py",
    "receipts.py",
    "sandbox_lease.py",
    "sandbox_state.py",
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
    "VolumeObservationV1",
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
ALLOWED_IMPORTS_BY_FILE = {
    "__init__.py": _internal_imports(
        "audit_types",
        "baseline",
        "baseline_evidence",
        "callbacks",
        "composition",
        "contracts",
        "errors",
        "evidence",
        "mutation_gate",
        "operator_entry",
        "receipts",
        "topology",
        "topology_evidence",
    ),
    "audit_bridge.py": {
        "backend.container_audit",
        "backend.container_audit.policy",
    },
    "audit_types.py": {"__future__", "dataclasses", "typing"}
    | _internal_imports("canonical"),
    "authorization_gate.py": {"__future__"}
    | _internal_imports("canonical", "contracts_bridge"),
    "baseline.py": {"__future__", "dataclasses"}
    | _internal_imports(
        "authorization_gate",
        "baseline_bridge",
        "baseline_evidence",
        "canonical",
        "contracts",
        "contracts_bridge",
        "evidence",
        "integrity",
        "profile_snapshot",
    ),
    "baseline_bridge.py": {"backend.migration_evidence"},
    "baseline_evidence.py": {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
    }
    | _internal_imports("canonical", "contracts", "evidence"),
    "callbacks.py": {"__future__", "dataclasses", "typing"}
    | _internal_imports("contracts", "evidence"),
    "canonical.py": {"__future__", "hashlib", "json"},
    "collection.py": {"__future__"}
    | _internal_imports(
        "callbacks",
        "canonical",
        "contracts",
        "contracts_bridge",
        "evidence",
        "integrity",
        "topology_evidence",
    ),
    "composition.py": {"__future__", "dataclasses"}
    | _internal_imports(
        "audit_bridge",
        "audit_types",
        "authorization_gate",
        "canonical",
        "contracts_bridge",
        "receipts",
    ),
    "contracts.py": {
        "__future__",
        "dataclasses",
        "enum",
        "hashlib",
        "json",
    },
    "contracts_bridge.py": {"backend.cutover_contracts"},
    "errors.py": {"__future__"},
    "evidence.py": {"__future__", "dataclasses", "enum"}
    | _internal_imports("canonical"),
    "integrity.py": {"__future__"}
    | _internal_imports("baseline_evidence", "contracts", "evidence"),
    "mutation_gate.py": {
        "__future__",
        "dataclasses",
        "threading",
        "uuid",
        "weakref",
    }
    | _internal_imports(
        "authorization_gate",
        "callbacks",
        "canonical",
        "collection",
        "contracts_bridge",
        "profile_snapshot",
        "receipts",
    ),
    "operator_entry.py": _internal_imports("contracts_bridge"),
    "profile_snapshot.py": {"__future__"}
    | _internal_imports("contracts_bridge"),
    "receipts.py": {
        "__future__",
        "dataclasses",
        "threading",
        "weakref",
    }
    | _internal_imports("contracts_bridge"),
    "sandbox_lease.py": {
        "__future__",
        "contextlib",
        "pathlib",
        "typing",
    }
    | _internal_imports(
        "contracts",
        "errors",
        "sandbox_state",
        "windows_api",
        "windows_chain",
    ),
    "sandbox_state.py": {
        "__future__",
        "dataclasses",
        "pathlib",
        "threading",
        "typing",
        "weakref",
    },
    "sandbox_validation.py": {"__future__"}
    | _internal_imports("contracts_bridge", "errors", "windows_paths"),
    "topology.py": {"__future__"}
    | _internal_imports(
        "authorization_gate",
        "callbacks",
        "canonical",
        "collection",
        "contracts_bridge",
        "profile_snapshot",
        "receipts",
    ),
    "topology_evidence.py": {"__future__", "dataclasses"}
    | _internal_imports("canonical", "contracts", "integrity"),
    "windows_api.py": {
        "__future__",
        "ctypes",
        "dataclasses",
        "hashlib",
        "pathlib",
        "sys",
    }
    | _internal_imports("errors"),
    "windows_chain.py": {
        "__future__",
        "contextlib",
        "dataclasses",
        "pathlib",
        "typing",
    }
    | _internal_imports(
        "contracts",
        "errors",
        "windows_api",
        "windows_paths",
        "windows_projection",
    ),
    "windows_observation.py": {"__future__", "pathlib"}
    | _internal_imports(
        "canonical",
        "contracts",
        "errors",
        "evidence",
        "sandbox_lease",
        "sandbox_state",
        "sandbox_validation",
        "windows_api",
        "windows_chain",
        "windows_paths",
    ),
    "windows_paths.py": {"pathlib"},
    "windows_projection.py": _internal_imports("contracts", "windows_api"),
}
SENSITIVE_IMPORT_FILES = {
    "ctypes": {"windows_api.py"},
    "pathlib": {
        "sandbox_lease.py",
        "sandbox_state.py",
        "windows_api.py",
        "windows_chain.py",
        "windows_observation.py",
        "windows_paths.py",
    },
    "threading": {
        "mutation_gate.py",
        "receipts.py",
        "sandbox_state.py",
    },
    "weakref": {
        "mutation_gate.py",
        "receipts.py",
        "sandbox_state.py",
    },
}
SENSITIVE_FROM_NAMES = {
    "ctypes": set(),
    "pathlib": {"Path"},
    "threading": {"Lock"},
    "weakref": {"WeakKeyDictionary"},
}
SENSITIVE_IMPORT_FORMS = {
    "ctypes": "import",
    "pathlib": "from",
    "threading": "from",
    "weakref": "from",
}
ALLOWED_PRIVATE_IMPORTS = {
    ("composition.py", f"{PACKAGE_MODULE}.receipts"): {
        "_mint_final_audit_ready_receipt",
    },
    ("mutation_gate.py", f"{PACKAGE_MODULE}.receipts"): {
        "_claim_current_topology_receipt",
        "_mint_pre_mutation_gate_receipt",
    },
    ("sandbox_lease.py", f"{PACKAGE_MODULE}.windows_api"): {
        "_WindowsApi",
        "_WindowsApiFailure",
    },
    ("topology.py", f"{PACKAGE_MODULE}.receipts"): {
        "_mint_current_topology_receipt",
    },
    ("windows_chain.py", f"{PACKAGE_MODULE}.windows_api"): {
        "_NativeObservation",
        "_WindowsApi",
        "_WindowsApiFailure",
    },
    ("windows_observation.py", f"{PACKAGE_MODULE}.sandbox_state"): {
        "_claim_permit",
        "_observer_state",
        "_register_observer",
        "_register_permit",
        "_register_scope",
        "_scope_state",
    },
    ("windows_observation.py", f"{PACKAGE_MODULE}.windows_api"): {
        "_WindowsApi",
        "_WindowsApiFailure",
        "_text_fingerprint",
    },
    ("windows_projection.py", f"{PACKAGE_MODULE}.windows_api"): {
        "_NativeObservation",
        "_text_fingerprint",
        "_volume_fingerprint",
    },
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
    "open",
    "read_bytes",
    "read_text",
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
FORBIDDEN_PATH_CAPABILITY_ATTRIBUTES = {
    "absolute",
    "chmod",
    "cwd",
    "exists",
    "expanduser",
    "glob",
    "group",
    "hardlink_to",
    "home",
    "is_block_device",
    "is_char_device",
    "is_dir",
    "is_fifo",
    "is_file",
    "is_junction",
    "is_mount",
    "is_socket",
    "is_symlink",
    "iterdir",
    "lchmod",
    "link_to",
    "lstat",
    "mkdir",
    "open",
    "owner",
    "read_bytes",
    "read_text",
    "readlink",
    "rename",
    "replace",
    "resolve",
    "rglob",
    "rmdir",
    "samefile",
    "stat",
    "symlink_to",
    "touch",
    "unlink",
    "walk",
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
    def test_mutation_fixtures_close_capability_guard_escapes(self) -> None:
        relative = _source_policy_violations(
            "canonical.py",
            "from ..email_agent import analyze\n",
        )
        self.assertIn(
            ("unexpected-import", "backend.email_agent"),
            relative,
        )
        escaped = _source_policy_violations(
            "canonical.py",
            "from ...email_agent import analyze\n",
        )
        self.assertIn(("relative-import-escape", "email_agent"), escaped)
        resolved, resolution_escapes = _canonical_imports_from_source(
            "topology.py",
            "from .canonical import fingerprint\n",
        )
        self.assertEqual(
            resolved,
            {f"{PACKAGE_MODULE}.canonical"},
        )
        self.assertEqual(resolution_escapes, set())
        for filename in ("composition.py", "operator_entry.py"):
            with self.subTest(native_seam=filename):
                violations = _source_policy_violations(
                    filename,
                    "from .windows_api import _WindowsApi\n",
                )
                self.assertIn(
                    (
                        "unexpected-import",
                        f"{PACKAGE_MODULE}.windows_api",
                    ),
                    violations,
                )

        for filename, module in (
            ("canonical.py", "pathlib"),
            ("contracts.py", "ctypes"),
            ("topology.py", "threading"),
            ("baseline.py", "weakref"),
        ):
            with self.subTest(filename=filename, module=module):
                violations = _source_policy_violations(
                    filename,
                    f"import {module}\n",
                )
                self.assertIn(("sensitive-import", module), violations)

        direct_native = _source_policy_violations(
            "windows_api.py",
            "from ctypes import CDLL\n",
        )
        self.assertIn(
            ("unexpected-import-name", "ctypes:CDLL"),
            direct_native,
        )
        threading_form = _source_policy_violations(
            "mutation_gate.py",
            "import threading\nthreading.Thread(target=lambda: None)\n",
        )
        self.assertIn(
            ("unexpected-import-form", "threading:import"),
            threading_form,
        )
        private_seam = _source_policy_violations(
            "topology.py",
            "from .receipts import _reset_all_receipts\n",
        )
        self.assertIn(
            (
                "unexpected-private-import",
                "backend.real_host_preflight.receipts:_reset_all_receipts",
            ),
            private_seam,
        )
        wildcard = _source_policy_violations(
            "topology.py",
            "from .receipts import *\n",
        )
        self.assertIn(
            (
                "wildcard-import",
                "backend.real_host_preflight.receipts:*",
            ),
            wildcard,
        )
        for source in (
            "import backend.real_host_preflight.receipts as receipts\n",
            "from . import receipts\n",
            "from backend.real_host_preflight.receipts import "
            "CurrentTopologyPreflightReceiptV1\n",
        ):
            with self.subTest(internal_form=source):
                violations = _source_policy_violations(
                    "topology.py",
                    source,
                )
                self.assertTrue(
                    any(
                        code == "internal-import-form"
                        for code, _detail in violations
                    ),
                    violations,
                )

        for method in ("open", "read_text", "read_bytes"):
            with self.subTest(method=method):
                violations = _source_policy_violations(
                    "windows_paths.py",
                    (
                        "from pathlib import Path\n"
                        f"Path('opaque').{method}()\n"
                    ),
                )
                self.assertIn(
                    ("forbidden-attribute-call", method),
                    violations,
                )
        aliased_reader = _source_policy_violations(
            "windows_paths.py",
            (
                "from pathlib import Path\n"
                "reader = Path('opaque').read_text\n"
                "reader()\n"
            ),
        )
        self.assertIn(
            ("forbidden-attribute-reference", "read_text"),
            aliased_reader,
        )
        ambient_path_reader = _source_policy_violations(
            "windows_paths.py",
            (
                "from pathlib import Path\n"
                "entries = Path('opaque').iterdir\n"
            ),
        )
        self.assertIn(
            ("forbidden-attribute-reference", "iterdir"),
            ambient_path_reader,
        )
        aliased_path_mutator = _source_policy_violations(
            "windows_paths.py",
            (
                "from pathlib import Path\n"
                "linker = Path('opaque').symlink_to\n"
            ),
        )
        self.assertIn(
            ("forbidden-attribute-reference", "symlink_to"),
            aliased_path_mutator,
        )

        for suffix in (".cmd", ".ps1", ".bat", ".sh"):
            self.assertTrue(
                _is_root_wrapper(ROOT / f"mutant{suffix}", ROOT)
            )
        self.assertTrue(
            _is_root_consumer_file(ROOT / "mutant.py", ROOT)
        )
        self.assertTrue(
            _text_consumes_preflight(
                "python -m backend.real_host_preflight"
            )
        )
        self.assertTrue(
            _python_consumes_preflight(
                "from backend import real_host_preflight\n"
            )
        )
        self.assertTrue(
            _python_consumes_preflight(
                "__import__('backend.real_host_preflight')\n"
            )
        )
        self.assertTrue(
            _python_consumes_preflight(
                "from backend.real_host_preflight.composition "
                "import prepare_final_audit_composition\n"
            )
        )

    def test_package_and_public_surface_are_exact(self) -> None:
        files = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.relative_to(PACKAGE).parts
        }
        self.assertEqual(files, EXPECTED_FILES)
        self.assertEqual(set(ALLOWED_IMPORTS_BY_FILE), EXPECTED_FILES)
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
            imports = _canonical_imports(path)
            prior_layers = imports & ALLOWED_ABSOLUTE_IMPORTS
            self.assertEqual(prior_layers, expected.get(path.name, set()), path)
            self.assertFalse(
                {
                    item
                    for item in imports
                    if item.startswith("backend.")
                    and not item.startswith(f"{PACKAGE_MODULE}.")
                    and item not in ALLOWED_ABSOLUTE_IMPORTS
                },
                path,
            )

    def test_package_has_no_mutation_or_ambient_host_capability(self) -> None:
        for path in sorted(PACKAGE.glob("*.py")):
            source = path.read_text(encoding="utf-8")
            imports = _canonical_imports_from_source(path.name, source)[0]
            self.assertEqual(
                imports,
                ALLOWED_IMPORTS_BY_FILE[path.name],
                path,
            )
            self.assertEqual(
                _source_policy_violations(path.name, source),
                set(),
                path,
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
        candidates.extend(
            path
            for path in ROOT.iterdir()
            if path.is_file() and _is_root_consumer_file(path, ROOT)
        )
        workflows = ROOT / ".github" / "workflows"
        if workflows.exists():
            candidates.extend(path for path in workflows.rglob("*") if path.is_file())
        violations = []
        generator = (ROOT / "scripts" / "generate_project_status.py").resolve()
        for path in candidates:
            source = path.read_text(encoding="utf-8", errors="ignore")
            if path.resolve() == generator:
                consumed = _python_consumes_preflight(source)
            else:
                consumed = _text_consumes_preflight(source)
            if consumed:
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])
        self.assertEqual(
            tuple(
                inspect.signature(
                    preflight.real_host_preflight_operator_entry
                ).parameters
            ),
            (),
        )

    def test_test_sandbox_and_receipt_issuers_have_exact_consumers(
        self,
    ) -> None:
        expected = {
            "_issue_test_sandbox_permit": {
                "backend/real_host_preflight/windows_observation.py",
                "tests/test_real_host_preflight_windows.py",
                "tests/test_real_host_preflight_windows_composition.py",
            },
            "_mint_current_topology_receipt": {
                "backend/real_host_preflight/receipts.py",
                "backend/real_host_preflight/topology.py",
                "tests/test_real_host_preflight_gate.py",
            },
            "_mint_pre_mutation_gate_receipt": {
                "backend/real_host_preflight/mutation_gate.py",
                "backend/real_host_preflight/receipts.py",
            },
            "_mint_final_audit_ready_receipt": {
                "backend/real_host_preflight/composition.py",
                "backend/real_host_preflight/receipts.py",
            },
            "_claim_current_topology_receipt": {
                "backend/real_host_preflight/mutation_gate.py",
                "backend/real_host_preflight/receipts.py",
            },
        }
        candidates = tuple(ROOT.rglob("*.py"))
        for marker, allowed in expected.items():
            consumers = {
                path.relative_to(ROOT).as_posix()
                for path in candidates
                if path.resolve() != Path(__file__).resolve()
                if marker in path.read_text(encoding="utf-8")
            }
            self.assertEqual(consumers, allowed, marker)


def _canonical_imports(path: Path) -> set[str]:
    return _canonical_imports_from_source(
        path.name,
        path.read_text(encoding="utf-8"),
    )[0]


def _canonical_imports_from_source(
    filename: str,
    source: str,
) -> tuple[set[str], set[str]]:
    tree = ast.parse(source)
    imports: set[str] = set()
    escapes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            targets = _canonical_from_import(filename, node)
            imports.update(targets)
            if node.level:
                escapes.update(
                    target
                    for target in targets
                    if target != PACKAGE_MODULE
                    and not target.startswith(f"{PACKAGE_MODULE}.")
                )
    return imports, escapes


def _canonical_from_import(
    filename: str,
    node: ast.ImportFrom,
) -> set[str]:
    if node.level == 0:
        return {node.module} if node.module else set()
    module_name = (
        PACKAGE_MODULE
        if filename == "__init__.py"
        else f"{PACKAGE_MODULE}.{Path(filename).stem}"
    )
    package = module_name.split(".")
    if filename != "__init__.py":
        package = package[:-1]
    up = node.level - 1
    base = package[: max(0, len(package) - up)]
    if node.module:
        return {".".join((*base, *node.module.split(".")))}
    return {
        ".".join((*base, alias.name))
        for alias in node.names
        if alias.name != "*"
    }


def _source_policy_violations(
    filename: str,
    source: str,
) -> set[tuple[str, str]]:
    imports, escapes = _canonical_imports_from_source(filename, source)
    expected = ALLOWED_IMPORTS_BY_FILE[filename]
    violations = {
        ("unexpected-import", item)
        for item in imports
        if item not in expected
    }
    violations.update(
        ("relative-import-escape", item) for item in escapes
    )
    for module, allowed_files in SENSITIVE_IMPORT_FILES.items():
        if module in imports and filename not in allowed_files:
            violations.add(("sensitive-import", module))
    for module, name in _from_import_entries(filename, source):
        if (
            module in SENSITIVE_FROM_NAMES
            and name not in SENSITIVE_FROM_NAMES[module]
        ):
            violations.add(
                ("unexpected-import-name", f"{module}:{name}")
            )
        if (
            module.startswith(f"{PACKAGE_MODULE}.")
            and name.startswith("_")
            and name
            not in ALLOWED_PRIVATE_IMPORTS.get((filename, module), set())
        ):
            violations.add(
                ("unexpected-private-import", f"{module}:{name}")
            )
    roots = {item.split(".", 1)[0] for item in imports}
    violations.update(
        ("forbidden-import", item)
        for item in roots & FORBIDDEN_IMPORT_ROOTS
    )
    violations.update(_import_form_violations(filename, source))
    violations.update(_forbidden_call_violations(source))
    return violations


def _import_form_violations(
    filename: str,
    source: str,
) -> set[tuple[str, str]]:
    violations: set[tuple[str, str]] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in SENSITIVE_IMPORT_FORMS and (
                    SENSITIVE_IMPORT_FORMS[alias.name] != "import"
                ):
                    violations.add(
                        ("unexpected-import-form", f"{alias.name}:import")
                    )
                if _is_internal_module(alias.name):
                    violations.add(
                        ("internal-import-form", alias.name)
                    )
        elif isinstance(node, ast.ImportFrom):
            targets = _canonical_from_import(filename, node)
            if any(alias.name == "*" for alias in node.names):
                wildcard_targets = targets or {PACKAGE_MODULE}
                violations.update(
                    ("wildcard-import", f"{target}:*")
                    for target in wildcard_targets
                )
            for target in targets:
                if target in SENSITIVE_IMPORT_FORMS and (
                    SENSITIVE_IMPORT_FORMS[target] != "from"
                ):
                    violations.add(
                        ("unexpected-import-form", f"{target}:from")
                    )
                if _is_internal_module(target) and (
                    node.level != 1 or not node.module
                ):
                    violations.add(
                        ("internal-import-form", target)
                    )
    return violations


def _is_internal_module(value: str) -> bool:
    return value == PACKAGE_MODULE or value.startswith(
        f"{PACKAGE_MODULE}."
    )


def _from_import_entries(
    filename: str,
    source: str,
) -> set[tuple[str, str]]:
    entries: set[tuple[str, str]] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.ImportFrom):
            continue
        targets = _canonical_from_import(filename, node)
        if node.module and len(targets) == 1:
            module = next(iter(targets))
            entries.update((module, alias.name) for alias in node.names)
    return entries


def _forbidden_call_violations(source: str) -> set[tuple[str, str]]:
    tree = ast.parse(source)
    violations: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALL_NAMES
        ):
            violations.add(("forbidden-call", node.func.id))
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in FORBIDDEN_CALL_ATTRIBUTES
        ):
            violations.add(
                ("forbidden-attribute-call", node.func.attr)
            )
    violations.update(
        ("forbidden-attribute-reference", node.attr)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in FORBIDDEN_PATH_CAPABILITY_ATTRIBUTES
    )
    return violations


def _is_root_wrapper(path: Path, root: Path) -> bool:
    return (
        path.parent == root
        and path.suffix.lower() in {".cmd", ".ps1", ".bat", ".sh"}
    )


def _is_root_consumer_file(path: Path, root: Path) -> bool:
    return _is_root_wrapper(path, root) or (
        path.parent == root and path.suffix.lower() == ".py"
    )


def _text_consumes_preflight(source: str) -> bool:
    return "real_host_preflight" in source


def _python_consumes_preflight(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == PACKAGE_MODULE
            or alias.name.startswith(f"{PACKAGE_MODULE}.")
            for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and (
            node.module == PACKAGE_MODULE
            or (
                node.module is not None
                and node.module.startswith(f"{PACKAGE_MODULE}.")
            )
            or (
                node.module == "backend"
                and any(
                    alias.name == "real_host_preflight"
                    for alias in node.names
                )
            )
        ):
            return True
        if isinstance(node, ast.Call) and any(
            isinstance(argument, ast.Constant)
            and type(argument.value) is str
            and (
                argument.value == PACKAGE_MODULE
                or argument.value.startswith(f"{PACKAGE_MODULE}.")
            )
            for argument in node.args
        ):
            return True
    return False


if __name__ == "__main__":
    unittest.main()
