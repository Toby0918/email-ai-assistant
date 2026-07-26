from __future__ import annotations

import unittest

from backend.reparenting_rehearsal import (
    PublicationBoundary,
    ReparentingStatus,
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
    rehearse_repository_reparenting,
)


class ReparentingRehearsalContractTests(unittest.TestCase):
    def test_invalid_reviewed_choice_set_fails_before_rehearsal(self) -> None:
        result = rehearse_repository_reparenting(
            worktree_choices=(
                ReviewedWorktreeChoice(
                    worktree=SyntheticWorktree.ALPHA,
                    strategy=WorktreeStrategy.REPAIR,
                ),
            ),
            fail_at=None,
        )

        self.assertEqual(result.status, ReparentingStatus.FAILED)
        self.assertEqual(result.counts.completed, 0)
        self.assertEqual(result.counts.rollback_verified, 0)
        self.assertEqual(result.counts.failed, 1)
        self.assertNotIn("path", repr(result).casefold())

    def test_public_enums_are_closed_and_content_free(self) -> None:
        self.assertEqual(
            {item.value for item in SyntheticWorktree},
            {"alpha", "beta"},
        )
        self.assertEqual(
            {item.value for item in WorktreeStrategy},
            {"repair", "recreate"},
        )
        self.assertEqual(
            {item.value for item in PublicationBoundary},
            {
                "evidence_package",
                "legacy_rename",
                "container_publication",
                "main_publication",
                "worktree_publication",
                "container_audit",
            },
        )
        self.assertEqual(
            {item.value for item in ReparentingStatus},
            {
                "reparenting_rehearsal_completed",
                "reparenting_rehearsal_rollback_verified",
                "reparenting_rehearsal_failed",
            },
        )


if __name__ == "__main__":
    unittest.main()
