from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_repository_transaction.real_lock import (
    locked_real_repository_transaction_constructor,
)
from tests.cutover_contract_fixtures import valid_profile_body

MASTER = "96fceda6e85316dd6b17ef516adf96491d28cb6d"
OBSERVED = 1_900_000_000


class RepositoryTransactionRealLockTests(unittest.TestCase):
    def test_missing_and_test_authorization_never_construct(self):
        profile = _profile()
        operation = "a" * 64
        test_authorization = TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=operation,
            phase="execute",
            expires_at_epoch=OBSERVED + 600,
        )
        missing = locked_real_repository_transaction_constructor(
            profile=profile,
            authorization=None,
            operation_fingerprint=operation,
            observed_at_epoch=OBSERVED,
        )
        synthetic = locked_real_repository_transaction_constructor(
            profile=profile,
            authorization=test_authorization,
            operation_fingerprint=operation,
            observed_at_epoch=OBSERVED,
        )
        self.assertEqual(missing.status.value, "BLOCKED_AUTHORIZATION_MISSING")
        self.assertEqual(synthetic.status.value, "BLOCKED_TEST_AUTHORIZATION")
        self.assertEqual(missing.constructed + synthetic.constructed, 0)

    def test_exact_real_authorization_still_has_no_approved_command(self):
        profile = _profile()
        operation = "b" * 64
        authorization = CutoverExecutionAuthorizationV1.from_mapping(
            _authorization_mapping(profile, operation)
        )
        result = locked_real_repository_transaction_constructor(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            observed_at_epoch=OBSERVED,
        )
        self.assertEqual(result.status.value, "BLOCKED_NO_APPROVED_COMMAND")
        self.assertEqual((result.blocked, result.constructed), (1, 0))


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
