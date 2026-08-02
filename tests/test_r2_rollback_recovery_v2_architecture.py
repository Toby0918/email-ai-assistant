"""Architecture guards for the dormant Issue #97 rollback package."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

import backend.r2_rollback_recovery_v2 as package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_rollback_recovery_v2"


class R2RollbackRecoveryV2ArchitectureTests(unittest.TestCase):
    def test_exact_files_exports_and_no_executable(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {"__init__.py", "errors.py", "plan.py", "evidence.py", "progress.py", "seal.py"},
        )
        self.assertFalse((PACKAGE / "__main__.py").exists())
        self.assertEqual(
            set(package.__all__),
            {
                "R2LegacyRestorationEvidenceV2",
                "R2RollbackEffectEvidenceV2",
                "R2RollbackPlanV2",
                "R2RollbackTransitionV2",
                "RollbackBoundaryV2",
                "RollbackProgressStatusV2",
                "RollbackProgressV2",
                "RollbackRecoveryError",
                "begin_next_rollback_action_v2",
                "classify_rollback_pending_v2",
                "commit_rollback_effect_v2",
                "resume_rollback_transition_v2",
                "seal_legacy_flat_layout_restored_v2",
            },
        )

    def test_package_is_pathless_content_free_and_has_no_cleanup_capability(self):
        forbidden = {
            "pathlib", "subprocess", "shutil", "sqlite3", "socket", "requests",
            "openai", "mailbox", "vault", "private_data", "unlink", "rmtree",
            "remove(", "delete(", "replace(", "cleanup", "retry",
        }
        source = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py"))
        lowered = source.lower()
        for token in forbidden:
            self.assertNotIn(token, lowered)

    def test_module_and_function_size_limits(self):
        for path in PACKAGE.glob("*.py"):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path.name)
            tree = ast.parse("\n".join(lines))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = getattr(node, "end_lineno", node.lineno)
                    self.assertLessEqual(end - node.lineno + 1, 50, f"{path.name}:{node.name}")

    def test_no_normal_runtime_or_script_consumer(self):
        consumers = []
        for root_name in ("backend", "frontend", "scripts"):
            for path in (ROOT / root_name).rglob("*.py"):
                if PACKAGE in path.parents:
                    continue
                text = path.read_text(encoding="utf-8")
                if "r2_rollback_recovery_v2" in text:
                    consumers.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
