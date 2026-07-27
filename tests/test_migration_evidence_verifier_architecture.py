"""Mechanical capability guards for the read-only verifier process."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "migration_evidence_verifier"
EXPECTED_FILES = {
    "__init__.py", "bridge.py", "canonical.py", "contracts.py",
    "package_read.py", "process.py", "process_tree.py", "worker.py",
}
CORE_OPERATIONS = {
    "create_migration_evidence_package", "prepare_migration_evidence_review",
    "publish_new_package", "verify_migration_evidence_package",
    "verify_migration_evidence_payload",
}
PASSTHROUGH_ENV_KEYS = {
    "COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "SystemRoot",
    "TEMP", "TMP", "TMPDIR", "WINDIR",
}
FIXED_ENV_KEYS = {
    "LANG", "LC_ALL", "PYTHONDONTWRITEBYTECODE",
    "PYTHONHASHSEED", "PYTHONIOENCODING",
}


def python_paths() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE.glob("*.py")))


def tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree(path)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.add("." * node.level + (node.module or ""))
            elif node.module:
                modules.add(node.module)
    return modules


def called_names(path: Path) -> set[str]:
    values: set[str] = set()
    for node in ast.walk(tree(path)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            values.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            values.add(node.func.attr)
    return values


def qualified_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def call_paths(path: Path) -> set[str]:
    return {
        qualified_name(node.func)
        for node in ast.walk(tree(path))
        if isinstance(node, ast.Call)
    }


class MigrationEvidenceVerifierArchitectureTests(unittest.TestCase):
    def test_exact_files_and_single_public_core_bridge(self) -> None:
        paths = python_paths()
        self.assertEqual(
            {path.name for path in paths},
            EXPECTED_FILES,
        )
        consumers = {
            path.name
            for path in paths
            if any(
                module == "backend.migration_evidence"
                or module.startswith("backend.migration_evidence.")
                for module in imported_modules(path)
            )
        }
        self.assertEqual(consumers, {"bridge.py"})

        bridge_tree = tree(PACKAGE / "bridge.py")
        payload_imports = [
            node
            for node in ast.walk(bridge_tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "backend.migration_evidence.verification"
        ]
        self.assertEqual(len(payload_imports), 1)
        self.assertEqual(
            {alias.name for alias in payload_imports[0].names},
            {"verify_migration_evidence_payload"},
        )
        self.assertEqual(
            called_names(PACKAGE / "bridge.py") & CORE_OPERATIONS,
            {"verify_migration_evidence_payload"},
        )

    def test_runtime_bridge_import_does_not_load_creator_modules(
        self,
    ) -> None:
        code = (
            "import sys;"
            "from backend.migration_evidence_verifier.bridge "
            "import verify_existing_payload;"
            "verify_existing_payload(payload=b'invalid');"
            "forbidden={'backend.migration_evidence.package',"
            "'backend.migration_evidence.publication'};"
            "sys.stdout.write('isolated' if "
            "forbidden.isdisjoint(sys.modules) else 'loaded')"
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in PASSTHROUGH_ENV_KEYS
        }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        completed = subprocess.run(
            (sys.executable, "-B", "-c", code),
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "isolated")
        self.assertEqual(completed.stderr, "")

    def test_package_has_no_publication_or_target_mutation_capability(
        self,
    ) -> None:
        forbidden_calls = {
            "chmod",
            "chown",
            "hardlink_to",
            "link",
            "mkdir",
            "remove",
            "rename",
            "replace",
            "rmdir",
            "rmtree",
            "symlink_to",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
        writes: set[tuple[str, str]] = set()
        for path in python_paths():
            with self.subTest(path=path.name):
                modules = imported_modules(path)
                self.assertFalse(
                    any(
                        module.startswith(
                            "backend.migration_evidence_publication"
                        )
                        for module in modules
                    )
                )
                self.assertTrue(
                    called_names(path).isdisjoint(forbidden_calls)
                )
                writes.update(
                    (path.name, call)
                    for call in call_paths(path)
                    if call.endswith(".write")
                )
        self.assertEqual(
            writes,
            {
                ("process.py", "process.stdin.write"),
                ("worker.py", "sys.stdout.buffer.write"),
            },
        )
        reader = (PACKAGE / "package_read.py").read_text("utf-8")
        self.assertIn("os.O_RDONLY", reader)
        for flag in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC"):
            self.assertNotIn(flag, reader)
        self.assertIn('zipfile.ZipFile(io.BytesIO(payload), "r")', reader)
        opens = {
            (path.name, call)
            for path in python_paths()
            for call in call_paths(path)
            if call == "open" or call.endswith(".open")
        }
        self.assertEqual(
            opens,
            {("package_read.py", "os.open")},
        )

    def test_worker_is_fixed_sanitized_bounded_and_tree_owned(self) -> None:
        from backend.migration_evidence_verifier import process, worker

        process_tree = tree(PACKAGE / "process.py")
        popen_calls = [
            node
            for node in ast.walk(process_tree)
            if isinstance(node, ast.Call)
            and qualified_name(node.func) == "subprocess.Popen"
        ]
        self.assertEqual(len(popen_calls), 1)
        popen = popen_calls[0]
        self.assertEqual(
            tuple(
                ast.unparse(item)
                for item in popen.args[0].elts
            ),
            (
                "sys.executable",
                "'-B'",
                "'-m'",
                "'backend.migration_evidence_verifier.worker'",
            ),
        )
        keywords = {
            item.arg: ast.unparse(item.value)
            for item in popen.keywords
            if item.arg is not None
        }
        self.assertEqual(keywords["shell"], "False")
        self.assertEqual(keywords["env"], "_worker_environment()")
        self.assertEqual(keywords["stderr"], "subprocess.DEVNULL")
        self.assertEqual(process._MAX_RESPONSE_BYTES, 4096)
        self.assertEqual(process._TIMEOUT_SECONDS, 30)
        self.assertEqual(worker._MAX_REQUEST_BYTES, 64 * 1024)
        self.assertIn("sys.stdin.buffer.read", call_paths(PACKAGE / "worker.py"))

        canaries = {
            "OPENAI_API_KEY": "provider-canary",
            "MAILBOX_PASSWORD": "mailbox-canary",
            "PYTHONPATH": "unreviewed-import-root",
            "GIT_DIR": "unreviewed-repository",
        }
        with mock.patch.dict(os.environ, canaries, clear=False):
            environment = process._worker_environment()
        self.assertTrue(set(environment).isdisjoint(canaries))
        self.assertLessEqual(
            set(environment),
            PASSTHROUGH_ENV_KEYS | FIXED_ENV_KEYS,
        )
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(environment["PYTHONHASHSEED"], "0")

        owner_calls = call_paths(PACKAGE / "process.py")
        self.assertTrue(
            {
                "ProcessTree.prepare",
                "process_tree.popen_options",
                "process_tree.attach",
                "process_tree.finish",
                "process_tree.terminate",
                "process.stdout.read",
                "threading.Timer",
            }.issubset(owner_calls)
        )
        owner = (PACKAGE / "process_tree.py").read_text("utf-8")
        for required in (
            "_CREATE_SUSPENDED",
            "_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
            "AssignProcessToJobObject",
            "NtResumeProcess",
            "start_new_session",
            "os.WNOWAIT",
            "os.killpg",
        ):
            self.assertIn(required, owner)


if __name__ == "__main__":
    unittest.main()
