from __future__ import annotations

import unittest

from backend.reparenting_rehearsal import (
    ReparentingStatus,
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
)
from tests.reparenting_rehearsal_fixtures import observed_public_rehearsal


class ReparentingRehearsalSuccessTests(unittest.TestCase):
    def test_complete_synthetic_reparenting_passes(self) -> None:
        choices = (
            ReviewedWorktreeChoice(
                worktree=SyntheticWorktree.ALPHA,
                strategy=WorktreeStrategy.REPAIR,
            ),
            ReviewedWorktreeChoice(
                worktree=SyntheticWorktree.BETA,
                strategy=WorktreeStrategy.RECREATE,
            ),
        )
        with observed_public_rehearsal(
            worktree_choices=choices,
            fail_at=None,
        ) as (result, scope, _baseline):
            self.assertEqual(result.status, ReparentingStatus.COMPLETED)
            self.assertEqual(result.counts.completed, 1)
            self.assertEqual(result.counts.rollback_verified, 0)
            self.assertEqual(result.counts.failed, 0)
            self.assertTrue((scope / "email_ai_assistant").is_dir())
            self.assertTrue(
                (scope / "email_ai_assistant-legacy-source").is_dir()
            )
            self.assertTrue(
                (
                    scope
                    / "email_ai_assistant"
                    / "Worktrees"
                    / "alpha"
                ).is_dir()
            )
            self.assertTrue(
                (
                    scope
                    / "email_ai_assistant"
                    / "Worktrees"
                    / "beta"
                ).is_dir()
            )


if __name__ == "__main__":
    unittest.main()
