"""TDD coverage for separately authorized create and verify composition."""

from __future__ import annotations

import hashlib
import json
import subprocess
import unittest

from backend.cutover_contracts import (
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    TestSandboxAuthorizationV1,
)
from backend.migration_evidence_publication import (
    MigrationEvidenceCreatedReceiptV1,
    MigrationEvidencePublicationError,
    MigrationEvidenceReceiptSetV1,
    MigrationEvidenceVerifiedReceiptV1,
    publish_reviewed_migration_evidence,
    require_matching_migration_evidence_receipts,
    review_profile_bound_migration_evidence,
    verify_published_migration_evidence,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.migration_evidence_publication_fixtures import (
    OBSERVED_AT,
    OPERATION_FINGERPRINT,
    PublicationReviewFixture,
)


def _authorization(
    fixture: PublicationReviewFixture,
    authorization_type: type[
        EvidencePublicationAuthorizationV1
        | RealPreflightAuthorizationV1
    ],
    *,
    phase: str,
    operation_fingerprint: str = OPERATION_FINGERPRINT,
) -> object:
    operation = (
        "evidence_publication"
        if authorization_type is EvidencePublicationAuthorizationV1
        else "real_preflight"
    )
    body = {
        "authorization_type": authorization_type.__name__,
        "operation": operation,
        "operation_fingerprint": operation_fingerprint,
        "profile_fingerprint": fixture.profile.profile_fingerprint,
        "governing_master_commit": (
            fixture.profile.governing_master_commit
        ),
        "operator_fingerprint": fixture.profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": OBSERVED_AT - 20,
        "not_before_epoch": OBSERVED_AT - 10,
        "expires_at_epoch": OBSERVED_AT + 300,
    }
    encoded = json.dumps(
        body,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return authorization_type.from_mapping(
        {
            **body,
            "authorization_fingerprint": hashlib.sha256(
                encoded
            ).hexdigest(),
        }
    )


def _review(fixture: PublicationReviewFixture):
    selection = fixture.bind_selection()
    receipt = review_profile_bound_migration_evidence(
        profile=fixture.profile,
        authorization=fixture.real_authorization(),
        operation_fingerprint=OPERATION_FINGERPRINT,
        observed_at_epoch=OBSERVED_AT,
        selection=selection,
    )
    return selection, receipt


def _publish(
    fixture: PublicationReviewFixture,
    selection,
    review,
):
    return publish_reviewed_migration_evidence(
        profile=fixture.profile,
        authorization=_authorization(
            fixture,
            EvidencePublicationAuthorizationV1,
            phase="evidence_publication",
        ),
        operation_fingerprint=OPERATION_FINGERPRINT,
        observed_at_epoch=OBSERVED_AT,
        selection=selection,
        review_receipt=review,
        confirmed_review_fingerprint=review.review_fingerprint,
    )


class MigrationEvidenceCreateVerifyTests(unittest.TestCase):
    def test_create_verify_and_chain_bind_the_same_evidence(self) -> None:
        fixture = PublicationReviewFixture()
        try:
            selection, review = _review(fixture)

            created = _publish(
                fixture,
                selection,
                review,
            )
            package_before = fixture.target.read_bytes()
            verified = verify_published_migration_evidence(
                profile=fixture.profile,
                authorization=_authorization(
                    fixture,
                    RealPreflightAuthorizationV1,
                    phase="evidence_verification",
                ),
                operation_fingerprint=OPERATION_FINGERPRINT,
                observed_at_epoch=OBSERVED_AT,
                created_receipt=created,
            )
            chain = require_matching_migration_evidence_receipts(
                review_receipt=review,
                created_receipt=created,
                verified_receipt=verified,
            )

            self.assertIs(
                type(created),
                MigrationEvidenceCreatedReceiptV1,
            )
            self.assertIs(
                type(verified),
                MigrationEvidenceVerifiedReceiptV1,
            )
            self.assertIs(
                type(chain),
                MigrationEvidenceReceiptSetV1,
            )
            self.assertEqual(
                (
                    created.review_fingerprint,
                    created.package_sha256,
                    created.manifest_sha256,
                    created.package_identity_fingerprint,
                    created.package_counts_fingerprint,
                ),
                (
                    verified.review_fingerprint,
                    verified.package_sha256,
                    verified.manifest_sha256,
                    verified.package_identity_fingerprint,
                    verified.package_counts_fingerprint,
                ),
            )
            self.assertEqual(
                created.review_fingerprint,
                review.review_fingerprint,
            )
            self.assertEqual(
                created.review_counts_fingerprint,
                review.counts_fingerprint,
            )
            self.assertEqual(
                created.package_counts,
                verified.package_counts,
            )
            self.assertEqual(
                fixture.target.read_bytes(),
                package_before,
            )
            public = json.dumps(
                {
                    "review": review.to_mapping(),
                    "created": created.to_mapping(),
                    "verified": verified.to_mapping(),
                    "chain": chain.to_mapping(),
                },
                sort_keys=True,
            )
            for forbidden in (
                str(fixture.root),
                "refs/heads/",
                "worktree-02",
                fixture.profile.governing_master_commit,
            ):
                self.assertNotIn(forbidden, public)
        finally:
            fixture.close()

    def test_create_requires_exact_authorization_and_confirmation(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        try:
            invalid = (
                None,
                TestSandboxAuthorizationV1.create(
                    profile_fingerprint=(
                        fixture.profile.profile_fingerprint
                    ),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    phase="evidence_publication",
                    expires_at_epoch=OBSERVED_AT + 300,
                ),
                _authorization(
                    fixture,
                    RealPreflightAuthorizationV1,
                    phase="evidence_verification",
                ),
                _authorization(
                    fixture,
                    EvidencePublicationAuthorizationV1,
                    phase="evidence_publication",
                    operation_fingerprint=opaque_fingerprint(999),
                ),
            )
            for authorization in invalid:
                selection, review = _review(fixture)
                with self.subTest(
                    authorization=type(authorization).__name__
                ), self.assertRaisesRegex(
                    MigrationEvidencePublicationError,
                    "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
                ):
                    publish_reviewed_migration_evidence(
                        profile=fixture.profile,
                        authorization=authorization,
                        operation_fingerprint=OPERATION_FINGERPRINT,
                        observed_at_epoch=OBSERVED_AT,
                        selection=selection,
                        review_receipt=review,
                        confirmed_review_fingerprint=(
                            review.review_fingerprint
                        ),
                    )
            selection, review = _review(fixture)
            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
            ):
                publish_reviewed_migration_evidence(
                    profile=fixture.profile,
                    authorization=_authorization(
                        fixture,
                        EvidencePublicationAuthorizationV1,
                        phase="evidence_publication",
                    ),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    observed_at_epoch=OBSERVED_AT,
                    selection=selection,
                    review_receipt=review,
                    confirmed_review_fingerprint=opaque_fingerprint(998),
                )
            self.assertFalse(fixture.target.exists())
        finally:
            fixture.close()

    def test_create_rejects_dirty_worktree_ref_and_host_drift(self) -> None:
        drift_cases = ("dirty", "worktree", "ref", "host")
        for drift in drift_cases:
            fixture = PublicationReviewFixture()
            try:
                selection, review = _review(fixture)
                if drift == "dirty":
                    source = (
                        fixture.repository
                        / "backend"
                        / "service.py"
                    )
                    source.write_text(
                        "VALUE = 'post-review drift'\n",
                        encoding="utf-8",
                    )
                elif drift == "worktree":
                    (fixture.worktrees[1] / "unexpected.txt").write_text(
                        "post-review drift\n",
                        encoding="utf-8",
                    )
                elif drift == "ref":
                    subprocess.run(
                        (
                            "git",
                            "commit",
                            "--allow-empty",
                            "-m",
                            "post-review synthetic drift",
                        ),
                        cwd=fixture.worktrees[1],
                        check=True,
                        capture_output=True,
                    )
                else:
                    fixture.drift_host_baseline()
                with self.subTest(drift=drift), self.assertRaisesRegex(
                    MigrationEvidencePublicationError,
                    "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
                ):
                    _publish(fixture, selection, review)
                self.assertFalse(fixture.target.exists())
            finally:
                fixture.close()

    def test_target_collision_is_preserved(self) -> None:
        fixture = PublicationReviewFixture()
        try:
            selection, review = _review(fixture)
            competitor = b"synthetic competitor package"
            fixture.target.write_bytes(competitor)

            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
            ):
                _publish(fixture, selection, review)

            self.assertEqual(fixture.target.read_bytes(), competitor)
        finally:
            fixture.close()

    def test_high_level_verification_rejects_post_create_corruption(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        try:
            selection, review = _review(fixture)
            created = _publish(fixture, selection, review)
            original = fixture.target.read_bytes()
            fixture.target.write_bytes(original[:-32])
            corrupted = fixture.target.read_bytes()

            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_VERIFICATION_REJECTED$",
            ):
                verify_published_migration_evidence(
                    profile=fixture.profile,
                    authorization=_authorization(
                        fixture,
                        RealPreflightAuthorizationV1,
                        phase="evidence_verification",
                    ),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    observed_at_epoch=OBSERVED_AT,
                    created_receipt=created,
                )

            self.assertEqual(fixture.target.read_bytes(), corrupted)
        finally:
            fixture.close()


if __name__ == "__main__":
    unittest.main()
