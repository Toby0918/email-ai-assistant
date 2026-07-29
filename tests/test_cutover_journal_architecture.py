"""Issue #52 synthetic-only capability and public-surface guards."""

from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

import backend.cutover_journal as journal
from backend.cutover_journal import (
    inspect_restart,
    resume_synthetic,
    rollback_next_synthetic,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "cutover_journal"
EXPECTED_FILES = {
    "__init__.py",
    "_canonical.py",
    "action_common.py",
    "chain_reducer.py",
    "closed_classifier.py",
    "contracts_bridge.py",
    "durability.py",
    "effect_permit.py",
    "effect_guard.py",
    "effect_state.py",
    "errors.py",
    "journal_chain.py",
    "journal_record.py",
    "journal_store.py",
    "journal_types.py",
    "operation_binding.py",
    "pending_classifier.py",
    "record_schema.py",
    "recovery.py",
    "recovery_classifier.py",
    "recovery_types.py",
    "resume_actions.py",
    "rollback_actions.py",
    "store_support.py",
    "transaction.py",
}
EXPECTED_PUBLIC = {
    "DurabilityCutPoint",
    "DurabilityPlatform",
    "DurableJournalStore",
    "JournalContractError",
    "JournalDirection",
    "JournalEffectOutcome",
    "JournalEventCode",
    "JournalOperationBindingV1",
    "JournalOperationCountsV1",
    "JournalOperationPhase",
    "JournalOperationResultV1",
    "JournalOperationStatus",
    "JournalRecordV1",
    "JournalStepCode",
    "SyntheticEffectStateV1",
    "SyntheticJournalMediumV1",
    "SyntheticJournalTransaction",
    "TransactionCutPoint",
    "VerifiedJournalChainV1",
    "inspect_restart",
    "resume_synthetic",
    "rollback_next_synthetic",
    "verify_synthetic_journal_snapshot",
}
PACKAGE_MODULES = {Path(name).stem for name in EXPECTED_FILES}
STDLIB_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "hashlib",
    "json",
}
BRIDGE_SYMBOLS = {
    "AuthorizationValidationStatus",
    "CutoverExecutionAuthorizationV1",
    "CutoverProfileV1",
    "RecoveryAuthorizationV1",
    "validate_real_host_authorization",
}
FORBIDDEN_IMPORT_ROOTS = {
    "asyncio",
    "ctypes",
    "fcntl",
    "http",
    "importlib",
    "logging",
    "msvcrt",
    "os",
    "pathlib",
    "shutil",
    "socket",
    "sqlite3",
    "subprocess",
    "tempfile",
    "threading",
    "urllib",
}
FORBIDDEN_CALLS = {
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
FORBIDDEN_ATTRIBUTES = {
    "chmod",
    "connect",
    "cwd",
    "getenv",
    "lstat",
    "mkdir",
    "open",
    "read_bytes",
    "read_text",
    "rename",
    "replace",
    "resolve",
    "rmdir",
    "run",
    "stat",
    "system",
    "unlink",
    "write_bytes",
    "write_text",
}
FORBIDDEN_PARAMETER_PARTS = {
    "adapter",
    "callback",
    "command",
    "database",
    "filesystem",
    "mailbox",
    "path",
    "provider",
    "repository",
    "service",
    "sqlite",
    "vault",
    "worktree",
}


def _dynamic_import_aliases(tree: ast.AST) -> set[str]:
    aliases = {"__import__", "import_module"}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module in {"builtins", "importlib"}
        ):
            aliases.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in {"__import__", "import_module"}
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
            is_dynamic = (
                isinstance(value, ast.Name) and value.id in aliases
            ) or (
                isinstance(value, ast.Attribute)
                and value.attr in {"__import__", "import_module"}
            )
            if not is_dynamic:
                continue
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else (node.target,)
            )
            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id not in aliases
                ):
                    aliases.add(target.id)
                    changed = True
    return aliases


