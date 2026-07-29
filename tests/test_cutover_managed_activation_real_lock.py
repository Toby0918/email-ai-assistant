from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_managed_activation import (
    locked_real_artifact_publisher_constructor,
    locked_real_config_publisher_constructor,
    locked_real_database_copier_constructor,
    locked_real_runtime_builder_constructor,
)
from tests.cutover_contract_fixtures import valid_profile_body

MASTER = "7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd"
OBSERVED = 1_900_000_000
CONSTRUCTORS = (
    locked_real_runtime_builder_constructor,
    locked_real_database_copier_constructor,
    locked_real_artifact_publisher_constructor,
    locked_real_config_publisher_constructor,
)


class ManagedActivationRealLockTests(unittest.TestCase):
    def test_all_real_constructors_reject_missing_authorization(self) -> None:
        profile = _profile()
        results = tuple(
            constructor(
                profile=profile,
                authorization=None,
                operation_fingerprint="c" * 64,
                observed_at_epoch=OBSERVED,
            )
            for constructor in CONSTRUCTORS
        )
        self.assertEqual(
            tuple(result.status.value for result in results),
            ("BLOCKED_AUTHORIZATION_MISSING",) * 4,
        )
        self.assertEqual(sum(result.constructed for result in results), 0)

    def test_all_real_constructors_reject_test_authorization(self) -> None:
        profile = _profile()
        operation = "a" * 64
        authorization = TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=operation,
            phase="execute",
            expires_at_epoch=OBSERVED + 600,
        )

        results = tuple(
            constructor(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation,
                observed_at_epoch=OBSERVED,
            )
            for constructor in CONSTRUCTORS
        )

        self.assertEqual(
            tuple(result.status.value for result in results),
            ("BLOCKED_TEST_AUTHORIZATION",) * 4,
        )
        self.assertEqual(sum(result.constructed for result in results), 0)

    def test_exact_real_authorization_still_constructs_nothing(self) -> None:
        profile = _profile()
        operation = "b" * 64
        authorization = CutoverExecutionAuthorizationV1.from_mapping(
            _authorization_mapping(profile, operation)
        )

        results = tuple(
            constructor(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation,
                observed_at_epoch=OBSERVED,
            )
            for constructor in CONSTRUCTORS
        )

        self.assertEqual(
            tuple(result.status.value for result in results),
            ("BLOCKED_NO_APPROVED_COMMAND",) * 4,
        )
        self.assertEqual(sum(result.constructed for result in results), 0)


def _profile() -> CutoverProfileV1:
    body = valid_profile_body()
    body["governing_master_commit"] = MASTER
    return CutoverProfileV1.create(body)


def _authorization_mapping(profile, operation):
    body = {
        "authorization_type": "CutoverExecutionAuthorizationV1",
        "operation": "cutover_execution",
        "operation_fingerprint": operation,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": MASTER,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": "execute",
        "issued_at_epoch": OBSERVED - 100,
        "not_before_epoch": OBSERVED - 50,
        "expires_at_epoch": OBSERVED + 600,
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
