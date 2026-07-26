from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from backend.reparenting_rehearsal import (
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
)
from backend.reparenting_rehearsal.baseline import (
    capture_repository_baseline,
    directory_identity,
)
from backend.reparenting_rehearsal.evidence_bridge import (
    prepare_synthetic_evidence,
)
from backend.reparenting_rehearsal.errors import RehearsalError
from backend.reparenting_rehearsal.git_runner import git_output
from backend.reparenting_rehearsal.publication import (
    publish_container,
    publish_legacy_source,
    publish_main_repository,
)
from backend.reparenting_rehearsal.rehearsal import _run_rehearsal
from backend.reparenting_rehearsal.synthetic_project import (
    build_synthetic_project,
)
from backend.reparenting_rehearsal.worktrees import publish_worktrees


RECREATE_CHOICES = tuple(
    ReviewedWorktreeChoice(item, WorktreeStrategy.RECREATE)
    for item in SyntheticWorktree
)


class ReparentingRehearsalDriftTests(unittest.TestCase):
    def test_remote_drift_during_review_capture_is_rejected(self) -> None:
        real_prepare = prepare_synthetic_evidence

        def drift_then_prepare(project):
            git_output(
                project.scope,
                project.source,
                (
                    "remote",
                    "set-url",
                    "origin",
                    "https://example.invalid/repository.git",
                ),
            )
            return real_prepare(project)

        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            with mock.patch(
                "backend.reparenting_rehearsal.rehearsal."
                "prepare_synthetic_evidence",
                side_effect=drift_then_prepare,
            ):
                with self.assertRaises(RehearsalError):
                    _run_rehearsal(
                        Path(temporary),
                        RECREATE_CHOICES,
                        None,
                    )

    @unittest.skipUnless(os.name == "nt", "Windows junction contract")
    def test_worktrees_parent_junction_is_rejected_before_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(Path(temporary))
            review = prepare_synthetic_evidence(project)
            baseline = capture_repository_baseline(project, review)
            publish_legacy_source(project)
            publish_container(project)
            repository = publish_main_repository(project, baseline)
            worktrees_root = repository.container / "Worktrees"
            preserved_root = repository.container / "Worktrees-original"
            worktrees_root.rename(preserved_root)
            outside = project.scope / "outside-worktrees"
            outside.mkdir()
            self._create_junction(worktrees_root, outside)
            originals = {
                item: directory_identity(project.old_worktree(item))
                for item in SyntheticWorktree
            }

            with self.assertRaises(RehearsalError):
                publish_worktrees(
                    project=project,
                    repository=repository,
                    baseline=baseline,
                    choices=RECREATE_CHOICES,
                )

            self.assertEqual(tuple(outside.iterdir()), ())
            for item in SyntheticWorktree:
                self.assertEqual(
                    directory_identity(project.old_worktree(item)),
                    originals[item],
                )

    def _create_junction(self, junction: Path, target: Path) -> None:
        completed = subprocess.run(
            (
                os.environ.get("COMSPEC", "cmd.exe"),
                "/d",
                "/c",
                "mklink",
                "/J",
                str(junction),
                str(target),
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stderr.decode(errors="replace"),
        )


if __name__ == "__main__":
    unittest.main()
