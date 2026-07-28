"""Real mutation construction stays locked before Issue #39."""

from __future__ import annotations

import unittest

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.cutover_host_mutation.operator_entry import (
    MutationConstructorStatus,
    locked_real_mutation_constructor,
)
from tests.cutover_journal_fixtures import valid_operation_contracts


_NOW = 1_800_000_100


class CutoverHostMutationOperatorTests(unittest.TestCase):
    def test_missing_execution_authorization_cannot_construct(self) -> None:
        profile, forward, _recovery = valid_operation_contracts()

        result = locked_real_mutation_constructor(
            profile=profile,
            authorization=None,
            operation_fingerprint=forward.operation_fingerprint,
            observed_at_epoch=_NOW,
        )

        self.assertIs(
            result.status,
            MutationConstructorStatus.BLOCKED_AUTHORIZATION_MISSING,
        )
        self.assertEqual((result.blocked, result.constructed), (1, 0))

    def test_test_authorization_is_explicitly_rejected(self) -> None:
        profile, forward, _recovery = valid_operation_contracts()
        authorization = TestSandboxAuthorizationV1.create(
            profile_fingerprint=profile.profile_fingerprint,
            operation_fingerprint=forward.operation_fingerprint,
            phase="execute",
            expires_at_epoch=_NOW + 100,
        )

        result = locked_real_mutation_constructor(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=forward.operation_fingerprint,
            observed_at_epoch=_NOW,
        )

        self.assertIs(
            result.status,
            MutationConstructorStatus.BLOCKED_TEST_AUTHORIZATION,
        )
        self.assertEqual((result.blocked, result.constructed), (1, 0))

    def test_valid_execution_authorization_still_has_no_approved_command(
        self,
    ) -> None:
        profile, forward, _recovery = valid_operation_contracts()

        result = locked_real_mutation_constructor(
            profile=profile,
            authorization=forward,
            operation_fingerprint=forward.operation_fingerprint,
            observed_at_epoch=_NOW,
        )

        self.assertIs(
            result.status,
            MutationConstructorStatus.BLOCKED_NO_APPROVED_COMMAND,
        )
        self.assertEqual((result.blocked, result.constructed), (1, 0))
        rendered = repr(result)
        self.assertNotIn(profile.profile_fingerprint, rendered)
        self.assertNotIn(forward.authorization_fingerprint, rendered)


if __name__ == "__main__":
    unittest.main()
