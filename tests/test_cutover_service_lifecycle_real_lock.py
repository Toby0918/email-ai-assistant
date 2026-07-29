"""Default-locked real lifecycle constructor tests for Issue #58."""

from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_service_lifecycle import (
    locked_real_service_lifecycle_constructor,
)
from tests.cutover_contract_fixtures import valid_profile_body


MASTER = "dcb53169f7c8e73b6bf5387a02b18d4e6741d6ee"
NOW = 1_900_000_000
OPERATION = "8" * 64


class ServiceLifecycleRealLockTests(unittest.TestCase):
    def test_empty_exact_type_values_are_fixed_blocked(self):
        profile = _profile()
        values = {
            "profile": profile,
            "execution_authorization": _execution(profile),
            "recovery_authorization": _recovery(profile),
            "operation_fingerprint": OPERATION,
            "observed_at_epoch": NOW,
        }
        malformed = (
            ("profile", object.__new__(CutoverProfileV1)),
            (
                "execution_authorization",
                object.__new__(CutoverExecutionAuthorizationV1),
            ),
            (
                "recovery_authorization",
                object.__new__(RecoveryAuthorizationV1),
            ),
        )
        for name, value in malformed:
            with self.subTest(name=name):
                result = locked_real_service_lifecycle_constructor(
                    **{**values, name: value}
                )
                self.assertEqual(
                    result.status.value,
                    "BLOCKED_AUTHORIZATION_INVALID",
                )
                self.assertEqual((result.blocked, result.constructed), (1, 0))

    def test_malformed_profile_operation_and_time_are_fixed_blocked(self):
        profile = _profile()

        class DuckProfile:
            governing_master_commit = MASTER

        for overrides in (
            {"profile": DuckProfile()},
            {"operation_fingerprint": object()},
            {"observed_at_epoch": True},
        ):
            with self.subTest(field=next(iter(overrides))):
                values = {
                    "profile": profile,
                    "execution_authorization": _execution(profile),
                    "recovery_authorization": _recovery(profile),
                    "operation_fingerprint": OPERATION,
                    "observed_at_epoch": NOW,
                }
                values.update(overrides)

                result = locked_real_service_lifecycle_constructor(**values)

                self.assertEqual(
                    result.status.value,
                    "BLOCKED_AUTHORIZATION_INVALID",
                )
                self.assertEqual((result.blocked, result.constructed), (1, 0))

    def test_missing_either_authorization_constructs_nothing(self) -> None:
        profile = _profile()
        execution = _execution(profile)
        recovery = _recovery(profile)

        missing_execution = locked_real_service_lifecycle_constructor(
            profile=profile,
            execution_authorization=None,
            recovery_authorization=recovery,
            operation_fingerprint=OPERATION,
            observed_at_epoch=NOW,
        )
        missing_recovery = locked_real_service_lifecycle_constructor(
            profile=profile,
            execution_authorization=execution,
            recovery_authorization=None,
            operation_fingerprint=OPERATION,
            observed_at_epoch=NOW,
        )

        self.assertEqual(
            missing_execution.status.value,
            "BLOCKED_EXECUTION_AUTHORIZATION_MISSING",
        )
        self.assertEqual(
            missing_recovery.status.value,
            "BLOCKED_RECOVERY_AUTHORIZATION_MISSING",
        )
        self.assertEqual(
            missing_execution.constructed + missing_recovery.constructed, 0
        )

    def test_test_authorization_is_never_real_authority(self) -> None:
        profile = _profile()
        test = TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=OPERATION,
            phase="execute",
            expires_at_epoch=NOW + 600,
        )

        result = locked_real_service_lifecycle_constructor(
            profile=profile,
            execution_authorization=test,
            recovery_authorization=test,
            operation_fingerprint=OPERATION,
            observed_at_epoch=NOW,
        )

        self.assertEqual(result.status.value, "BLOCKED_TEST_AUTHORIZATION")
        self.assertEqual((result.blocked, result.constructed), (1, 0))

    def test_both_exact_authorizations_still_have_no_command(self) -> None:
        profile = _profile()

        result = locked_real_service_lifecycle_constructor(
            profile=profile,
            execution_authorization=_execution(profile),
            recovery_authorization=_recovery(profile),
            operation_fingerprint=OPERATION,
            observed_at_epoch=NOW,
        )

        self.assertEqual(result.status.value, "BLOCKED_NO_APPROVED_COMMAND")
        self.assertEqual((result.blocked, result.constructed), (1, 0))


def _profile() -> CutoverProfileV1:
    body = valid_profile_body()
    body["governing_master_commit"] = MASTER
    return CutoverProfileV1.create(body)


def _execution(profile):
    return CutoverExecutionAuthorizationV1.from_mapping(
        _authorization(
            profile,
            authorization_type="CutoverExecutionAuthorizationV1",
            operation="cutover_execution",
            phase="execute",
        )
    )


def _recovery(profile):
    return RecoveryAuthorizationV1.from_mapping(
        _authorization(
            profile,
            authorization_type="RecoveryAuthorizationV1",
            operation="recovery",
            phase="rollback",
        )
    )


def _authorization(
    profile, *, authorization_type: str, operation: str, phase: str
):
    body = {
        "authorization_type": authorization_type,
        "operation": operation,
        "operation_fingerprint": OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": MASTER,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": NOW - 100,
        "not_before_epoch": NOW - 50,
        "expires_at_epoch": NOW + 600,
    }
    payload = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return {
        **body,
        "authorization_fingerprint": hashlib.sha256(payload).hexdigest(),
    }


if __name__ == "__main__":
    unittest.main()
