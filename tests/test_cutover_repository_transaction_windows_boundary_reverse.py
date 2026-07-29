from __future__ import annotations

import sys
import unittest

from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)
from backend.cutover_repository_transaction.git_inspection import (
    directory_identity,
)
from backend.cutover_repository_transaction.journal_types import (
    ForwardBoundary,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.cutover_repository_transaction.transaction import (
    run_forward_synthetic_transaction,
    run_reverse_synthetic_transaction,
)
from backend.cutover_repository_transaction.transaction_types import (
    SyntheticCrashGap,
    SyntheticFailureSelectorV1,
    SyntheticTransactionDirection,
)
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    build_synthetic_repository_scenario,
    profile_for_review,
    run_fixture_git,
)

_BOUNDARY_LAST_MUTATIONS = (
    (ForwardBoundary.SOURCE_FROZEN, 1, False),
    (ForwardBoundary.WORKTREES_PRESERVED, 24, False),
    (ForwardBoundary.LEGACY_RENAMED, 25, False),
    (ForwardBoundary.CONTAINER_PUBLISHED, 26, True),
    (ForwardBoundary.NON_MAIN_ZONES_PUBLISHED, 34, True),
    (ForwardBoundary.MAIN_PUBLISHED, 35, True),
    (ForwardBoundary.WORKTREES_RECREATED, 57, True),
    (ForwardBoundary.REPOSITORY_FINAL_VERIFIED, 58, True),
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class RepositoryTransactionBoundaryReverseTests(unittest.TestCase):
    def test_every_committed_forward_boundary_is_reversible(self):
        for boundary, mutation_index, failed_preserved in (
            _BOUNDARY_LAST_MUTATIONS
        ):
            with self.subTest(boundary=boundary.value):
                self._assert_boundary_reverse(
                    boundary, mutation_index, failed_preserved
                )

    def _assert_boundary_reverse(
        self,
        boundary: ForwardBoundary,
        mutation_index: int,
        failed_preserved: bool,
    ) -> None:
        scenario = build_synthetic_repository_scenario()
        try:
            root_identity = directory_identity(scenario.source)
            physical = tuple(
                directory_identity(item.original)
                for item in scenario.worktrees
            )
            review = _review_test_sandbox(scenario)
            admin = tuple(
                item.admin_identity for item in review.observations
            )
            profile = profile_for_review(review)
            authorization = authorization_for(
                profile, review.operation_fingerprint
            )
            scope = _bind_test_sandbox_transaction(
                review=review,
                profile=profile,
                authorization=authorization,
                observed_at_epoch=OBSERVED_AT,
            )
            selector = SyntheticFailureSelectorV1.create(
                direction=SyntheticTransactionDirection.FORWARD,
                boundary=boundary,
                mutation_index=mutation_index,
                gap=SyntheticCrashGap.AFTER_COMMITTED,
            )
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_transaction_interrupted$",
            ):
                run_forward_synthetic_transaction(
                    scope=scope,
                    failure_selector=selector,
                    observed_at_epoch=OBSERVED_AT,
                )

            receipt = run_reverse_synthetic_transaction(
                scope=scope,
                failure_selector=SyntheticFailureSelectorV1.none(),
                observed_at_epoch=OBSERVED_AT,
            )

            self.assertEqual(
                directory_identity(scenario.source), root_identity
            )
            self.assertEqual(
                tuple(
                    directory_identity(item.original)
                    for item in scenario.worktrees
                ),
                physical,
            )
            self.assertEqual(
                tuple(
                    directory_identity(item.admin)
                    for item in review.observations
                ),
                admin,
            )
            self.assertEqual(
                _worktree_count(
                    run_fixture_git(
                        scenario.source,
                        "worktree",
                        "list",
                        "--porcelain",
                        "-z",
                    )
                ),
                12,
            )
            self.assertEqual(
                scenario.failed_container.is_dir(), failed_preserved
            )
            self.assertEqual(
                receipt.failed_state_preserved, failed_preserved
            )
        finally:
            scenario.close()


def _worktree_count(payload: bytes) -> int:
    return sum(
        field.startswith(b"worktree ")
        for field in payload.split(b"\0")
    )


if __name__ == "__main__":
    unittest.main()
