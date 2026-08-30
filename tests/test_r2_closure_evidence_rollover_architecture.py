"""Architecture guards for the closure evidence rollover maintenance seam."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import backend.r2_closure_evidence_rollover as public
from backend.r2_closure_evidence_rollover import ClosureEvidenceRollover
from scripts import rollover_r2_solo_maintainer_closure as cli


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend/r2_closure_evidence_rollover"


class ClosureEvidenceRolloverArchitectureTests(unittest.TestCase):
    def test_public_surface_and_package_files_are_exact(self) -> None:
        self.assertEqual(
            set(public.__all__),
            {
                "ClosureEvidenceRollover",
                "ClosureEvidenceRolloverCandidateV1",
                "ClosureEvidenceRolloverError",
                "ClosureEvidenceRolloverReceiptV1",
                "RolloverErrorCode",
            },
        )
        self.assertEqual(
            {item.name for item in PACKAGE.iterdir() if item.is_file()},
            {"__init__.py", "contracts.py", "repository.py", "storage.py", "rollover.py"},
        )
        self.assertEqual(tuple(inspect.signature(ClosureEvidenceRollover).parameters), ())
        self.assertEqual(
            tuple(inspect.signature(ClosureEvidenceRollover.prepare).parameters), ("self",)
        )
        self.assertEqual(
            tuple(inspect.signature(ClosureEvidenceRollover.execute).parameters),
            ("self", "exact_candidate_fingerprint"),
        )

    def test_package_respects_file_and_function_shape_limits(self) -> None:
        for path in PACKAGE.glob("*.py"):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path.name)
            tree = ast.parse("\n".join(lines), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertLessEqual(
                        node.end_lineno - node.lineno + 1, 50, f"{path.name}:{node.name}"
                    )

    def test_module_has_no_issue39_runtime_or_broad_capability_import(self) -> None:
        banned_roots = {
            "backend.r2_issue39_orchestrator",
            "backend.r2_issue39_enablement",
            "backend.r2_real_host_cutover",
            "backend.email_agent",
            "frontend",
            "requests",
            "urllib",
            "shutil",
            "sqlite3",
        }
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
            self.assertFalse(
                any(
                    name == banned or name.startswith(banned + ".")
                    for name in imported
                    for banned in banned_roots
                ),
                path.name,
            )

    def test_only_fixed_cli_consumes_rollover_package(self) -> None:
        consumers = set()
        for path in (*((ROOT / "backend").rglob("*.py")), *((ROOT / "scripts").glob("*.py"))):
            if path.is_relative_to(PACKAGE):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            if any(name == "backend.r2_closure_evidence_rollover" or name.startswith(
                "backend.r2_closure_evidence_rollover."
            ) for name in imports):
                consumers.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, {"scripts/rollover_r2_solo_maintainer_closure.py"})

    def test_storage_has_no_copy_delete_overwrite_or_repair_calls(self) -> None:
        path = PACKAGE / "storage.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        banned = {"copy", "copy2", "copyfile", "unlink", "remove", "rmdir", "rmtree", "replace"}
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        calls.update(
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        )
        self.assertTrue(calls.isdisjoint(banned), calls & banned)

    def test_native_primitives_remain_behind_storage_boundary(self) -> None:
        repository = (PACKAGE / "repository.py").read_text(encoding="utf-8")
        storage = (PACKAGE / "storage.py").read_text(encoding="utf-8")
        self.assertNotIn("r2_solo_maintainer_closure.storage", repository)
        self.assertIn("r2_solo_maintainer_closure.storage", storage)

    def test_cli_has_one_fixed_verb_and_forwards_its_own_candidate(self) -> None:
        candidate = SimpleNamespace(
            candidate_fingerprint="a" * 64,
            to_canonical_json=lambda: b'{"candidate":"synthetic"}',
        )
        receipt = SimpleNamespace(to_canonical_json=lambda: b'{"receipt":"synthetic"}')
        rollover = SimpleNamespace(
            prepare=lambda: candidate,
            execute=lambda supplied: receipt if supplied == "a" * 64 else None,
        )
        with patch.object(cli, "ClosureEvidenceRollover", return_value=rollover), patch.object(
            cli.sys, "argv", ["rollover_r2_solo_maintainer_closure.py", "run"]
        ), patch.object(cli.sys, "stdout") as stdout, patch.object(cli.sys, "stderr") as stderr:
            self.assertEqual(cli.main(), 0)
        self.assertEqual(cli.VERBS, ("run",))
        stderr.write.assert_called_once_with('{"candidate":"synthetic"}\n')
        stdout.write.assert_called_once_with('{"receipt":"synthetic"}\n')

    def test_existing_closure_package_remains_exactly_ten_files(self) -> None:
        package = ROOT / "backend/r2_solo_maintainer_closure"
        self.assertEqual(len([item for item in package.iterdir() if item.is_file()]), 10)


if __name__ == "__main__":
    unittest.main()
