from __future__ import annotations

import sys
import unittest

from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)
from backend.cutover_repository_transaction.journal_types import (
    ForwardBoundary,
    ReverseBoundary,
)
from backend.cutover_repository_transaction.git_inspection import (
    directory_identity,
    opaque_directory_fingerprint,
)
from backend.cutover_repository_transaction.restart_classification import (
    classify_synthetic_restart,
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
    RestartClassification,
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


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class RepositoryTransactionCrashGapTests(unittest.TestCase):
    def test_every_reverse_crash_gap_resumes_to_exact_original_state(self):
        boundaries = (
            (ReverseBoundary.NEW_STATE_PRESERVED, 18),
            (ReverseBoundary.MAIN_EXTRACTED, 19),
            (ReverseBoundary.ADMIN_RECORDS_RESTORED, 30),
            (ReverseBoundary.PHYSICAL_WORKTREES_RESTORED, 41),
            (ReverseBoundary.ORIGINAL_REPOSITORY_VERIFIED, 42),
        )
        gaps = tuple(
            gap
            for gap in SyntheticCrashGap
            if gap is not SyntheticCrashGap.NONE
        )
        for boundary, mutation_index in boundaries:
            for gap in gaps:
                with self.subTest(boundary=boundary.value, gap=gap.value):
                    scenario, scope = _bound_scenario()
                    try:
                        original = _capture_original_identities(scope)
                        run_forward_synthetic_transaction(
                            scope=scope,
                            failure_selector=(
                                SyntheticFailureSelectorV1.none()
                            ),
                            observed_at_epoch=OBSERVED_AT,
                        )
                        selector = SyntheticFailureSelectorV1.create(
                            direction=(
                                SyntheticTransactionDirection.REVERSE
                            ),
                            boundary=boundary,
                            mutation_index=mutation_index,
                            gap=gap,
                        )
                        with self.assertRaisesRegex(
                            RepositoryTransactionError,
                            "^repository_transaction_interrupted$",
                        ):
                            run_reverse_synthetic_transaction(
                                scope=scope,
                                failure_selector=selector,
                                observed_at_epoch=OBSERVED_AT,
                            )
                        self.assertIs(
                            classify_synthetic_restart(scope),
                            _expected_reverse_classification(
                                mutation_index, gap
                            ),
                        )
                        receipt = run_reverse_synthetic_transaction(
                            scope=scope,
                            failure_selector=(
                                SyntheticFailureSelectorV1.none()
                            ),
                            observed_at_epoch=OBSERVED_AT,
                        )
                        self.assertEqual(receipt.direction, "reverse")
                        self.assertEqual(receipt.mutation_count, 42)
                        _assert_original_identities(
                            self, scope, original
                        )
                    finally:
                        scenario.close()

    def test_forward_move_crash_gaps_are_safely_classified(self):
        expected = {
            SyntheticCrashGap.AFTER_INTENT: RestartClassification.SAFE_ABORT,
            SyntheticCrashGap.AFTER_EFFECT: (
                RestartClassification.SAFE_COMMIT_FACTS
            ),
            SyntheticCrashGap.AFTER_OBSERVED: (
                RestartClassification.SAFE_COMMIT_FACTS
            ),
            SyntheticCrashGap.AFTER_COMMITTED: (
                RestartClassification.SAFE_ABORT
            ),
        }
        for gap, classification in expected.items():
            with self.subTest(gap=gap.value):
                scenario, scope = _bound_scenario()
                try:
                    original_identity = directory_identity(
                        scenario.source
                    )
                    selector = SyntheticFailureSelectorV1.create(
                        direction=SyntheticTransactionDirection.FORWARD,
                        boundary=ForwardBoundary.LEGACY_RENAMED,
                        mutation_index=25,
                        gap=gap,
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
                    self.assertIs(
                        classify_synthetic_restart(scope), classification
                    )
                    receipt = run_reverse_synthetic_transaction(
                        scope=scope,
                        failure_selector=SyntheticFailureSelectorV1.none(),
                        observed_at_epoch=OBSERVED_AT,
                    )
                    self.assertEqual(receipt.direction, "reverse")
                    self.assertEqual(
                        directory_identity(scenario.source),
                        original_identity,
                    )
                finally:
                    scenario.close()

    def test_nonfinal_legacy_reverse_main_gap_resumes_exactly(self):
        for gap in (
            item
            for item in SyntheticCrashGap
            if item is not SyntheticCrashGap.NONE
        ):
            with self.subTest(gap=gap.value):
                scenario, scope = _bound_scenario()
                try:
                    original = _capture_original_identities(scope)
                    forward_selector = SyntheticFailureSelectorV1.create(
                        direction=SyntheticTransactionDirection.FORWARD,
                        boundary=ForwardBoundary.LEGACY_RENAMED,
                        mutation_index=25,
                        gap=SyntheticCrashGap.AFTER_COMMITTED,
                    )
                    with self.assertRaisesRegex(
                        RepositoryTransactionError,
                        "^repository_transaction_interrupted$",
                    ):
                        run_forward_synthetic_transaction(
                            scope=scope,
                            failure_selector=forward_selector,
                            observed_at_epoch=OBSERVED_AT,
                        )
                    reverse_selector = SyntheticFailureSelectorV1.create(
                        direction=SyntheticTransactionDirection.REVERSE,
                        boundary=ReverseBoundary.MAIN_EXTRACTED,
                        mutation_index=1,
                        gap=gap,
                    )
                    with self.assertRaisesRegex(
                        RepositoryTransactionError,
                        "^repository_transaction_interrupted$",
                    ):
                        run_reverse_synthetic_transaction(
                            scope=scope,
                            failure_selector=reverse_selector,
                            observed_at_epoch=OBSERVED_AT,
                        )
                    receipt = run_reverse_synthetic_transaction(
                        scope=scope,
                        failure_selector=SyntheticFailureSelectorV1.none(),
                        observed_at_epoch=OBSERVED_AT,
                    )
                    self.assertEqual(receipt.mutation_count, 24)
                    _assert_original_identities(self, scope, original)
                finally:
                    scenario.close()

def _bound_scenario():
    scenario = build_synthetic_repository_scenario()
    review = _review_test_sandbox(scenario)
    profile = profile_for_review(review)
    authorization = authorization_for(profile, review.operation_fingerprint)
    scope = _bind_test_sandbox_transaction(
        review=review,
        profile=profile,
        authorization=authorization,
        observed_at_epoch=OBSERVED_AT,
    )
    return scenario, scope


def _capture_original_identities(scope):
    return (
        directory_identity(scope.review.scenario.source),
        tuple(
            (
                directory_identity(item.paths.original),
                directory_identity(item.admin),
                opaque_directory_fingerprint(item.admin),
            )
            for item in scope.review.observations
        ),
    )


def _assert_original_identities(test, scope, expected) -> None:
    repository_identity, worktrees = expected
    test.assertEqual(
        directory_identity(scope.review.scenario.source),
        repository_identity,
    )
    for item, identities in zip(
        scope.review.observations, worktrees, strict=True
    ):
        physical, admin, admin_content = identities
        test.assertEqual(
            directory_identity(item.paths.original), physical
        )
        test.assertEqual(directory_identity(item.admin), admin)
        test.assertEqual(
            opaque_directory_fingerprint(item.admin), admin_content
        )
    porcelain = run_fixture_git(
        scope.review.scenario.source,
        "worktree",
        "list",
        "--porcelain",
    )
    test.assertEqual(porcelain.count(b"worktree "), 12)


def _expected_reverse_classification(index, gap):
    if gap is SyntheticCrashGap.AFTER_COMMITTED:
        if index == 42:
            return RestartClassification.NO_INTERRUPTION
        return RestartClassification.SAFE_ABORT
    if gap is SyntheticCrashGap.AFTER_INTENT and index not in {18, 42}:
        return RestartClassification.SAFE_ABORT
    return RestartClassification.SAFE_COMMIT_FACTS


if __name__ == "__main__":
    unittest.main()
