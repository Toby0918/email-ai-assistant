"""Complete two-start provider-disabled validation lifecycle for Issue #81."""

from __future__ import annotations

import unittest

from backend.r2_validation_lifecycle import (
    ValidationBoundary,
    ValidationFaultSelectorV1,
    ValidationLifecycle,
    ValidationStatus,
)
from tests.r2_validation_lifecycle_fixture import (
    NOW,
    SyntheticValidationAdapters,
    approved_slice,
)


class R2ValidationLifecycleTests(unittest.TestCase):
    def test_complete_lifecycle_has_exact_order_counts_and_two_starts(self):
        adapters = SyntheticValidationAdapters()
        result = ValidationLifecycle.create(
            approved=approved_slice(),
            adapters=adapters.bundle(),
            nonce_factory=iter(
                (
                    "11111111-1111-4111-8111-111111111111",
                    "22222222-2222-4222-8222-222222222222",
                )
            ).__next__,
            now=lambda: NOW,
            fault=ValidationFaultSelectorV1.none(),
        ).run()

        self.assertIs(result.status, ValidationStatus.VALIDATED)
        self.assertEqual(result.completed_boundaries, 11)
        self.assertEqual(result.analysis_count, 1)
        self.assertEqual(result.database_write_count, 1)
        self.assertEqual(result.provider_attempts, 0)
        self.assertEqual(adapters.analysis_calls, 1)
        self.assertEqual(adapters.row_writes, 1)
        self.assertEqual(
            adapters.calls,
            [
                "start_start_a",
                "health",
                "analysis",
                "confirm",
                "row",
                "stop",
                "database_proof",
                "audit_stopped_layout",
                "start_start_b",
                "health",
                "audit_final_running_health",
            ],
        )
        first, second = adapters.starts
        self.assertNotEqual((first.pid, first.start_time_ns, first.nonce), (
            second.pid,
            second.start_time_ns,
            second.nonce,
        ))
        for name in (
            "runtime_fingerprint",
            "config_fingerprint",
            "profile_fingerprint",
            "data_role_fingerprint",
            "port",
            "primary_provider",
            "fallback_provider",
        ):
            self.assertEqual(getattr(first, name), getattr(second, name))

    def test_wrong_public_result_confirmation_or_row_cannot_pass(self):
        for mode in (
            "wrong_source",
            "provider_attempt",
            "unsafe",
            "confirmation_drift",
            "duplicate_row",
            "start_b_identity_drift",
        ):
            adapters = SyntheticValidationAdapters()
            adapters.mode = mode
            with self.subTest(mode=mode):
                result = self._run(adapters)
                self.assertIs(result.status, ValidationStatus.ROLLBACK_REQUIRED)

    def test_every_boundary_has_deterministic_crash_and_failure_classification(self):
        for boundary in ValidationBoundary:
            for factory, expected in (
                (ValidationFaultSelectorV1.crash, ValidationStatus.ROLLBACK_REQUIRED),
                (
                    ValidationFaultSelectorV1.deterministic_failure,
                    ValidationStatus.ROLLBACK_REQUIRED,
                ),
                (
                    ValidationFaultSelectorV1.ambiguous_failure,
                    ValidationStatus.INCIDENT_STOP,
                ),
            ):
                with self.subTest(boundary=boundary, factory=factory.__name__):
                    adapters = SyntheticValidationAdapters()
                    result = self._run(adapters, fault=factory(boundary))
                    self.assertIs(result.status, expected)
                    self.assertLess(result.completed_boundaries, 11)

    def test_lifecycle_and_fault_selector_are_single_use_and_closed(self):
        adapters = SyntheticValidationAdapters()
        lifecycle = ValidationLifecycle.create(
            approved=approved_slice(),
            adapters=adapters.bundle(),
            nonce_factory=iter(
                (
                    "11111111-1111-4111-8111-111111111111",
                    "22222222-2222-4222-8222-222222222222",
                )
            ).__next__,
            now=lambda: NOW,
            fault=ValidationFaultSelectorV1.none(),
        )
        self.assertIs(lifecycle.run().status, ValidationStatus.VALIDATED)
        with self.assertRaises(ValueError):
            lifecycle.run()
        with self.assertRaises(TypeError):
            ValidationFaultSelectorV1()

    def _run(self, adapters, *, fault=None):
        return ValidationLifecycle.create(
            approved=approved_slice(),
            adapters=adapters.bundle(),
            nonce_factory=iter(
                (
                    "11111111-1111-4111-8111-111111111111",
                    "22222222-2222-4222-8222-222222222222",
                )
            ).__next__,
            now=lambda: NOW,
            fault=fault or ValidationFaultSelectorV1.none(),
        ).run()


if __name__ == "__main__":
    unittest.main()
