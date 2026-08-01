"""Mechanical capability and leakage guards for Issue #56."""

from __future__ import annotations

import ast
import inspect
import types
import unittest
from pathlib import Path

import backend.cutover_repository_transaction as transaction

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "cutover_repository_transaction"
EXPECTED_FILES = {
    "__init__.py",
    "contracts.py",
    "container_audit_bridge.py",
    "durable_store.py",
    "errors.py",
    "failed_evidence.py",
    "forward.py",
    "forward_recovery.py",
    "git_inspection.py",
    "git_executable.py",
    "git_recreation.py",
    "git_runner.py",
    "issue52_bridge.py",
    "journal_chain.py",
    "journal_identity.py",
    "journal_record.py",
    "journal_types.py",
    "mutation_executor.py",
    "real_lock.py",
    "restart_classification.py",
    "reverse.py",
    "reverse_checkpoint.py",
    "reverse_plan.py",
    "reverse_resume.py",
    "scope_models.py",
    "scope_paths.py",
    "stable_observation.py",
    "synthetic_scope.py",
    "transaction.py",
    "transaction_types.py",
    "verification.py",
    "windows_identity.py",
}
EXPECTED_PUBLIC = {
    "ForwardBoundary",
    "RepositoryJournalDirection",
    "RepositoryJournalEvent",
    "RepositoryJournalOutcome",
    "RepositoryJournalRecordV1",
    "RepositoryMutationKind",
    "RepositoryTransactionReceiptV1",
    "RepositoryWorktreePlacement",
    "RestartClassification",
    "ReviewedWorktreeV1",
    "ReverseBoundary",
    "SyntheticCrashGap",
    "SyntheticFailureSelectorV1",
    "SyntheticRepositoryRosterV1",
    "SyntheticTransactionDirection",
    "classify_synthetic_restart",
    "locked_real_repository_transaction_constructor",
    "run_forward_synthetic_transaction",
    "run_reverse_synthetic_transaction",
}
FORBIDDEN_CALLS = {
    "copy",
    "copy2",
    "copyfile",
    "copytree",
    "rmtree",
    "unlink",
    "remove",
    "removedirs",
    "replace",
    "rename",
    "system",
    "popen",
    "print",
}
FORBIDDEN_GIT_WORDS = {
    "clone",
    "fetch",
    "reset",
    "stash",
    "prune",
    "repair",
}


class RepositoryTransactionArchitectureTests(unittest.TestCase):
    def test_exact_files_and_content_free_public_surface(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            EXPECTED_FILES,
        )
        self.assertEqual(set(transaction.__all__), EXPECTED_PUBLIC)
        self.assertEqual(
            {
                name
                for name, value in vars(transaction).items()
                if not name.startswith("_")
                and not isinstance(value, types.ModuleType)
            },
            EXPECTED_PUBLIC,
        )
        for entry in (
            transaction.run_forward_synthetic_transaction,
            transaction.run_reverse_synthetic_transaction,
        ):
            parameters = inspect.signature(entry).parameters
            self.assertEqual(
                tuple(parameters),
                ("scope", "failure_selector", "observed_at_epoch"),
            )
            self.assertFalse(
                {"path", "ref", "command", "repository"} & set(parameters)
            )

    def test_no_copy_delete_replace_or_forbidden_git_capability(self):
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            calls = {
                _call_name(node)
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
            }
            strings = {
                node.value.casefold()
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
            }
            with self.subTest(path=path.name):
                allowed_calls = {"popen"} if path.name == "git_runner.py" else set()
                self.assertFalse(
                    (FORBIDDEN_CALLS - allowed_calls) & calls
                )
                self.assertFalse(FORBIDDEN_GIT_WORDS & strings)

    def test_only_exact_internal_bridges_import_mutation_and_journal(self):
        mutation_importers = set()
        journal_importers = set()
        for path in PACKAGE.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "backend.cutover_host_mutation" in source:
                mutation_importers.add(path.name)
            if "backend.cutover_journal" in source:
                journal_importers.add(path.name)
        self.assertEqual(
            mutation_importers,
            {
                "git_runner.py",
                "issue52_bridge.py",
                "mutation_executor.py",
                "real_lock.py",
                "stable_observation.py",
                "windows_identity.py",
            },
        )
        self.assertEqual(journal_importers, {"issue52_bridge.py"})

    def test_only_exact_bridge_imports_container_audit_policy_seams(self):
        importers = set()
        for path in PACKAGE.glob("*.py"):
            if "backend.container_audit" in path.read_text("utf-8"):
                importers.add(path.name)
        self.assertEqual(importers, {"container_audit_bridge.py"})

    def test_no_normal_runtime_script_frontend_or_workflow_consumer(self):
        allowed_consumers = {
            "backend/r2_repository_manifest/host.py",
            "backend/r2_repository_manifest/recovery.py",
            "backend/r2_repository_manifest/review.py",
            "backend/r2_repository_manifest/testing.py",
            "backend/r2_repository_manifest/verification.py",
        }
        violations = []
        for root in (
            ROOT / "backend",
            ROOT / "scripts",
            ROOT / "frontend",
            ROOT / ".github" / "workflows",
        ):
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if (
                    not path.is_file()
                    or PACKAGE in path.parents
                    or path.name == "generate_project_status.py"
                    or path.suffix not in {
                        ".py", ".js", ".html", ".yml", ".yaml",
                    }
                ):
                    continue
                source = path.read_text(
                    encoding="utf-8", errors="ignore"
                )
                if "cutover_repository_transaction" in source:
                    violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(set(violations), allowed_consumers)

    def test_subprocess_is_one_fixed_sanitized_git_runner(self):
        importers = []
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            if any(
                isinstance(node, (ast.Import, ast.ImportFrom))
                and "subprocess" in ast.unparse(node)
                for node in ast.walk(tree)
            ):
                importers.append(path.name)
        self.assertEqual(importers, ["git_runner.py"])
        source = (PACKAGE / "git_runner.py").read_text("utf-8")
        self.assertIn("shell=False", source)
        self.assertIn("stdin=subprocess.DEVNULL", source)
        self.assertIn("GIT_CONFIG_NOSYSTEM", source)
        self.assertIn("GIT_TERMINAL_PROMPT", source)
        self.assertNotIn("def git_output", source)
        self.assertIn("ProcessTree", source)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id.casefold()
    if isinstance(node.func, ast.Attribute):
        return node.func.attr.casefold()
    return ""


if __name__ == "__main__":
    unittest.main()
