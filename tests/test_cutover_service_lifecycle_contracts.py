"""Public contract tests for Issue #58 service lifecycle values."""

from __future__ import annotations

import unittest
import uuid

from backend.cutover_service_lifecycle import (
    LegacyRecoveryConfigV1,
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
)


FP = "a" * 64
PROFILE = "b" * 64
RUNTIME = "c" * 64
CONFIG = "d" * 64
DATA = "e" * 64


class ServiceLifecycleContractTests(unittest.TestCase):
    def test_dedicated_legacy_config_is_environment_independent(self) -> None:
        config = LegacyRecoveryConfigV1.create()

        self.assertEqual(config.primary_provider, "disabled")
        self.assertEqual(config.fallback_provider, "disabled")
        self.assertFalse(config.reads_environment)
        self.assertEqual(
            set(config.to_mapping()),
            {
                "config_type",
                "primary_provider",
                "fallback_provider",
                "reads_environment",
            },
        )

    def test_start_and_health_bind_exact_service_identity(self) -> None:
        nonce = str(uuid.uuid4())
        start = ServiceStartEvidenceV1.create(
            role=ServiceRole.NEW,
            pid=4120,
            start_time_ns=1_900_000_000_000_000_000,
            executable_fingerprint=FP,
            port=8765,
            port_owner_pid=4120,
            profile_fingerprint=PROFILE,
            runtime_fingerprint=RUNTIME,
            config_fingerprint=CONFIG,
            data_role_fingerprint=DATA,
            nonce=nonce,
            primary_provider="disabled",
            fallback_provider="disabled",
        )
        health = ServiceHealthEvidenceV1.create_from_start(start)

        self.assertEqual(health.role, ServiceRole.NEW.value)
        self.assertEqual(health.nonce, nonce)
        self.assertEqual(health.pid, health.port_owner_pid)
        self.assertEqual(health.primary_provider, "disabled")
        self.assertEqual(health.fallback_provider, "disabled")
        self.assertTrue(health.healthy)


if __name__ == "__main__":
    unittest.main()
