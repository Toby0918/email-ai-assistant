"""Fresh physical Windows Runtime publication tests for Issue #77."""

from __future__ import annotations

import sys
import unittest

from backend.r2_runtime_publication import (
    RuntimeCrashGap,
    RuntimeFaultSelectorV1,
    RuntimePublicationStatus,
    RuntimeVerificationAuthority,
)
from backend.r2_runtime_publication.testing import bind_test_runtime_transaction
from tests.cutover_managed_activation_fixtures import build_runtime_scenario


@unittest.skipUnless(sys.platform == "win32", "physical Windows claim")
class R2RuntimePublicationWindowsTests(unittest.TestCase):
    def test_prepare_then_publish_proves_exact_offline_runtime(self) -> None:
        with _world() as world:
            transaction = world.transaction()
            receipt = transaction.execute(RuntimeFaultSelectorV1.none())
            self.assertEqual(receipt.status, RuntimePublicationStatus.PUBLISHED)
            self.assertEqual(receipt.python_version, "3.12.13")
            self.assertEqual(receipt.sqlite_version, "3.50.4")
            self.assertGreaterEqual(receipt.dependency_count, 9)
            self.assertEqual(
                receipt.verification_authority,
                RuntimeVerificationAuthority.CANONICAL_LOCK_SELF_VERIFICATION,
            )
            self.assertTrue(world.target.is_dir())
            self.assertFalse(world.staging.exists())
            self.assertTrue(receipt.same_volume)
            self.assertTrue(receipt.complete)
            for boundary in ("runtime_prepare", "runtime_publish"):
                self.assertEqual(
                    [record.fact for record in transaction.records if record.boundary == boundary],
                    ["intent", "effect_observed", "stable_verified", "committed"],
                )

    def test_all_prepare_publish_gaps_retain_and_classify_state(self) -> None:
        for boundary in ("runtime_prepare", "runtime_publish"):
            for gap in RuntimeCrashGap:
                with self.subTest(boundary=boundary, gap=gap.value), _world() as world:
                    transaction = world.transaction()
                    with self.assertRaisesRegex(RuntimeError, "runtime_transaction_interrupted"):
                        transaction.execute(RuntimeFaultSelectorV1.crash(boundary, gap))
                    recovery = transaction.recover()
                    self.assertIn(
                        recovery.status,
                        {RuntimePublicationStatus.RECOVERED, RuntimePublicationStatus.INCIDENT_STOP},
                    )
                    if recovery.status is RuntimePublicationStatus.RECOVERED:
                        self.assertFalse(world.target.exists())

    def test_collision_drift_reparse_and_verification_fail_closed(self) -> None:
        selectors = (
            RuntimeFaultSelectorV1.collision(),
            RuntimeFaultSelectorV1.source_drift(),
            RuntimeFaultSelectorV1.dependency_drift(),
            RuntimeFaultSelectorV1.verification_failure(),
            RuntimeFaultSelectorV1.reparse(),
        )
        for selector in selectors:
            with self.subTest(fault=selector.kind), _world() as world:
                transaction = world.transaction()
                with self.assertRaises((ValueError, RuntimeError)):
                    transaction.execute(selector)
                recovery = transaction.recover()
                self.assertGreaterEqual(recovery.retained_artifact_count, 1)
                self.assertTrue(world.staging.exists() or world.target.exists())


class _World:
    def __init__(self) -> None:
        self.scenario = build_runtime_scenario()
        self.staging = self.scenario.runtime_target.with_name("managed-runtime.prepare")
        self.target = self.scenario.runtime_target
        self.journal = self.scenario.root / "runtime-unit.journal"
        self._transactions = []

    def transaction(self):
        value = bind_test_runtime_transaction(
            python_source=self.scenario.python_source,
            source_manifest=self.scenario.python_source_manifest,
            wheelhouse=self.scenario.wheelhouse,
            dependency_lock=self.scenario.dependency_lock,
            staging=self.staging,
            target=self.target,
            journal=self.journal,
            quiescence_receipt_fingerprint="a" * 64,
        )
        self._transactions.append(value)
        return value

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        for transaction in self._transactions:
            transaction.close()
        self.scenario.close()


def _world() -> _World:
    return _World()


if __name__ == "__main__":
    unittest.main()
