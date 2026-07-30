"""Default-locked real operator entries for Issue #59."""

from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_composition_contracts import OperatorEntryStatus
from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    RecoveryAuthorizationV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_transaction_composition import (
    locked_cutover_transaction_composition_constructor,
    locked_execute_entry,
    locked_resume_entry,
    locked_rollback_entry,
)
from backend.migration_evidence_publication_composition import (
    locked_evidence_publication_entry,
    locked_migration_evidence_publication_composition_constructor,
)
from backend.real_host_preflight_composition import (
    locked_current_topology_entry,
    locked_evidence_review_entry,
    locked_evidence_verification_entry,
    locked_final_audit_readiness_entry,
    locked_host_baseline_entry,
    locked_real_host_preflight_composition_constructor,
    locked_recovery_inspection_entry,
)
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(9001)


ENTRY_CASES = (
    (
        locked_real_host_preflight_composition_constructor,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "current_topology_preflight",
    ),
    (
        locked_current_topology_entry,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "current_topology_preflight",
    ),
    (
        locked_host_baseline_entry,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "host_baseline",
    ),
    (
        locked_evidence_review_entry,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "evidence_review",
    ),
    (
        locked_evidence_verification_entry,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "evidence_verification",
    ),
    (
        locked_final_audit_readiness_entry,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "final_audit_readiness",
    ),
    (
        locked_recovery_inspection_entry,
        RealPreflightAuthorizationV1,
        "real_preflight",
        "recovery_inspection",
    ),
    (
        locked_migration_evidence_publication_composition_constructor,
        EvidencePublicationAuthorizationV1,
        "evidence_publication",
        "evidence_publication",
    ),
    (
        locked_evidence_publication_entry,
        EvidencePublicationAuthorizationV1,
        "evidence_publication",
        "evidence_publication",
    ),
    (
        locked_cutover_transaction_composition_constructor,
        CutoverExecutionAuthorizationV1,
        "cutover_execution",
        "execute",
    ),
    (
        locked_execute_entry,
        CutoverExecutionAuthorizationV1,
        "cutover_execution",
        "execute",
    ),
    (
        locked_resume_entry,
        CutoverExecutionAuthorizationV1,
        "cutover_execution",
        "resume",
    ),
    (
        locked_rollback_entry,
        RecoveryAuthorizationV1,
        "recovery",
        "rollback",
    ),
)


class CutoverCompositionOperatorLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = CutoverProfileV1.create(valid_profile_body())

    def test_exact_real_authorization_still_returns_blocked(self) -> None:
        for entry, authorization_type, operation, phase in ENTRY_CASES:
            authorization = _authorization(
                authorization_type,
                self.profile,
                operation=operation,
                phase=phase,
            )
            with self.subTest(entry=entry.__name__):
                result = _call(entry, self.profile, authorization)
                self.assertIs(
                    result.status,
                    OperatorEntryStatus.BLOCKED_NO_APPROVED_COMMAND,
                )
                self.assertEqual((result.blocked, result.executed), (1, 0))

    def test_missing_test_wrong_phase_and_expired_are_rejected(self) -> None:
        for entry, authorization_type, operation, phase in ENTRY_CASES:
            test_authorization = TestSandboxAuthorizationV1.create(
                profile_fingerprint=self.profile.profile_fingerprint,
                operation_fingerprint=OPERATION,
                phase=phase,
                expires_at_epoch=OBSERVED_AT + 60,
            )
            wrong_phase, wrong_phase_status = _wrong_phase_authorization(
                authorization_type,
                self.profile,
                operation,
                phase,
            )
            expired = _authorization(
                authorization_type,
                self.profile,
                operation=operation,
                phase=phase,
                expires_at_epoch=OBSERVED_AT,
            )
            cases = (
                (
                    None,
                    OperatorEntryStatus.BLOCKED_AUTHORIZATION_MISSING,
                ),
                (
                    test_authorization,
                    OperatorEntryStatus.BLOCKED_TEST_AUTHORIZATION,
                ),
                (
                    wrong_phase,
                    wrong_phase_status,
                ),
                (
                    expired,
                    OperatorEntryStatus.BLOCKED_AUTHORIZATION_EXPIRED,
                ),
            )
            for authorization, expected in cases:
                with self.subTest(entry=entry.__name__, expected=expected):
                    result = _call(entry, self.profile, authorization)
                    self.assertIs(result.status, expected)
                    self.assertEqual(
                        (result.blocked, result.executed),
                        (1, 0),
                    )

    def test_results_are_content_free(self) -> None:
        result = _call(
            locked_execute_entry,
            self.profile,
            _authorization(
                CutoverExecutionAuthorizationV1,
                self.profile,
                operation="cutover_execution",
                phase="execute",
            ),
        )
        public = repr(result)
        for forbidden in (
            self.profile.governing_master_commit,
            self.profile.operator_fingerprint,
            OPERATION,
            "D:\\",
            "S-1-",
            "refs/heads",
            "git ",
            "credential",
            "mailbox",
            "database row",
        ):
            self.assertNotIn(forbidden, public)


def _call(entry, profile, authorization):
    return entry(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=OPERATION,
        observed_at_epoch=OBSERVED_AT,
    )


def _authorization(
    authorization_type,
    profile,
    *,
    operation: str,
    phase: str,
    expires_at_epoch: int = OBSERVED_AT + 60,
):
    body = {
        "authorization_type": authorization_type.AUTHORIZATION_TYPE,
        "operation": operation,
        "operation_fingerprint": OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": OBSERVED_AT - 20,
        "not_before_epoch": OBSERVED_AT - 10,
        "expires_at_epoch": expires_at_epoch,
    }
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return authorization_type.from_mapping(
        {
            **body,
            "authorization_fingerprint": hashlib.sha256(encoded).hexdigest(),
        }
    )


def _other_phase(authorization_type, phase: str) -> str:
    values = {
        RealPreflightAuthorizationV1: (
            "current_topology_preflight",
            "host_baseline",
        ),
        EvidencePublicationAuthorizationV1: ("evidence_publication",),
        CutoverExecutionAuthorizationV1: ("execute", "resume"),
        RecoveryAuthorizationV1: ("rollback", "legacy_recovery"),
    }[authorization_type]
    if len(values) == 1:
        return values[0]
    return next(item for item in values if item != phase)


def _wrong_phase_authorization(
    authorization_type,
    profile,
    operation: str,
    phase: str,
):
    if authorization_type is EvidencePublicationAuthorizationV1:
        return (
            _authorization(
                RealPreflightAuthorizationV1,
                profile,
                operation="real_preflight",
                phase="evidence_review",
            ),
            OperatorEntryStatus.BLOCKED_AUTHORIZATION_WRONG_TYPE,
        )
    return (
        _authorization(
            authorization_type,
            profile,
            operation=operation,
            phase=_other_phase(authorization_type, phase),
        ),
        OperatorEntryStatus.BLOCKED_AUTHORIZATION_WRONG_PHASE,
    )


if __name__ == "__main__":
    unittest.main()
