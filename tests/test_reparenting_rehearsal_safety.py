from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from backend.migration_evidence.snapshot import read_checked_file
from backend.reparenting_rehearsal import (
    PublicationBoundary,
    ReparentingStatus,
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
    rehearse_repository_reparenting,
)
from backend.reparenting_rehearsal.baseline import (
    capture_repository_baseline,
    directory_identity,
)
from backend.reparenting_rehearsal.evidence_bridge import (
    create_and_verify_synthetic_evidence,
    prepare_synthetic_evidence,
)
from backend.reparenting_rehearsal.errors import RehearsalError
from backend.reparenting_rehearsal.publication import (
    publish_container,
    publish_legacy_source,
    publish_main_repository,
)
from backend.reparenting_rehearsal.synthetic_project import (
    EXCLUDED_PATHS,
    REVIEWED_DIRTY,
    build_synthetic_project,
    require_synthetic_project,
)
from backend.reparenting_rehearsal.rehearsal import _run_rehearsal
from backend.reparenting_rehearsal.worktrees import publish_worktrees
from backend.reparenting_rehearsal.git_runner import git_output
from backend.reparenting_rehearsal.synthetic_scope import (
    MARKER_NAME,
    MARKER_VALUE,
    prepare_synthetic_scope,
    require_synthetic_scope,
)


class ReparentingRehearsalSafetyTests(unittest.TestCase):
    def test_baseline_is_nontrivial_and_complete(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(
                Path(temporary).resolve()
            )
            review = prepare_synthetic_evidence(project)
            baseline = capture_repository_baseline(project, review)

            self.assertEqual(review.git_baseline.ahead, 1)
            self.assertEqual(review.git_baseline.behind, 0)
            self.assertEqual(len(review.git_baseline.remotes), 1)
            self.assertEqual(len(review.reviewed_refs), 3)
            self.assertEqual(len(review.worktrees), 3)
            self.assertEqual(len(baseline.linked_worktrees), 2)
            self.assertTrue(
                all(item.status_count == 0 for item in review.worktrees[1:])
            )
            self.assertEqual(
                {
                    item.path
                    for item in review.dirty_entries
                    if item.disposition.value == "included"
                },
                set(REVIEWED_DIRTY),
            )
            self.assertLessEqual(
                set(EXCLUDED_PATHS),
                {item.path for item in review.dirty_entries},
            )

    def test_evidence_snapshot_opens_only_reviewed_dirty_source(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(
                Path(temporary).resolve()
            )
            review = prepare_synthetic_evidence(project)

            with mock.patch(
                "backend.migration_evidence.snapshot.read_checked_file",
                wraps=read_checked_file,
            ) as checked_read:
                create_and_verify_synthetic_evidence(review)

            opened = {call.args[1] for call in checked_read.call_args_list}
            self.assertEqual(opened, set(REVIEWED_DIRTY))
            self.assertTrue(set(EXCLUDED_PATHS).isdisjoint(opened))

    def test_existing_legacy_target_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(
                Path(temporary).resolve()
            )
            source_identity = directory_identity(project.source)
            project.legacy.mkdir()

            with self.assertRaises(RehearsalError):
                publish_legacy_source(project)

            self.assertEqual(
                directory_identity(project.source),
                source_identity,
            )
            self.assertTrue(project.legacy.is_dir())
            self.assertEqual(tuple(project.legacy.iterdir()), ())

    def test_marker_identity_drift_blocks_publication(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(
                Path(temporary).resolve()
            )
            source_identity = directory_identity(project.source)
            marker = project.scope / MARKER_NAME
            marker.unlink()
            marker.write_text(
                MARKER_VALUE,
                encoding="utf-8",
                newline="\n",
            )

            with self.assertRaises(RehearsalError):
                publish_legacy_source(project)

            self.assertEqual(
                directory_identity(project.source),
                source_identity,
            )
            self.assertFalse(project.legacy.exists())

    def test_marker_reparse_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(
                Path(temporary).resolve()
            )
            original = (
                "backend.reparenting_rehearsal.synthetic_scope._is_reparse"
            )

            with mock.patch(original, return_value=True):
                with self.assertRaises(RehearsalError):
                    require_synthetic_scope(project.scope)

    def test_non_local_remote_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            project = build_synthetic_project(
                Path(temporary).resolve()
            )
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

            with self.assertRaises(RehearsalError):
                require_synthetic_project(project)

    def test_remote_drift_before_baseline_is_rejected_by_orchestration(
        self,
    ) -> None:
        real_builder = build_synthetic_project

        def drift_remote(scope: Path):
            project = real_builder(scope)
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
            return project

        choices = (
            ReviewedWorktreeChoice(
                SyntheticWorktree.ALPHA,
                WorktreeStrategy.REPAIR,
            ),
            ReviewedWorktreeChoice(
                SyntheticWorktree.BETA,
                WorktreeStrategy.RECREATE,
            ),
        )
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-"
        ) as temporary:
            with mock.patch(
                "backend.reparenting_rehearsal.rehearsal."
                "build_synthetic_project",
                side_effect=drift_remote,
            ):
                with self.assertRaises(RehearsalError):
                    _run_rehearsal(
                        Path(temporary),
                        choices,
                        PublicationBoundary.EVIDENCE_PACKAGE,
                    )

    def test_existing_recreate_target_fails_before_any_worktree_move(
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
            target = repository.container / "Worktrees" / "beta"
            target.mkdir()
            alpha = project.old_worktree(SyntheticWorktree.ALPHA)
            alpha_identity = directory_identity(alpha)

            with self.assertRaises(RehearsalError):
                publish_worktrees(
                    project=project,
                    repository=repository,
                    baseline=baseline,
                    choices=(
                        ReviewedWorktreeChoice(
                            SyntheticWorktree.ALPHA,
                            WorktreeStrategy.REPAIR,
                        ),
                        ReviewedWorktreeChoice(
                            SyntheticWorktree.BETA,
                            WorktreeStrategy.RECREATE,
                        ),
                    ),
                )

            self.assertEqual(directory_identity(alpha), alpha_identity)
            self.assertEqual(tuple(target.iterdir()), ())

    def test_non_canonical_temporary_scope_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="not-issue36-"
        ) as temporary:
            with self.assertRaises(RehearsalError):
                prepare_synthetic_scope(Path(temporary))

    def test_invalid_choice_set_fails_before_sandbox_creation(self) -> None:
        choices = (
            ReviewedWorktreeChoice(
                SyntheticWorktree.ALPHA,
                WorktreeStrategy.REPAIR,
            ),
            ReviewedWorktreeChoice(
                SyntheticWorktree.ALPHA,
                WorktreeStrategy.RECREATE,
            ),
        )
        with mock.patch(
            "backend.reparenting_rehearsal.rehearsal.tempfile.TemporaryDirectory"
        ) as temporary:
            result = rehearse_repository_reparenting(
                worktree_choices=choices,
                fail_at=None,
            )

        self.assertEqual(result.status, ReparentingStatus.FAILED)
        temporary.assert_not_called()


if __name__ == "__main__":
    unittest.main()
