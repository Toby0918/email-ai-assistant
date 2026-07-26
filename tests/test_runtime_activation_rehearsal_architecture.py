"""Mechanical isolation guards for the Issue #37 rehearsal."""

from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

from scripts.repo_utils import read_text

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "runtime_activation_rehearsal"
PACKAGE_FILES = {
    "__init__.py",
    "adapters.py",
    "artifact_checks.py",
    "artifact_evidence.py",
    "contract.py",
    "database_checks.py",
    "filesystem_checks.py",
    "lifecycle_checks.py",
    "policy.py",
    "rehearsal.py",
    "runtime_checks.py",
    "runtime_evidence.py",
    "service_checks.py",
    "service_evidence.py",
    "service_validation.py",
}
PACKAGE_MODULE = "backend.runtime_activation_rehearsal"
ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "hashlib",
    "re",
    "typing",
    "uuid",
    *{
        f"{PACKAGE_MODULE}.{Path(name).stem}"
        for name in PACKAGE_FILES
        if name != "__init__.py"
    },
}
FORBIDDEN_CAPABILITY_NAMES = {
    "cleanup",
    "copy_signing_material",
    "delete",
    "move",
    "prune",
    "remove",
    "rename",
    "replace_target",
    "rmtree",
    "unlink",
}
FORBIDDEN_BARE_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "input",
    "open",
    "print",
}
FORBIDDEN_HOST_ATTRIBUTES = {
    "chmod",
    "chown",
    "connect",
    "cursor",
    "execute",
    "getenv",
    "glob",
    "iterdir",
    "lstat",
    "mkdir",
    "open",
    "popen",
    "read",
    "read_bytes",
    "read_text",
    "recv",
    "remove",
    "rename",
    "replace",
    "rglob",
    "rmdir",
    "rmtree",
    "send",
    "stat",
    "system",
    "touch",
    "truncate",
    "unlink",
    "urlopen",
    "walk",
    "write",
    "write_bytes",
    "write_text",
}


