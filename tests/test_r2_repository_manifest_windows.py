"""Physical complete-manifest and eleven-worktree proof for Issue #75."""

from __future__ import annotations

import sys
import unittest

from backend.cutover_host_mutation.acl_contracts import AclCompatibilityPolicyV1
from backend.cutover_host_mutation.windows_acl import _current_operator_sid_fingerprint
from backend.cutover_contracts import CutoverProfileV1
from backend.cutover_repository_transaction.git_inspection import directory_identity
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.r2_repository_manifest import (
    ManifestBoundary,
    ManifestCrashGap,
    ManifestSelectorV1,
)
from backend.r2_repository_manifest.testing import bind_test_manifest_transaction
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    profile_for_review,
)
from tests.r2_repository_manifest_fixture import (
    build_manifest_repository_scenario,
    run_manifest_git,
)


@unittest.skipUnless(sys.platform == "win32", "Windows NTFS sandbox required")
class R2RepositoryManifestWindowsTests(unittest.TestCase):
    def test_full_manifest_forward_and_reverse_preserve_all_identities(self) -> None:
        scenario, transaction, originals = self._bound()
        try:
            forward = transaction.execute(ManifestSelectorV1.none())

            self.assertEqual(forward.status, "REPOSITORY_TOPOLOGY_PUBLISHED")
            self.assertEqual(forward.repository_count, 1)
            self.assertEqual(forward.worktree_count, 11)
            self.assertEqual(forward.embedded_count, 8)
            self.assertEqual(forward.external_count, 3)
            self.assertEqual(_worktree_count(run_manifest_git(
                scenario.source / "main", "worktree", "list", "--porcelain", "-z"
            )), 12)
            self.assertTrue(transaction.manifest_exact())
            self.assertTrue(transaction.residue_exact())
            self.assertTrue(transaction.original_worktree_identities_retained())

            reverse = transaction.rollback()

            self.assertEqual(reverse.status, "LEGACY_FLAT_LAYOUT_RESTORED")
            self.assertTrue(scenario.failed_container.is_dir())
            self.assertEqual(directory_identity(scenario.source), originals[0])
            self.assertEqual(transaction.current_original_identities(), originals)
            self.assertEqual(_worktree_count(run_manifest_git(
                scenario.source, "worktree", "list", "--porcelain", "-z"
            )), 12)
        finally:
            transaction.close()
            scenario.close()

    def test_manifest_exact_rejects_an_unreviewed_extra_object(self) -> None:
        scenario, transaction, _originals = self._bound()
        try:
            transaction.execute(ManifestSelectorV1.none())
            extra = scenario.source / "main" / "unreviewed-extra.txt"
            extra.write_text("not selected\n", encoding="utf-8")
            self.assertFalse(transaction.manifest_exact())
        finally:
            transaction.close()
            scenario.close()

    def test_each_manifest_and_worktree_boundary_can_crash_and_reverse(self) -> None:
        cases = (
            (ManifestBoundary.MANIFEST_RELOCATION, 1),
            (ManifestBoundary.MANIFEST_RELOCATION, 6),
            (ManifestBoundary.WORKTREE_RECONSTRUCTION, 1),
            (ManifestBoundary.WORKTREE_RECONSTRUCTION, 11),
        )
        for boundary, index in cases:
            for gap in ManifestCrashGap:
                with self.subTest(boundary=boundary.value, index=index, gap=gap.value):
                    scenario, transaction, originals = self._bound()
                    try:
                        selector = ManifestSelectorV1.create(
                            boundary=boundary,
                            item_index=index,
                            gap=gap,
                        )
                        with self.assertRaisesRegex(RuntimeError, "manifest_interrupted"):
                            transaction.execute(selector)
                        receipt = transaction.rollback()
                        self.assertEqual(receipt.status, "LEGACY_FLAT_LAYOUT_RESTORED")
                        self.assertEqual(transaction.current_original_identities(), originals)
                    finally:
                        transaction.close()
                        scenario.close()

    def test_reverse_manifest_and_worktree_gaps_resume_exactly(self) -> None:
        cases = (
            (ManifestBoundary.MANIFEST_RELOCATION, 1),
            (ManifestBoundary.WORKTREE_PRESERVATION, 1),
        )
        for boundary, index in cases:
            for gap in ManifestCrashGap:
                with self.subTest(boundary=boundary.value, gap=gap.value):
                    scenario, transaction, originals = self._bound()
                    try:
                        transaction.execute(ManifestSelectorV1.none())
                        selector = ManifestSelectorV1.create(
                            boundary=boundary,
                            item_index=index,
                            gap=gap,
                        )
                        with self.assertRaisesRegex(
                            RuntimeError, "manifest_interrupted"
                        ):
                            transaction.rollback(selector)
                        receipt = transaction.rollback()
                        self.assertEqual(
                            receipt.status, "LEGACY_FLAT_LAYOUT_RESTORED"
                        )
                        self.assertEqual(
                            transaction.current_original_identities(), originals
                        )
                    finally:
                        transaction.close()
                        scenario.close()

    def _bound(self):
        scenario = build_manifest_repository_scenario()
        review = _review_test_sandbox(scenario)
        policy = AclCompatibilityPolicyV1.create(
            allowed_descriptor_fingerprints=(opaque_fingerprint(750),),
            maximum_objects=10_000,
        )
        profile = profile_for_review(
            review, acl_policy_fingerprint=policy.policy_fingerprint
        )
        body = profile.to_mapping()
        body.pop("profile_fingerprint")
        body["operator_fingerprint"] = _current_operator_sid_fingerprint()
        profile = CutoverProfileV1.create(body)
        body = profile.to_mapping()
        self.assertEqual(body["operator_fingerprint"], _current_operator_sid_fingerprint())
        authorization = authorization_for(profile, review.operation_fingerprint)
        scope = _bind_test_sandbox_transaction(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )
        transaction = bind_test_manifest_transaction(
            scope=scope,
            policy=policy,
            approved_untracked=("approved-note.txt",),
            observed_at_epoch=OBSERVED_AT,
        )
        return scenario, transaction, transaction.current_original_identities()


def _worktree_count(payload: bytes) -> int:
    return sum(field.startswith(b"worktree ") for field in payload.split(b"\0"))


if __name__ == "__main__":
    unittest.main()
