"""Fresh physical Windows CRX publication tests for Issue #78."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from backend.r2_crx_publication import (
    CrxCrashGap,
    CrxFaultSelectorV1,
    CrxPendingState,
    CrxPublicationStatus,
)
from backend.r2_crx_publication.testing import bind_test_crx_transaction


@unittest.skipUnless(sys.platform == "win32", "physical Windows claim")
class R2CrxPublicationWindowsTests(unittest.TestCase):
    def test_exact_reviewed_crx_is_prepared_published_and_held(self) -> None:
        with _world() as world:
            transaction = world.transaction()
            receipt = transaction.execute(CrxFaultSelectorV1.none())
            self.assertEqual(receipt.status, CrxPublicationStatus.PUBLISHED)
            self.assertEqual(receipt.format_version, 3)
            self.assertEqual(receipt.size_bytes, len(world.payload))
            self.assertEqual(world.target.read_bytes(), world.payload)
            self.assertTrue(receipt.source_held_through_final_verify)
            self.assertTrue(receipt.target_held_through_final_verify)
            self.assertEqual(receipt.pending_state, CrxPendingState.EFFECT_PRESENT_EXACT)
            for boundary in ("crx_prepare", "crx_publish"):
                self.assertEqual(
                    [record.fact for record in transaction.records if record.boundary == boundary],
                    ["intent", "effect_observed", "stable_verified", "committed"],
                )

    def test_every_prepare_publish_gap_is_exactly_classified(self) -> None:
        for boundary in ("crx_prepare", "crx_publish"):
            for gap in CrxCrashGap:
                with self.subTest(boundary=boundary, gap=gap.value), _world() as world:
                    transaction = world.transaction()
                    with self.assertRaisesRegex(RuntimeError, "crx_transaction_interrupted"):
                        transaction.execute(CrxFaultSelectorV1.crash(boundary, gap))
                    recovery = transaction.recover()
                    self.assertIn(
                        recovery.pending_state,
                        {
                            CrxPendingState.EFFECT_ABSENT_EXACT,
                            CrxPendingState.EFFECT_PRESENT_EXACT,
                            CrxPendingState.EFFECT_AMBIGUOUS,
                        },
                    )
                    if recovery.status is CrxPublicationStatus.RECOVERED:
                        self.assertFalse(world.target.exists())

    def test_collision_race_replacement_reparse_drift_partial_and_verify_fail(self) -> None:
        selectors = (
            CrxFaultSelectorV1.collision(),
            CrxFaultSelectorV1.target_race(),
            CrxFaultSelectorV1.source_replacement(),
            CrxFaultSelectorV1.reparse(),
            CrxFaultSelectorV1.hash_drift(),
            CrxFaultSelectorV1.size_drift(),
            CrxFaultSelectorV1.partial_staging(),
            CrxFaultSelectorV1.verification_failure(),
        )
        for selector in selectors:
            with self.subTest(fault=selector.kind), _world() as world:
                transaction = world.transaction()
                with self.assertRaises((ValueError, RuntimeError, PermissionError)):
                    transaction.execute(selector)
                recovery = transaction.recover()
                self.assertGreaterEqual(recovery.retained_artifact_count, 1)
                self.assertEqual(world.source.read_bytes(), world.payload)

    def test_pending_staging_blocks_a_fresh_generation(self) -> None:
        with _world() as world:
            world.staging.write_bytes(b"pending")
            with self.assertRaisesRegex(ValueError, "crx_pending_generation"):
                world.transaction()
            self.assertEqual(world.staging.read_bytes(), b"pending")


class _World:
    def __init__(self) -> None:
        self.owner = tempfile.TemporaryDirectory(
            prefix="issue78-synthetic-",
            dir=Path(sys.executable).anchor,
        )
        self.root = Path(self.owner.name)
        self.source = self.root / "reviewed-extension.crx"
        header = b"synthetic-crx3-header"
        self.payload = (
            b"Cr24"
            + (3).to_bytes(4, "little")
            + len(header).to_bytes(4, "little")
            + header
            + b"PK\x03\x04synthetic-reviewed-payload"
        )
        self.source.write_bytes(self.payload)
        artifacts = self.root / "Artifacts"
        artifacts.mkdir()
        self.staging = artifacts / "email-ai-assistant.crx.prepare"
        self.target = artifacts / "email-ai-assistant.crx"
        self.journal = self.root / "crx-unit.journal"
        self._transactions = []

    def transaction(self):
        value = bind_test_crx_transaction(
            source=self.source,
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
        self.owner.cleanup()


def _world() -> _World:
    return _World()


if __name__ == "__main__":
    unittest.main()