class RuntimeActivationRehearsalArchitectureTests(unittest.TestCase):
    def test_package_has_exact_files_and_no_host_imports(self) -> None:
        paths = tuple(sorted(PACKAGE.rglob("*.py")))

        self.assertEqual(
            {path.relative_to(PACKAGE).as_posix() for path in paths},
            PACKAGE_FILES,
        )
        for path in paths:
            with self.subTest(path=path.name):
                imports = _import_modules(path)
                self.assertLessEqual(imports, ALLOWED_IMPORTS)

    def test_package_has_no_destructive_or_signing_capability(self) -> None:
        for path in sorted(PACKAGE.rglob("*.py")):
            tree = ast.parse(read_text(path))
            names = {
                node.id.lower()
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
            } | {
                node.attr.lower()
                for node in ast.walk(tree)
                if isinstance(node, ast.Attribute)
            }
            with self.subTest(path=path.name):
                self.assertTrue(
                    names.isdisjoint(FORBIDDEN_CAPABILITY_NAMES)
                )
                self.assertEqual(_forbidden_host_capabilities(tree), set())
                self.assertNotRegex(
                    read_text(path).lower(),
                    r"\b(?:pem|pfx|private[_-]?key|certificate)\b",
                )

    def test_host_capability_guard_detects_unreviewed_access(self) -> None:
        samples = {
            "import ftplib\n": {"ftplib"},
            "import winreg\n": {"winreg"},
            "from pathlib import Path\n": {"pathlib"},
        }
        for source, unexpected in samples.items():
            with self.subTest(source=source):
                imports = _import_modules_from_tree(
                    ast.parse(source),
                    PACKAGE / "rehearsal.py",
                )
                self.assertEqual(imports - ALLOWED_IMPORTS, unexpected)

        for source, capability in (
            ("open('target')\n", "open"),
            ("target.write('value')\n", "write"),
            ("target.connect()\n", "connect"),
        ):
            with self.subTest(source=source):
                self.assertIn(
                    capability,
                    _forbidden_host_capabilities(ast.parse(source)),
                )

    def test_rehearsal_has_no_host_consumer(self) -> None:
        references: list[str] = []
        for path in _host_surface_files():
            text = read_text(path)
            if path.suffix == ".py":
                modules = _import_modules(path)
                tree = ast.parse(text)
                from_backend = any(
                    isinstance(node, ast.ImportFrom)
                    and node.module == "backend"
                    and any(
                        alias.name == "runtime_activation_rehearsal"
                        for alias in node.names
                    )
                    for node in ast.walk(tree)
                )
                called = any(
                    isinstance(node, ast.Call)
                    and (
                        isinstance(node.func, ast.Name)
                        and node.func.id
                        == "rehearse_managed_runtime_activation"
                        or isinstance(node.func, ast.Attribute)
                        and node.func.attr
                        == "rehearse_managed_runtime_activation"
                    )
                    for node in ast.walk(tree)
                )
                consumes = from_backend or called or any(
                    module == "backend.runtime_activation_rehearsal"
                    or module.startswith(
                        "backend.runtime_activation_rehearsal."
                    )
                    for module in modules
                )
            else:
                consumes = re.search(
                    r"\bruntime[_-]activation[_-]rehearsal\b"
                    r"|\brehearse_managed_runtime_activation\b",
                    text,
                    re.IGNORECASE,
                ) is not None
            if consumes:
                references.append(path.relative_to(ROOT).as_posix())

        self.assertEqual(references, [])

    def test_consumer_candidates_cover_every_host_surface(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "backend" / "runtime_activation_rehearsal"
            paths = (
                package / "__init__.py",
                root / "backend" / "service.py",
                root / "scripts" / "tool.py",
                root / "frontend" / "extension.js",
                root / ".github" / "workflows" / "guard.yml",
                root / "start.cmd",
                root / "start.bat",
                root / "start.ps1",
                root / "start.sh",
                root / "root_tool.py",
            )
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")

            candidates = _host_surface_files(root, package)

        self.assertEqual(
            {path.relative_to(root).as_posix() for path in candidates},
            {
                ".github/workflows/guard.yml",
                "backend/service.py",
                "frontend/extension.js",
                "root_tool.py",
                "scripts/tool.py",
                "start.bat",
                "start.cmd",
                "start.ps1",
                "start.sh",
            },
        )

    def test_architecture_document_records_synthetic_only_seam(
        self,
    ) -> None:
        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )

        self.assertIn("runtime_activation_rehearsal", architecture)
        self.assertIn(
            "rehearse_managed_runtime_activation(*, adapters=...)",
            architecture,
        )
        self.assertIn("no default host adapter", architecture)


def _import_modules(path: Path) -> set[str]:
    return _import_modules_from_tree(ast.parse(read_text(path)), path)


def _import_modules_from_tree(tree: ast.AST, path: Path) -> set[str]:
    relative = path.resolve().relative_to(ROOT.resolve())
    package_parts = list(relative.parent.parts)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    modules.add(node.module)
                continue
            retained = len(package_parts) - (node.level - 1)
            prefix = package_parts[:retained]
            suffix = node.module.split(".") if node.module else []
            modules.add(".".join((*prefix, *suffix)))
    return modules


def _forbidden_host_capabilities(tree: ast.AST) -> set[str]:
    bare_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in FORBIDDEN_BARE_CALLS
    }
    attributes = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in FORBIDDEN_HOST_ATTRIBUTES
    }
    return bare_calls | attributes


def _host_surface_files(
    root: Path = ROOT,
    package: Path = PACKAGE,
) -> tuple[Path, ...]:
    roots = (
        root / "backend",
        root / "scripts",
        root / "frontend",
        root / ".github" / "workflows",
    )
    resolved_package = package.resolve()
    paths = tuple(
        path
        for root in roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and not path.resolve().is_relative_to(resolved_package)
        and path.suffix.lower()
        in {
            ".py",
            ".js",
            ".json",
            ".yml",
            ".yaml",
            ".cmd",
            ".bat",
            ".ps1",
            ".sh",
        }
    )
    wrappers = tuple(
        path
        for path in root.iterdir()
        if path.is_file()
        and path.suffix.lower()
        in {".cmd", ".bat", ".ps1", ".py", ".sh"}
    )
    return tuple(sorted((*paths, *wrappers)))


if __name__ == "__main__":
    unittest.main()
