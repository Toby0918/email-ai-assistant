from __future__ import annotations

import unittest

from backend.cutover_repository_transaction.journal_types import (
    ForwardBoundary,
)
from backend.cutover_repository_transaction.reverse_plan import (
    reverse_stage_plan,
)


class RepositoryTransactionReversePlanTests(unittest.TestCase):
    def test_every_forward_stage_has_exact_reverse_progress_boundaries(self):
        expected = {
            ForwardBoundary.SOURCE_FROZEN: (0, None, None, None, 1),
            ForwardBoundary.WORKTREES_PRESERVED: (0, None, 11, 22, 23),
            ForwardBoundary.LEGACY_RENAMED: (0, 1, 12, 23, 24),
            ForwardBoundary.CONTAINER_PUBLISHED: (2, 3, 14, 25, 26),
            ForwardBoundary.NON_MAIN_ZONES_PUBLISHED: (2, 3, 14, 25, 26),
            ForwardBoundary.MAIN_PUBLISHED: (2, 3, 14, 25, 26),
            ForwardBoundary.WORKTREES_RECREATED: (18, 19, 30, 41, 42),
            ForwardBoundary.REPOSITORY_FINAL_VERIFIED: (18, 19, 30, 41, 42),
        }
        for stage, values in expected.items():
            with self.subTest(stage=stage.value):
                plan = reverse_stage_plan(stage)
                self.assertEqual(
                    (
                        plan.preserve_last,
                        plan.main_index,
                        plan.admin_last,
                        plan.physical_last,
                        plan.final_index,
                    ),
                    values,
                )


if __name__ == "__main__":
    unittest.main()
