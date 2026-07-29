"""Content-free output and error tests for Issue #58."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from backend.cutover_service_lifecycle import (
    ActivationFailureKind,
    LifecycleStatus,
)
from tests.test_cutover_service_lifecycle_rollback import (
    JOURNAL_HEAD,
    NOW,
    OPERATION,
    PROFILE,
    _LifecycleHarness,
    recovery_authorization,
    transaction,
)


class ServiceLifecycleLeakageTests(unittest.TestCase):
    def test_reverse_exception_and_bound_values_never_reach_output(self):
        harness = _LifecycleHarness(
            activation_failure=ActivationFailureKind.PERSISTENCE_REJECTED
        )
        lifecycle = transaction(harness, fail_stage="preserved")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            failed = lifecycle.activate_new_service()
            incident = lifecycle.rollback_and_recover_legacy(
                authorization=recovery_authorization(),
                observed_at_epoch=NOW,
            )

        self.assertIs(failed.status, LifecycleStatus.ROLLBACK_REQUIRED)
        self.assertIs(incident.status, LifecycleStatus.INCIDENT_STOP)
        payload = "\n".join(
            (
                repr(failed),
                repr(incident),
                stdout.getvalue(),
                stderr.getvalue(),
            )
        )
        for forbidden in (
            PROFILE,
            OPERATION,
            JOURNAL_HEAD,
            "private fixture detail",
            "D:\\",
            "powershell",
            "command",
            "S-1-",
            "refs/heads/",
        ):
            self.assertNotIn(forbidden, payload)
        self.assertEqual((stdout.getvalue(), stderr.getvalue()), ("", ""))

    def test_public_error_is_one_fixed_code(self):
        lifecycle = transaction(
            _LifecycleHarness(
                activation_failure=(
                    ActivationFailureKind.PERSISTENCE_REJECTED
                )
            )
        )
        lifecycle.activate_new_service()

        with self.assertRaises(Exception) as raised:
            lifecycle.rollback_and_recover_legacy(
                authorization=None, observed_at_epoch=NOW
            )

        self.assertEqual(
            str(raised.exception),
            "lifecycle_recovery_authorization_invalid",
        )


if __name__ == "__main__":
    unittest.main()
