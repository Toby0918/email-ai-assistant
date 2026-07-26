from __future__ import annotations

import hashlib
from pathlib import Path
import unittest

from backend.migration_evidence import (
    MigrationEvidenceStatus,
    verify_migration_evidence_package,
)
from backend.reparenting_rehearsal import (
    PublicationBoundary,
    ReparentingStatus,
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
)
from backend.reparenting_rehearsal.baseline import (
    ObjectIdentity,
    RepositoryBaseline,
    directory_identity,
)
from backend.reparenting_rehearsal.git_runner import git_output
from tests.reparenting_rehearsal_fixtures import observed_public_rehearsal


CHOICES = (
    ReviewedWorktreeChoice(
        worktree=SyntheticWorktree.ALPHA,
        strategy=WorktreeStrategy.REPAIR,
    ),
    ReviewedWorktreeChoice(
        worktree=SyntheticWorktree.BETA,
        strategy=WorktreeStrategy.RECREATE,
    ),
)


class ReparentingRehearsalRollbackTests(unittest.TestCase):
    def test_every_publication_boundary_has_verified_rollback(self) -> None:
        for boundary in PublicationBoundary:
            with self.subTest(boundary=boundary.value):
                with observed_public_rehearsal(
                    worktree_choices=CHOICES,
                    fail_at=boundary,
                ) as (result, scope, baseline):
                    self.assertEqual(
                        result.status,
                        ReparentingStatus.ROLLBACK_VERIFIED,
                    )
                    self.assertEqual(result.counts.completed, 0)
                    self.assertEqual(result.counts.rollback_verified, 1)
                    self.assertEqual(result.counts.failed, 0)
                    self._require_observable_rollback(
                        scope,
                        boundary,
                        baseline,
                    )

    def test_reversed_choices_preserve_both_reviewed_strategies(self) -> None:
        with observed_public_rehearsal(
            worktree_choices=(
                ReviewedWorktreeChoice(
                    worktree=SyntheticWorktree.ALPHA,
                    strategy=WorktreeStrategy.RECREATE,
                ),
                ReviewedWorktreeChoice(
                    worktree=SyntheticWorktree.BETA,
                    strategy=WorktreeStrategy.REPAIR,
                ),
            ),
            fail_at=None,
        ) as (result, _scope, _baseline):
            self.assertEqual(result.status, ReparentingStatus.COMPLETED)

    def _require_observable_rollback(
        self,
        scope: Path,
        boundary: PublicationBoundary,
        baseline: RepositoryBaseline,
    ) -> None:
        package = scope / "evidence" / "rehearsal.migration-evidence.zip"
        verified = verify_migration_evidence_package(package=package)
        self.assertEqual(
            verified.status,
            MigrationEvidenceStatus.VERIFIED,
        )
        repository, excluded_root = self._rollback_roots(
            scope,
            boundary,
            baseline,
        )
        self._require_git_baseline(scope, repository, baseline)
        self._require_excluded_objects(excluded_root)
        self._require_linked_worktrees(
            scope,
            boundary,
            repository,
            baseline,
        )

    def _rollback_roots(
        self,
        scope: Path,
        boundary: PublicationBoundary,
        baseline: RepositoryBaseline,
    ) -> tuple[Path, Path]:
        late = boundary in {
            PublicationBoundary.MAIN_PUBLICATION,
            PublicationBoundary.WORKTREE_PUBLICATION,
            PublicationBoundary.CONTAINER_AUDIT,
        }
        canonical = scope / "email_ai_assistant"
        legacy = scope / "email_ai_assistant-legacy-source"
        rollback = scope / "rollback-container"
        if late:
            self.assertFalse(canonical.exists())
            self.assertTrue(legacy.is_dir())
            self.assertTrue(rollback.is_dir())
            repository = rollback / "main"
            excluded_root = legacy
            self.assertEqual(
                directory_identity(legacy),
                baseline.source_identity,
            )
        else:
            self.assertTrue(canonical.is_dir())
            self.assertFalse(legacy.exists())
            repository = canonical
            excluded_root = canonical
            self.assertEqual(
                directory_identity(canonical),
                baseline.source_identity,
            )
        return repository, excluded_root

    def _require_excluded_objects(self, excluded_root: Path) -> None:
        for relative in (
            ".env",
            "signing.pem",
            ".venv/runtime.bin",
            "outputs/build.bin",
            ".idea/workspace.xml",
            ".cache/cache.bin",
            "data/email_analysis.sqlite",
            "runtime/request.tmp",
            "logs/service.log",
            "private/excluded.bin",
        ):
            self.assertTrue((excluded_root / relative).is_file())

    def _require_linked_worktrees(
        self,
        scope: Path,
        boundary: PublicationBoundary,
        repository: Path,
        baseline: RepositoryBaseline,
    ) -> None:
        rollback = scope / "rollback-container"
        if boundary in {
            PublicationBoundary.WORKTREE_PUBLICATION,
            PublicationBoundary.CONTAINER_AUDIT,
        }:
            active_root = rollback / "Worktrees"
        else:
            active_root = scope / "legacy-worktrees"
        common_identity = directory_identity(repository / ".git")
        self.assertEqual(common_identity, baseline.common_identity)
        main_head = git_output(
            scope,
            repository,
            ("rev-parse", "HEAD"),
        ).strip()
        for name in ("alpha", "beta"):
            worktree = active_root / name
            expected = baseline.linked(SyntheticWorktree(name))
            if active_root == rollback / "Worktrees" and name == "beta":
                identity_path = scope / "legacy-worktrees" / name
            else:
                identity_path = worktree
            self.assertEqual(
                directory_identity(identity_path),
                expected.directory_identity,
            )
            self._require_linked_worktree_git_state(
                scope=scope,
                worktree=worktree,
                name=name,
                main_head=main_head,
                common_identity=common_identity,
            )

    def _require_linked_worktree_git_state(
        self,
        *,
        scope: Path,
        worktree: Path,
        name: str,
        main_head: str,
        common_identity: ObjectIdentity,
    ) -> None:
        self.assertTrue(worktree.is_dir())
        self.assertEqual(
            git_output(
                scope,
                worktree,
                ("symbolic-ref", "HEAD"),
            ).strip(),
            f"refs/heads/synthetic-{name}",
        )
        self.assertEqual(
            git_output(scope, worktree, ("rev-parse", "HEAD")).strip(),
            main_head,
        )
        common = Path(
            git_output(
                scope,
                worktree,
                (
                    "rev-parse",
                    "--path-format=absolute",
                    "--git-common-dir",
                ),
            ).strip()
        )
        self.assertEqual(directory_identity(common), common_identity)
        self.assertEqual(
            git_output(
                scope,
                worktree,
                (
                    "status",
                    "--porcelain=v1",
                    "-z",
                    "--untracked-files=all",
                ),
            ),
            "",
        )

    def _require_git_baseline(
        self,
        scope: Path,
        repository: Path,
        baseline: RepositoryBaseline,
    ) -> None:
        self.assertEqual(
            git_output(scope, repository, ("symbolic-ref", "HEAD")).strip(),
            "refs/heads/master",
        )
        refs = git_output(
            scope,
            repository,
            ("for-each-ref", "--format=%(refname)", "refs/heads"),
        ).splitlines()
        self.assertEqual(
            refs,
            [
                "refs/heads/master",
                "refs/heads/synthetic-alpha",
                "refs/heads/synthetic-beta",
            ],
        )
        ahead = git_output(
            scope,
            repository,
            (
                "rev-list",
                "--left-right",
                "--count",
                "origin/master...master",
            ),
        ).split()
        self.assertEqual(ahead, ["0", "1"])
        for expected in (
            *baseline.tracked_files,
            baseline.reviewed_untracked,
        ):
            digest = hashlib.sha256(
                (repository / expected.relative_path).read_bytes()
            ).hexdigest()
            self.assertEqual(digest, expected.sha256)


if __name__ == "__main__":
    unittest.main()
