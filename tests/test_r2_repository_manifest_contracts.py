"""Public contract tests for Issue #75 complete-manifest relocation."""

from __future__ import annotations

import unittest

from backend.r2_repository_manifest import (
    ManifestBoundary,
    ManifestCategory,
    ManifestCrashGap,
    RepositoryContentManifestV1,
    RepositoryTopologyReceiptV1,
)


class R2RepositoryManifestContractTests(unittest.TestCase):
    def test_contracts_are_nominal_and_categories_are_closed(self) -> None:
        for contract in (RepositoryContentManifestV1, RepositoryTopologyReceiptV1):
            with self.subTest(contract=contract.__name__):
                with self.assertRaises(TypeError):
                    contract()
        self.assertEqual(
            {item.value for item in ManifestCategory},
            {"git", "tracked", "approved_untracked"},
        )

    def test_boundary_and_gap_vocabularies_are_closed(self) -> None:
        self.assertEqual(
            {item.value for item in ManifestCrashGap},
            {
                "after_intent",
                "after_effect",
                "after_scan",
                "after_observation",
                "after_commit",
            },
        )
        self.assertIn("manifest_relocation", {item.value for item in ManifestBoundary})
        self.assertIn("worktree_reconstruction", {item.value for item in ManifestBoundary})


if __name__ == "__main__":
    unittest.main()