def _imports_cutover_journal(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name == "backend.cutover_journal"
            or alias.name.startswith("backend.cutover_journal.")
            for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (
                module == "backend.cutover_journal"
                or module.startswith("backend.cutover_journal.")
                or (
                    module == "backend"
                    and any(
                        alias.name == "cutover_journal"
                        for alias in node.names
                    )
                )
            ):
                return True
            if node.level > 0 and (
                module == "cutover_journal"
                or module.startswith("cutover_journal.")
                or any(
                    alias.name == "cutover_journal"
                    for alias in node.names
                )
            ):
                return True
    aliases = _dynamic_import_aliases(tree)
    return any(
        isinstance(node, ast.Call)
        and (
            isinstance(node.func, ast.Name)
            and node.func.id in aliases
            or isinstance(node.func, ast.Attribute)
            and node.func.attr in {"__import__", "import_module"}
        )
        for node in ast.walk(tree)
    )


class CutoverJournalArchitectureTests(unittest.TestCase):
    def test_files_and_public_exports_are_exact(self) -> None:
        files = {
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.relative_to(PACKAGE).parts
        }
        self.assertEqual(files, EXPECTED_FILES)
        self.assertEqual(set(journal.__all__), EXPECTED_PUBLIC)

    def test_imports_are_pure_and_bridge_is_the_only_contract_consumer(
        self,
    ) -> None:
        for path in _package_paths():
            relative = path.relative_to(PACKAGE).as_posix()
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    self.assertTrue(
                        all(
                            alias.name in STDLIB_IMPORTS
                            for alias in node.names
                        ),
                        (relative, ast.unparse(node)),
                    )
                elif isinstance(node, ast.ImportFrom):
                    self.assertTrue(
                        _allowed_import_from(relative, node),
                        (relative, ast.unparse(node)),
                    )

    def test_no_host_io_dynamic_access_or_callback_surface(self) -> None:
        for path in _package_paths():
            relative = path.relative_to(PACKAGE).as_posix()
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            loaded_names = {
                node.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
            }
            self.assertTrue(
                loaded_names.isdisjoint({"Protocol", "Callable"}),
                relative,
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    self.assertFalse(
                        _forbidden_call(node),
                        (relative, ast.unparse(node)),
                    )
                if isinstance(node, ast.Name) and isinstance(
                    node.ctx, ast.Load
                ):
                    self.assertNotIn(node.id, FORBIDDEN_CALLS, relative)

    def test_public_actions_accept_no_real_host_capability(self) -> None:
        expected = {
            inspect_restart: (
                "snapshot",
                "binding",
                "profile",
                "effect_snapshot",
                "resume_authorization",
                "recovery_authorization",
                "observed_at_epoch",
            ),
            resume_synthetic: (
                "store",
                "binding",
                "profile",
                "resume_authorization",
                "effect_state",
                "observed_at_epoch",
                "action_at_epoch",
                "cut_point",
            ),
            rollback_next_synthetic: (
                "store",
                "binding",
                "profile",
                "recovery_authorization",
                "effect_state",
                "observed_at_epoch",
                "action_at_epoch",
                "cut_point",
            ),
        }
        for function, parameters in expected.items():
            with self.subTest(function=function.__name__):
                actual = tuple(inspect.signature(function).parameters)
                self.assertEqual(actual, parameters)
                self.assertFalse(
                    any(
                        part in name
                        for name in actual
                        for part in FORBIDDEN_PARAMETER_PARTS
                    )
                )

    def test_no_backend_script_or_frontend_consumer_exists(self) -> None:
        allowed_consumers = {
            "backend/cutover_host_mutation/acl_journal.py",
            "backend/cutover_host_mutation/journal_intent.py",
        }
        violations = []
        for root_name in ("backend", "scripts", "frontend"):
            for path in (ROOT / root_name).rglob("*"):
                if (
                    not path.is_file()
                    or path.suffix not in {".py", ".js"}
                    or PACKAGE in path.parents
                ):
                    continue
                source = path.read_text(encoding="utf-8")
                imports_package = (
                    _imports_cutover_journal(source)
                    if path.suffix == ".py"
                    else (
                        "backend.cutover_journal" in source
                        or "backend/cutover_journal" in source
                    )
                )
                if imports_package:
                    violations.append(
                        path.relative_to(ROOT).as_posix()
                    )
        self.assertEqual(set(violations), allowed_consumers)

    def test_consumer_guard_recognizes_equivalent_imports(self) -> None:
        cases = (
            ("import backend.cutover_journal", True),
            ("from backend import cutover_journal", True),
            ("from . import cutover_journal", True),
            ("from ..cutover_journal import inspect_restart", True),
            ("from backend import email_agent", False),
            (
                "import importlib\n"
                "importlib.import_module('backend.' + 'cutover_journal')",
                True,
            ),
            (
                "from importlib import import_module as loader\n"
                "again = loader\nagain('backend.' + 'cutover_journal')",
                True,
            ),
            (
                "import builtins\n"
                "builtins.__import__('backend.' + 'cutover_journal')",
                True,
            ),
            (
                "import builtins\nloader = builtins.__import__\n"
                "loader('backend.' + 'cutover_journal')",
                True,
            ),
            (
                "from builtins import __import__ as loader\n"
                "loader('backend.' + 'cutover_journal')",
                True,
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    _imports_cutover_journal(source),
                    expected,
                )

    def test_files_and_functions_remain_bounded(self) -> None:
        for path in _package_paths():
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path)
            tree = ast.parse("\n".join(lines))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = node.end_lineno or node.lineno
                    self.assertLessEqual(
                        end - node.lineno + 1,
                        50,
                        (path, node.name),
                    )


def _package_paths() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE.glob("*.py")))


def _allowed_import_from(relative: str, node: ast.ImportFrom) -> bool:
    if node.level == 1:
        return (
            node.module in PACKAGE_MODULES
            and all(alias.name != "*" for alias in node.names)
        )
    if node.level != 0:
        return False
    if node.module == "backend.cutover_contracts":
        return (
            relative == "contracts_bridge.py"
            and {alias.name for alias in node.names} == BRIDGE_SYMBOLS
        )
    root = (node.module or "").split(".", 1)[0]
    return root in STDLIB_IMPORTS and root not in FORBIDDEN_IMPORT_ROOTS


def _forbidden_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in FORBIDDEN_CALLS
    if isinstance(node.func, ast.Attribute):
        return node.func.attr in FORBIDDEN_ATTRIBUTES
    return False


if __name__ == "__main__":
    unittest.main()
