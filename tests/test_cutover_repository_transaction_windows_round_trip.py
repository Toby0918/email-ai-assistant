from __future__ import annotations

import sys
import unittest
import json
import io
from contextlib import redirect_stderr, redirect_stdout

from backend.cutover_repository_transaction.git_inspection import (
    directory_identity,
)
from backend.cutover_repository_transaction.git_recreation import (
    observe_all_recreated,
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
    SyntheticFailureSelectorV1,
)
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    build_synthetic_repository_scenario,
    profile_for_review,
    run_fixture_git,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class RepositoryTransactionWindowsRoundTripTests(unittest.TestCase):
    def test_forward_and_reverse_restore_all_original_identities(self):
        scenario = build_synthetic_repository_scenario()
        try:
            original_root_identity = directory_identity(scenario.source)
            original_physical = tuple(
                directory_identity(item.original)
                for item in scenario.worktrees
            )
            review = _review_test_sandbox(scenario)
            original_admin = tuple(
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

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                forward = run_forward_synthetic_transaction(
                    scope=scope,
                    failure_selector=SyntheticFailureSelectorV1.none(),
                    observed_at_epoch=OBSERVED_AT,
                )
            self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))

            self.assertEqual(forward.status, "complete")
            self.assertEqual(forward.direction, "forward")
            self.assertEqual(forward.boundary_count, 8)
            self.assertEqual(forward.worktree_count, 11)
            main = scenario.source / "main"
            self.assertEqual(directory_identity(main), original_root_identity)
            for index, item in enumerate(scenario.worktrees):
                self.assertEqual(
                    directory_identity(item.preservation),
                    original_physical[index],
                )
                preserved_admin = (
                    scenario.admin_preservation / item.role
                )
                self.assertEqual(
                    directory_identity(preserved_admin),
                    original_admin[index],
                )
                self.assertTrue(item.target.is_dir())
            self.assertEqual(
                _worktree_count(run_fixture_git(
                    main, "worktree", "list", "--porcelain", "-z"
                )),
                12,
            )
            recreated = observe_all_recreated(scope, main)
            self.assertEqual(
                tuple(item.admin.name for item in recreated),
                tuple(item.admin.name for item in review.observations),
            )
            self.assertTrue(
                all(
                    current.admin_identity != original.admin_identity
                    for current, original in zip(
                        recreated, review.observations
                    )
                )
            )
            _assert_journal_triplets(self, scenario)
            _assert_journal_content_free(self, scenario)
            self.assertEqual(
                _journal_boundaries(scenario, "forward"),
                {
                    "source_frozen",
                    "worktrees_preserved",
                    "legacy_renamed",
                    "container_published",
                    "non_main_zones_published",
                    "main_published",
                    "worktrees_recreated",
                    "repository_final_verified",
                },
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                reverse = run_reverse_synthetic_transaction(
                    scope=scope,
                    failure_selector=SyntheticFailureSelectorV1.none(),
                    observed_at_epoch=OBSERVED_AT,
                )
            self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))

            self.assertEqual(reverse.status, "complete")
            self.assertEqual(reverse.direction, "reverse")
            self.assertEqual(reverse.boundary_count, 5)
            self.assertTrue(reverse.failed_state_preserved)
            self.assertTrue(scenario.failed_container.is_dir())
            self.assertEqual(
                directory_identity(scenario.source), original_root_identity
            )
            for index, item in enumerate(scenario.worktrees):
                self.assertEqual(
                    directory_identity(item.original),
                    original_physical[index],
                )
                self.assertEqual(
                    directory_identity(review.observations[index].admin),
                    original_admin[index],
                )
            self.assertEqual(
                _worktree_count(run_fixture_git(
                    scenario.source,
                    "worktree",
                    "list",
                    "--porcelain",
                    "-z",
                )),
                12,
            )
            _assert_journal_triplets(self, scenario)
            _assert_journal_content_free(self, scenario)
            self.assertEqual(
                _journal_boundaries(scenario, "reverse"),
                {
                    "new_state_preserved",
                    "main_extracted",
                    "admin_records_restored",
                    "physical_worktrees_restored",
                    "original_repository_verified",
                },
            )
            self.assertNotIn(str(scenario.root), repr(reverse))
        finally:
            scenario.close()


def _worktree_count(payload: bytes) -> int:
    return sum(
        field.startswith(b"worktree ")
        for field in payload.split(b"\0")
    )


def _assert_journal_triplets(test, scenario) -> None:
    paths = tuple(sorted(scenario.journal_root.glob("*.json")))
    test.assertGreater(len(paths), 0)
    test.assertEqual(len(paths) % 3, 0)
    events = [
        json.loads(path.read_text("ascii"))["event"]
        for path in paths
    ]
    for index in range(0, len(events), 3):
        test.assertEqual(
            events[index:index + 3],
            ["intent", "observed", "committed"],
        )


def _journal_boundaries(scenario, direction):
    return {
        body["boundary"]
        for path in scenario.journal_root.glob("*.json")
        if (body := json.loads(path.read_text("ascii")))["direction"]
        == direction
    }


def _assert_journal_content_free(test, scenario):
    payload = b"".join(
        path.read_bytes() for path in scenario.journal_root.glob("*.json")
    )
    forbidden = (
        str(scenario.root).encode(),
        b"refs/heads/",
        b"worktree_01",
        b"original-01",
        b".git",
    )
    for value in forbidden:
        test.assertNotIn(value, payload)


if __name__ == "__main__":
    unittest.main()
