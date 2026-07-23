"""Tests for explicit temporary standalone operational state."""

from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.project_layout import DirectoryIdentity, PlacementError
from backend.email_agent.standalone_verification import (
    prepare_standalone_runtime,
)


ROOT = Path(__file__).resolve().parents[1]


class StandaloneVerificationTests(unittest.TestCase):
    def test_prepared_runtime_keeps_all_writable_paths_under_temporary_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)

            runtime = prepare_standalone_runtime(
                repository_root=ROOT,
                state_root=state_root,
            )

        self.assertEqual(
            runtime.database_path,
            state_root / "LocalData" / "email_agent.sqlite3",
        )
        self.assertEqual(
            runtime.attachment_temp_dir,
            state_root / "RuntimeTemp" / "attachment_temp",
        )
        self.assertEqual(
            runtime.log_file,
            state_root / "Logs" / "local_debug_service.log",
        )
        self.assertEqual(
            runtime.pid_file,
            state_root / "Logs" / "local_debug_service.pid",
        )
        self.assertEqual(runtime.config.llm_provider, "disabled")
        self.assertFalse(runtime.config.private_knowledge_enabled)

    def test_prepared_runtime_rejects_reparse_operational_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            reparse_path = state_root / "RuntimeTemp"

            def inspect_directory(path: Path) -> DirectoryIdentity:
                candidate = Path(path)
                return DirectoryIdentity(
                    canonical_path=candidate,
                    device=1,
                    inode=max(1, abs(hash(str(candidate)))),
                    has_reparse_component=candidate == reparse_path,
                )

            with self.assertRaisesRegex(
                PlacementError,
                "placement_reparse_forbidden",
            ):
                prepare_standalone_runtime(
                    repository_root=ROOT,
                    state_root=state_root,
                    inspect_directory=inspect_directory,
                )

    def test_prepared_runtime_rejects_reparse_writable_file_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)

            def inspect_directory(path: Path) -> DirectoryIdentity:
                candidate = Path(path)
                return DirectoryIdentity(
                    canonical_path=candidate,
                    device=1,
                    inode=max(1, abs(hash(str(candidate)))),
                )

            reparse_file = SimpleNamespace(
                st_mode=stat.S_IFLNK | 0o777,
                st_file_attributes=0,
            )
            with (
                patch.object(Path, "lstat", return_value=reparse_file),
                self.assertRaisesRegex(
                    PlacementError,
                    "placement_reparse_forbidden",
                ),
            ):
                prepare_standalone_runtime(
                    repository_root=ROOT,
                    state_root=state_root,
                    inspect_directory=inspect_directory,
                )


if __name__ == "__main__":
    unittest.main()
