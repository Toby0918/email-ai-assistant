from __future__ import annotations

import hashlib
import unittest

from backend.cutover_contracts import (
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    TestSandboxAuthorizationV1,
)
from backend.migration_evidence_publication.operator_entry import (
    EvidenceOperatorEntryStatus,
    locked_evidence_publication_entry,
    locked_evidence_review_entry,
    locked_evidence_verification_entry,
)
from tests.cutover_contract_fixtures import (
    canonical_json,
    opaque_fingerprint,
    valid_profile_body,
)


_NOW = 1_800_000_100
_OPERATION = opaque_fingerprint(901)


def _profile() -> CutoverProfileV1:
    return CutoverProfileV1.create(valid_profile_body())


def _authorization(
    authorization_type: type[
        RealPreflightAuthorizationV1
        | EvidencePublicationAuthorizationV1
    ],
    *,
    profile: CutoverProfileV1,
    phase: str,
) -> object:
    operation = (
        "evidence_publication"
        if authorization_type is EvidencePublicationAuthorizationV1
        else "real_preflight"
    )
    body = {
        "authorization_type": authorization_type.__name__,
        "operation": operation,
        "operation_fingerprint": _OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": _NOW - 10,
        "not_before_epoch": _NOW - 5,
        "expires_at_epoch": _NOW + 300,
    }
    mapping = {
        **body,
        "authorization_fingerprint": hashlib.sha256(
            canonical_json(body)
        ).hexdigest(),
    }
    return authorization_type.from_json(canonical_json(mapping))


class LockedEvidenceOperatorEntryTests(unittest.TestCase):
    def test_missing_authorization_is_rejected_without_execution(self) -> None:
        result = locked_evidence_review_entry(
            profile=_profile(),
            authorization=None,
            operation_fingerprint=_OPERATION,
            observed_at_epoch=_NOW,
        )

        self.assertEqual(
            result.status,
            EvidenceOperatorEntryStatus.BLOCKED_AUTHORIZATION_MISSING,
        )
        self.assertEqual((result.blocked, result.executed), (1, 0))

    def test_wrong_phase_authorization_is_rejected(self) -> None:
        profile = _profile()
        authorization = _authorization(
            RealPreflightAuthorizationV1,
            profile=profile,
            phase="evidence_verification",
        )

        result = locked_evidence_review_entry(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=_OPERATION,
            observed_at_epoch=_NOW,
        )

        self.assertEqual(
            result.status,
            EvidenceOperatorEntryStatus.BLOCKED_AUTHORIZATION_WRONG_PHASE,
        )
        self.assertEqual((result.blocked, result.executed), (1, 0))

    def test_test_authorization_is_rejected_by_every_real_entry(self) -> None:
        profile = _profile()
        cases = (
            (
                locked_evidence_review_entry,
                "evidence_review",
            ),
            (
                locked_evidence_publication_entry,
                "evidence_publication",
            ),
            (
                locked_evidence_verification_entry,
                "evidence_verification",
            ),
        )
        for entry, phase in cases:
            authorization = TestSandboxAuthorizationV1.create(
                profile_fingerprint=profile.profile_fingerprint,
                operation_fingerprint=_OPERATION,
                phase=phase,
                expires_at_epoch=_NOW + 300,
            )
            with self.subTest(phase=phase):
                result = entry(
                    profile=profile,
                    authorization=authorization,
                    operation_fingerprint=_OPERATION,
                    observed_at_epoch=_NOW,
                )
                self.assertEqual(
                    result.status,
                    EvidenceOperatorEntryStatus.BLOCKED_TEST_AUTHORIZATION,
                )
                self.assertEqual((result.blocked, result.executed), (1, 0))

    def test_valid_real_authorization_still_cannot_execute_before_issue_39(
        self,
    ) -> None:
        profile = _profile()
        cases = (
            (
                locked_evidence_review_entry,
                _authorization(
                    RealPreflightAuthorizationV1,
                    profile=profile,
                    phase="evidence_review",
                ),
            ),
            (
                locked_evidence_publication_entry,
                _authorization(
                    EvidencePublicationAuthorizationV1,
                    profile=profile,
                    phase="evidence_publication",
                ),
            ),
            (
                locked_evidence_verification_entry,
                _authorization(
                    RealPreflightAuthorizationV1,
                    profile=profile,
                    phase="evidence_verification",
                ),
            ),
        )
        for entry, authorization in cases:
            with self.subTest(entry=entry.__name__):
                result = entry(
                    profile=profile,
                    authorization=authorization,
                    operation_fingerprint=_OPERATION,
                    observed_at_epoch=_NOW,
                )
                self.assertEqual(
                    result.status,
                    EvidenceOperatorEntryStatus.BLOCKED_NO_APPROVED_COMMAND,
                )
                self.assertEqual((result.blocked, result.executed), (1, 0))

    def test_result_repr_contains_no_authorization_values(self) -> None:
        profile = _profile()
        authorization = _authorization(
            EvidencePublicationAuthorizationV1,
            profile=profile,
            phase="evidence_publication",
        )

        result = locked_evidence_publication_entry(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=_OPERATION,
            observed_at_epoch=_NOW,
        )
        rendered = repr(result)

        self.assertNotIn(_OPERATION, rendered)
        self.assertNotIn(profile.profile_fingerprint, rendered)
        self.assertNotIn(authorization.authorization_fingerprint, rendered)


if __name__ == "__main__":
    unittest.main()
