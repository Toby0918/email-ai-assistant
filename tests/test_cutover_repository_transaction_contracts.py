from __future__ import annotations

import hashlib
import unittest

from backend.cutover_repository_transaction import (
    RepositoryWorktreePlacement,
    ReviewedWorktreeV1,
    SyntheticRepositoryRosterV1,
)
from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)


def _fingerprint(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _reviewed_worktree(index: int) -> ReviewedWorktreeV1:
    placement = (
        RepositoryWorktreePlacement.EMBEDDED
        if index <= 8
        else RepositoryWorktreePlacement.EXTERNAL
    )
    return ReviewedWorktreeV1.create(
        role=f"worktree_{index:02d}",
        placement=placement,
        selection_fingerprint=_fingerprint(f"selection-{index}"),
        ref_fingerprint=_fingerprint(f"ref-{index}"),
        commit_fingerprint=_fingerprint("shared-commit"),
        common_directory_fingerprint=_fingerprint("shared-common"),
        physical_identity_fingerprint=_fingerprint(f"physical-{index}"),
        admin_identity_fingerprint=_fingerprint(f"admin-{index}"),
        admin_content_fingerprint=_fingerprint(f"admin-content-{index}"),
        target_fingerprint=_fingerprint(f"target-{index}"),
        preservation_fingerprint=_fingerprint(f"preservation-{index}"),
        clean=True,
    )


class RepositoryTransactionContractTests(unittest.TestCase):
    def test_roster_requires_exactly_eight_embedded_and_three_external(self):
        worktrees = tuple(_reviewed_worktree(index) for index in range(1, 12))

        roster = SyntheticRepositoryRosterV1.create(worktrees=worktrees)

        self.assertEqual(roster.embedded_count, 8)
        self.assertEqual(roster.external_count, 3)
        self.assertEqual(roster.worktree_count, 11)
        self.assertNotIn(_fingerprint("selection-1"), repr(roster))
        self.assertNotIn("worktree_01", repr(roster))

    def test_roster_rejects_wrong_placement_order_and_duplicate_binding(self):
        worktrees = list(_reviewed_worktree(index) for index in range(1, 12))
        worktrees[7] = _reviewed_worktree(9)

        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_roster_invalid$",
        ):
            SyntheticRepositoryRosterV1.create(worktrees=tuple(worktrees))

        duplicate = list(
            _reviewed_worktree(index) for index in range(1, 12)
        )
        duplicate[10] = duplicate[9]
        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_roster_invalid$",
        ):
            SyntheticRepositoryRosterV1.create(worktrees=tuple(duplicate))

    def test_worktree_contract_rejects_dirty_or_non_fingerprint_values(self):
        values = {
            "role": "worktree_01",
            "placement": RepositoryWorktreePlacement.EMBEDDED,
            "selection_fingerprint": _fingerprint("selection"),
            "ref_fingerprint": _fingerprint("ref"),
            "commit_fingerprint": _fingerprint("commit"),
            "common_directory_fingerprint": _fingerprint("common"),
            "physical_identity_fingerprint": _fingerprint("physical"),
            "admin_identity_fingerprint": _fingerprint("admin"),
            "admin_content_fingerprint": _fingerprint("admin-content"),
            "target_fingerprint": _fingerprint("target"),
            "preservation_fingerprint": _fingerprint("preservation"),
            "clean": True,
        }
        for key, replacement in (
            ("clean", False),
            ("selection_fingerprint", "not-a-fingerprint"),
            ("placement", "embedded"),
        ):
            hostile = {**values, key: replacement}
            with self.subTest(key=key), self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_worktree_invalid$",
            ):
                ReviewedWorktreeV1.create(**hostile)


if __name__ == "__main__":
    unittest.main()
