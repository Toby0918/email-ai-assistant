"""TDD coverage for the profile-bound Issue #54 review composition."""

from __future__ import annotations

import copy
import inspect
import json
import pickle
import unittest
from unittest import mock

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.migration_evidence_publication import (
    MigrationEvidencePublicationError,
    MigrationEvidenceReviewReceiptV1,
    ProfileBoundEvidenceSelectionV1,
    review_profile_bound_migration_evidence,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.migration_evidence_publication_fixtures import (
    GOVERNING_MASTER,
    MARKER_BYTES,
    MARKER_NAME,
    OBSERVED_AT,
    OPERATION_FINGERPRINT,
    PublicationReviewFixture,
)


class MigrationEvidencePublicationReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = PublicationReviewFixture()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.fixture.close()

    def test_review_composes_profile_bound_content_free_receipt(self) -> None:
        selection = self.fixture.bind_selection()

        receipt = review_profile_bound_migration_evidence(
            profile=self.fixture.profile,
            authorization=self.fixture.real_authorization(),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
            selection=selection,
        )

        self.assertIs(type(selection), ProfileBoundEvidenceSelectionV1)
        self.assertIs(type(receipt), MigrationEvidenceReviewReceiptV1)
        self.assertEqual(receipt.counts.dirty_entries, 2)
        self.assertEqual(receipt.counts.included_dirty_entries, 2)
        self.assertEqual(receipt.counts.excluded_dirty_entries, 0)
        self.assertEqual(receipt.counts.refs, 11)
        self.assertEqual(receipt.counts.worktrees, 11)
        self.assertEqual(receipt.counts.source_records, 2)
        self.assertGreater(receipt.counts.source_bytes, 0)
        self.assertEqual(
            self.fixture.profile.governing_master_commit,
            GOVERNING_MASTER,
        )
        mapping = receipt.to_mapping()
        self.assertEqual(
            set(mapping),
            {
                "receipt_type",
                "status",
                "operation_fingerprint",
                "profile_fingerprint",
                "master_fingerprint",
                "review_fingerprint",
                "selection_fingerprint",
                "git_fingerprint",
                "host_fingerprint",
                "counts_fingerprint",
                "counts",
                "receipt_fingerprint",
            },
        )
        self.assertEqual(
            mapping["status"],
            "MIGRATION_EVIDENCE_REVIEW_ACCEPTED",
        )
        self.assertFalse(self.fixture.target.exists())
        serialized = json.dumps(mapping, sort_keys=True)
        forbidden = [
            str(self.fixture.root),
            "refs/heads/",
            "worktree-02",
            self.fixture.profile.governing_master_commit,
        ]
        for value in forbidden:
            self.assertNotIn(value, serialized)
            self.assertNotIn(value, repr(receipt))

    def test_public_review_accepts_no_raw_discovery_values(self) -> None:
        parameters = inspect.signature(
            review_profile_bound_migration_evidence
        ).parameters
        self.assertEqual(
            set(parameters),
            {
                "profile",
                "authorization",
                "operation_fingerprint",
                "observed_at_epoch",
                "selection",
            },
        )
        forbidden = {
            "repository_root",
            "target",
            "approved_dirty_paths",
            "reviewed_refs",
            "approved_worktrees",
            "host_baseline",
        }
        self.assertTrue(forbidden.isdisjoint(parameters))

    def test_review_rejects_non_real_and_wrong_phase_authorization(self) -> None:
        invalid = (
            None,
            TestSandboxAuthorizationV1.create(
                profile_fingerprint=(
                    self.fixture.profile.profile_fingerprint
                ),
                operation_fingerprint=OPERATION_FINGERPRINT,
                phase="evidence_review",
                expires_at_epoch=OBSERVED_AT + 300,
            ),
            self.fixture.real_authorization(phase="host_baseline"),
        )
        for authorization in invalid:
            with self.subTest(authorization=type(authorization).__name__):
                with self.assertRaisesRegex(
                    MigrationEvidencePublicationError,
                    "^MIGRATION_EVIDENCE_REVIEW_REJECTED$",
                ):
                    review_profile_bound_migration_evidence(
                        profile=self.fixture.profile,
                        authorization=authorization,
                        operation_fingerprint=OPERATION_FINGERPRINT,
                        observed_at_epoch=OBSERVED_AT,
                        selection=self.fixture.bind_selection(),
                    )

    def test_review_rejects_each_profile_selection_family_mismatch(
        self,
    ) -> None:
        variants = tuple(
            ("evidence_roles", key)
            for key in (
                "review_root",
                "package_target",
                "journal_root",
                "git_records_preservation",
                "worktree_preservation",
                "rollback_publication",
            )
        ) + tuple(
            ("reviewed_git_selections", key)
            for key in (
                "repository_identity",
                "common_directory_identity",
                "git_executable",
                "remote_configuration",
                "local_refs",
                "dirty_layers",
                "worktree_topology",
            )
        ) + tuple(
            ("worktree_roster", index)
            for index in range(11)
        )
        for section, key in variants:
            with self.subTest(section=section, key=key):
                profile = self.fixture.profile_with_changed_binding(
                    section,
                    key,
                )
                with self.assertRaisesRegex(
                    MigrationEvidencePublicationError,
                    "^MIGRATION_EVIDENCE_REVIEW_REJECTED$",
                ):
                    review_profile_bound_migration_evidence(
                        profile=profile,
                        authorization=self.fixture.real_authorization(profile),
                        operation_fingerprint=OPERATION_FINGERPRINT,
                        observed_at_epoch=OBSERVED_AT,
                        selection=self.fixture.bind_selection(profile),
                    )

    def test_selection_and_receipt_are_nominal_nonserializable_values(
        self,
    ) -> None:
        selection = self.fixture.bind_selection()
        receipt = review_profile_bound_migration_evidence(
            profile=self.fixture.profile,
            authorization=self.fixture.real_authorization(),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
            selection=selection,
        )

        with self.assertRaises(TypeError):
            ProfileBoundEvidenceSelectionV1()
        with self.assertRaises(TypeError):
            MigrationEvidenceReviewReceiptV1()
        for value in (selection, receipt):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(ValueError):
                    copy.copy(value)
                with self.assertRaises(ValueError):
                    copy.deepcopy(value)
                with self.assertRaises(ValueError):
                    pickle.dumps(value)
        self.assertFalse(hasattr(selection, "repository_root"))
        self.assertFalse(hasattr(selection, "review"))
        self.assertFalse(hasattr(receipt, "review"))

    def test_private_selection_binder_requires_exact_test_gates(
        self,
    ) -> None:
        for arguments in (
            {"authorization_phase": "host_baseline"},
            {"baseline_phase": "evidence_review"},
            {"baseline_collector": object()},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(
                    ValueError,
                    "^MIGRATION_EVIDENCE_SELECTION_REJECTED$",
                ):
                    self.fixture.bind_selection(**arguments)

    def test_marker_replacement_invalidates_bound_selection(self) -> None:
        selection = self.fixture.bind_selection()
        marker = self.fixture.root / MARKER_NAME
        marker.write_bytes(b"invalid synthetic marker\n")
        try:
            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_REVIEW_REJECTED$",
            ):
                review_profile_bound_migration_evidence(
                    profile=self.fixture.profile,
                    authorization=self.fixture.real_authorization(),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    observed_at_epoch=OBSERVED_AT,
                    selection=selection,
                )
        finally:
            marker.write_bytes(MARKER_BYTES)

    def test_review_fingerprints_host_baseline_drift(self) -> None:
        first = review_profile_bound_migration_evidence(
            profile=self.fixture.profile,
            authorization=self.fixture.real_authorization(),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
            selection=self.fixture.bind_selection(),
        )
        self.fixture.drift_host_baseline()
        try:
            second = review_profile_bound_migration_evidence(
                profile=self.fixture.profile,
                authorization=self.fixture.real_authorization(),
                operation_fingerprint=OPERATION_FINGERPRINT,
                observed_at_epoch=OBSERVED_AT,
                selection=self.fixture.bind_selection(),
            )
        finally:
            self.fixture.reset_host_baseline()

        self.assertNotEqual(
            first.host_fingerprint,
            second.host_fingerprint,
        )
        self.assertNotEqual(
            first.review_fingerprint,
            second.review_fingerprint,
        )
        self.assertNotEqual(
            first.selection_fingerprint,
            second.selection_fingerprint,
        )

    def test_review_rejects_live_dirty_and_worktree_drift(self) -> None:
        drift_paths = (
            self.fixture.repository / "unexpected.txt",
            self.fixture.worktrees[1] / "unexpected.txt",
        )
        for path in drift_paths:
            with self.subTest(role=path.parent.name):
                selection = self.fixture.bind_selection()
                path.write_text("synthetic drift\n", encoding="utf-8")
                try:
                    with self.assertRaisesRegex(
                        MigrationEvidencePublicationError,
                        "^MIGRATION_EVIDENCE_REVIEW_REJECTED$",
                    ):
                        review_profile_bound_migration_evidence(
                            profile=self.fixture.profile,
                            authorization=(
                                self.fixture.real_authorization()
                            ),
                            operation_fingerprint=(
                                OPERATION_FINGERPRINT
                            ),
                            observed_at_epoch=OBSERVED_AT,
                            selection=selection,
                        )
                finally:
                    path.unlink()

    def test_review_rejects_same_status_approved_source_byte_drift(
        self,
    ) -> None:
        source = self.fixture.repository / "backend" / "service.py"
        original = source.read_bytes()
        selection = self.fixture.bind_selection()
        source.write_bytes(b"VALUE = 'different reviewed bytes'\n")
        try:
            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_REVIEW_REJECTED$",
            ):
                review_profile_bound_migration_evidence(
                    profile=self.fixture.profile,
                    authorization=self.fixture.real_authorization(),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    observed_at_epoch=OBSERVED_AT,
                    selection=selection,
                )
        finally:
            source.write_bytes(original)

    def test_failed_review_releases_selection_for_exact_retry(
        self,
    ) -> None:
        source = self.fixture.repository / "backend" / "service.py"
        original = source.read_bytes()
        selection = self.fixture.bind_selection()
        source.write_bytes(b"VALUE = 'temporary review drift'\n")
        try:
            with self.assertRaises(MigrationEvidencePublicationError):
                review_profile_bound_migration_evidence(
                    profile=self.fixture.profile,
                    authorization=self.fixture.real_authorization(),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    observed_at_epoch=OBSERVED_AT,
                    selection=selection,
                )
        finally:
            source.write_bytes(original)

        receipt = review_profile_bound_migration_evidence(
            profile=self.fixture.profile,
            authorization=self.fixture.real_authorization(),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
            selection=selection,
        )
        self.assertIs(type(receipt), MigrationEvidenceReviewReceiptV1)

    def test_private_claim_is_single_use_and_receipt_bound(self) -> None:
        from backend.migration_evidence_publication.selection import (
            _claim_selection_for_publication,
        )

        selection = self.fixture.bind_selection()
        receipt = review_profile_bound_migration_evidence(
            profile=self.fixture.profile,
            authorization=self.fixture.real_authorization(),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
            selection=selection,
        )

        claim = _claim_selection_for_publication(
            selection=selection,
            receipt=receipt,
        )

        self.assertEqual(
            claim.confirmed_review.review_fingerprint,
            receipt.review_fingerprint,
        )
        with self.assertRaisesRegex(
            ValueError,
            "^MIGRATION_EVIDENCE_SELECTION_REJECTED$",
        ):
            _claim_selection_for_publication(
                selection=selection,
                receipt=receipt,
            )

    def test_claim_rejects_same_path_target_parent_replacement(self) -> None:
        import backend.migration_evidence_publication.synthetic_scope as scope
        from backend.migration_evidence_publication.selection import (
            _claim_selection_for_publication,
        )

        fixture = PublicationReviewFixture()
        try:
            selection = fixture.bind_selection()
            receipt = review_profile_bound_migration_evidence(
                profile=fixture.profile,
                authorization=fixture.real_authorization(),
                operation_fingerprint=OPERATION_FINGERPRINT,
                observed_at_epoch=OBSERVED_AT,
                selection=selection,
            )
            parent_identity = scope.object_identity_fingerprint(
                fixture.target.parent
            )
            real_identity = scope.object_identity_fingerprint
            for child in fixture.target.parent.iterdir():
                child.unlink()
            fixture.target.parent.rmdir()
            fixture.target.parent.mkdir()

            def recycled_identity(path):
                if path == fixture.target.parent:
                    return parent_identity
                return real_identity(path)

            with mock.patch.object(
                scope,
                "object_identity_fingerprint",
                side_effect=recycled_identity,
            ), self.assertRaisesRegex(
                ValueError,
                "^MIGRATION_EVIDENCE_SELECTION_REJECTED$",
            ):
                _claim_selection_for_publication(
                    selection=selection,
                    receipt=receipt,
                )
        finally:
            fixture.close()

    def test_review_rejects_operation_drift_content_free(self) -> None:
        with self.assertRaisesRegex(
            MigrationEvidencePublicationError,
            "^MIGRATION_EVIDENCE_REVIEW_REJECTED$",
        ):
            review_profile_bound_migration_evidence(
                profile=self.fixture.profile,
                authorization=self.fixture.real_authorization(),
                operation_fingerprint=opaque_fingerprint(999),
                observed_at_epoch=OBSERVED_AT,
                selection=self.fixture.bind_selection(),
            )


if __name__ == "__main__":
    unittest.main()
