"""Security behavior tests for Issue #54 nominal receipt composition."""

from __future__ import annotations

import copy
import io
import json
import logging
import os
import pickle
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from backend.cutover_contracts import (
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    TestSandboxAuthorizationV1,
)
from backend.migration_evidence_publication import (
    MigrationEvidenceCreatedReceiptV1,
    MigrationEvidencePublicationError,
    MigrationEvidenceReceiptSetV1,
    MigrationEvidenceReviewReceiptV1,
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
from tests.test_migration_evidence_publication_create_verify import (
    _authorization,
    _publish,
    _review,
)


ROOT = Path(__file__).resolve().parents[1]
PASSTHROUGH_ENV_KEYS = {
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SystemRoot",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
}


def _verify(
    fixture: PublicationReviewFixture,
    created: MigrationEvidenceCreatedReceiptV1,
):
    return verify_published_migration_evidence(
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


def _complete_workflow(fixture: PublicationReviewFixture):
    selection, review = _review(fixture)
    created = _publish(fixture, selection, review)
    verified = _verify(fixture, created)
    receipt_set = require_matching_migration_evidence_receipts(
        review_receipt=review,
        created_receipt=created,
        verified_receipt=verified,
    )
    return review, created, verified, receipt_set


class MigrationEvidencePublicationReceiptSecurityTests(
    unittest.TestCase
):
    def test_nominal_receipts_and_set_are_closed_and_content_free(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        stdout = io.StringIO()
        stderr = io.StringIO()
        logs = io.StringIO()
        handler = logging.StreamHandler(logs)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                values = _complete_workflow(fixture)

            expected_types = (
                MigrationEvidenceReviewReceiptV1,
                MigrationEvidenceCreatedReceiptV1,
                MigrationEvidenceVerifiedReceiptV1,
                MigrationEvidenceReceiptSetV1,
            )
            for receipt_type in expected_types:
                with self.subTest(
                    receipt_type=receipt_type.__name__,
                    boundary="constructor",
                ), self.assertRaises(TypeError):
                    receipt_type()
            for value in values:
                with self.subTest(
                    receipt_type=type(value).__name__,
                    boundary="closed",
                ):
                    self.assertFalse(hasattr(value, "__dict__"))
                    with self.assertRaises(ValueError):
                        setattr(value, "forged", opaque_fingerprint(991))
                    with self.assertRaises(ValueError):
                        delattr(value, "forged")
                    with self.assertRaises(ValueError):
                        copy.copy(value)
                    with self.assertRaises(ValueError):
                        copy.deepcopy(value)
                    with self.assertRaises(ValueError):
                        pickle.dumps(value)
                    with self.assertRaises(
                        (AttributeError, ValueError),
                    ):
                        object.__setattr__(
                            value,
                            "forged",
                            opaque_fingerprint(992),
                        )
                    forged = object.__new__(type(value))
                    with self.assertRaises(ValueError):
                        forged.to_mapping()

            review, created, verified, receipt_set = values
            forged_created = object.__new__(
                MigrationEvidenceCreatedReceiptV1
            )
            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_RECEIPT_CHAIN_REJECTED$",
            ):
                require_matching_migration_evidence_receipts(
                    review_receipt=review,
                    created_receipt=forged_created,
                    verified_receipt=verified,
                )

            public = json.dumps(
                {
                    "review": review.to_mapping(),
                    "created": created.to_mapping(),
                    "verified": verified.to_mapping(),
                    "set": receipt_set.to_mapping(),
                },
                sort_keys=True,
            ) + repr(values)
            head = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=fixture.repository,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
            forbidden = {
                str(fixture.root),
                str(fixture.target),
                fixture.target.name,
                fixture.profile.governing_master_commit,
                head,
                *fixture.refs,
                *(path.name for path in fixture.worktrees),
            }
            for raw in forbidden:
                self.assertNotIn(raw, public)
                self.assertNotIn(raw, stdout.getvalue())
                self.assertNotIn(raw, stderr.getvalue())
                self.assertNotIn(raw, logs.getvalue())
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(logs.getvalue(), "")
        finally:
            root_logger.removeHandler(handler)
            fixture.close()

    def test_verification_rejects_invalid_authorization_before_claim(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        try:
            selection, review = _review(fixture)
            created = _publish(fixture, selection, review)
            before = fixture.target.read_bytes()
            invalid = (
                None,
                TestSandboxAuthorizationV1.create(
                    profile_fingerprint=(
                        fixture.profile.profile_fingerprint
                    ),
                    operation_fingerprint=OPERATION_FINGERPRINT,
                    phase="evidence_verification",
                    expires_at_epoch=OBSERVED_AT + 300,
                ),
                _authorization(
                    fixture,
                    RealPreflightAuthorizationV1,
                    phase="evidence_review",
                ),
                _authorization(
                    fixture,
                    EvidencePublicationAuthorizationV1,
                    phase="evidence_publication",
                ),
                _authorization(
                    fixture,
                    RealPreflightAuthorizationV1,
                    phase="evidence_verification",
                    operation_fingerprint=opaque_fingerprint(997),
                ),
            )
            for authorization in invalid:
                with self.subTest(
                    authorization=type(authorization).__name__,
                ), self.assertRaisesRegex(
                    MigrationEvidencePublicationError,
                    "^MIGRATION_EVIDENCE_VERIFICATION_REJECTED$",
                ):
                    verify_published_migration_evidence(
                        profile=fixture.profile,
                        authorization=authorization,
                        operation_fingerprint=OPERATION_FINGERPRINT,
                        observed_at_epoch=OBSERVED_AT,
                        created_receipt=created,
                    )
                self.assertEqual(fixture.target.read_bytes(), before)

            verified = _verify(fixture, created)
            self.assertIs(
                type(verified),
                MigrationEvidenceVerifiedReceiptV1,
            )
        finally:
            fixture.close()

    def test_mixed_receipts_are_rejected_without_poisoning_valid_sets(
        self,
    ) -> None:
        first = PublicationReviewFixture()
        second = PublicationReviewFixture()
        try:
            first_values = _complete_workflow(first)
            second_values = _complete_workflow(second)
            first_review, first_created, first_verified, _ = first_values
            second_review, second_created, second_verified, _ = (
                second_values
            )
            mixed = (
                (first_review, second_created, second_verified),
                (first_review, first_created, second_verified),
                (second_review, first_created, first_verified),
            )
            for review, created, verified in mixed:
                with self.subTest(
                    review=review.receipt_fingerprint,
                    created=created.receipt_fingerprint,
                    verified=verified.receipt_fingerprint,
                ), self.assertRaisesRegex(
                    MigrationEvidencePublicationError,
                    "^MIGRATION_EVIDENCE_RECEIPT_CHAIN_REJECTED$",
                ):
                    require_matching_migration_evidence_receipts(
                        review_receipt=review,
                        created_receipt=created,
                        verified_receipt=verified,
                    )

            for review, created, verified in (
                first_values[:3],
                second_values[:3],
            ):
                receipt_set = (
                    require_matching_migration_evidence_receipts(
                        review_receipt=review,
                        created_receipt=created,
                        verified_receipt=verified,
                    )
                )
                self.assertIs(
                    type(receipt_set),
                    MigrationEvidenceReceiptSetV1,
                )
        finally:
            first.close()
            second.close()

    def test_selection_create_and_created_target_verify_are_single_use(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        try:
            selection, review = _review(fixture)
            created = _publish(fixture, selection, review)
            published = fixture.target.read_bytes()

            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
            ):
                _publish(fixture, selection, review)
            self.assertEqual(fixture.target.read_bytes(), published)

            verified = _verify(fixture, created)
            self.assertIs(
                type(verified),
                MigrationEvidenceVerifiedReceiptV1,
            )
            with self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_VERIFICATION_REJECTED$",
            ):
                _verify(fixture, created)
            self.assertEqual(fixture.target.read_bytes(), published)
        finally:
            fixture.close()

    def test_fresh_imports_keep_create_and_verify_capabilities_apart(
        self,
    ) -> None:
        cases = (
            (
                (
                    "from backend.migration_evidence_publication "
                    "import publish_reviewed_migration_evidence;"
                ),
                {
                    "backend.migration_evidence.verification",
                    "backend.migration_evidence_verifier",
                },
                "backend.migration_evidence_publication.publication",
            ),
            (
                (
                    "from backend.migration_evidence_publication "
                    "import verify_published_migration_evidence;"
                ),
                {
                    "backend.migration_evidence.package",
                    (
                        "backend.migration_evidence_publication."
                        "creator_bridge"
                    ),
                    (
                        "backend.migration_evidence_publication."
                        "publication"
                    ),
                },
                (
                    "backend.migration_evidence_publication."
                    "verification_composition"
                ),
            ),
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key in PASSTHROUGH_ENV_KEYS
        }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        for import_code, forbidden, expected in cases:
            blocked = repr(tuple(sorted(forbidden)))
            code = (
                "import sys;"
                f"{import_code}"
                f"blocked={blocked};"
                "loaded=sorted(name for name in sys.modules "
                "if any(name==item or name.startswith(item+'.') "
                "for item in blocked));"
                f"expected={expected!r};"
                "sys.stdout.write('isolated' if not loaded "
                "and expected in sys.modules else 'loaded')"
            )
            with self.subTest(expected=expected):
                completed = subprocess.run(
                    (sys.executable, "-B", "-c", code),
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    shell=False,
                )
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(completed.stdout, "isolated")
                self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
