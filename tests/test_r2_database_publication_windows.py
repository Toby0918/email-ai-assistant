"""Physical Windows sandbox tests for Issue #76."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from backend.r2_database_publication import (
    DatabaseCheckpoint,
    DatabaseCrashGap,
    DatabaseFaultSelectorV1,
    DatabaseTransactionStatus,
    QuiescencePrerequisitesV1,
)
from backend.r2_database_publication.testing import (
    bind_test_database_transaction,
    bind_test_legacy_service_controller,
)


@unittest.skipUnless(sys.platform == "win32", "physical Windows claim")
class R2DatabasePublicationWindowsTests(unittest.TestCase):
    def test_quiescence_precedes_first_mutation_and_handle_is_reused(self) -> None:
        with _world() as world:
            transaction = world.transaction()
            result = transaction.execute(DatabaseFaultSelectorV1.none())
            self.assertEqual(result.status, DatabaseTransactionStatus.PUBLISHED)
            self.assertEqual(world.service_state.read_text("ascii"), "stopped")
            self.assertEqual(world.target.read_bytes(), world.source.read_bytes())
            self.assertEqual(result.lease_read_passes, 2)
            self.assertEqual(
                transaction.checkpoints,
                tuple(DatabaseCheckpoint),
            )
            events = transaction.events
            self.assertLess(events.index("prerequisites:verified"), events.index("quiescence:intent"))
            self.assertLess(events.index("quiescence:intent"), events.index("service:stopped"))
            self.assertLess(events.index("service:stopped"), events.index("database_prepare:intent"))

    def test_quiescence_can_be_bound_before_later_publication_mutations(self) -> None:
        with _world() as world:
            transaction = world.transaction()
            stopped = transaction.quiesce()
            self.assertEqual(stopped.status, "STOPPED")
            self.assertFalse(world.staging.exists())
            self.assertFalse(world.target.exists())
            result = transaction.execute(DatabaseFaultSelectorV1.none())
            self.assertEqual(result.status, DatabaseTransactionStatus.PUBLISHED)
            self.assertEqual(transaction.events.count("service:stopped"), 1)

    def test_generic_result_cannot_forge_stopped_receipt(self) -> None:
        with _world() as world:
            transaction = world.transaction()
            with self.assertRaisesRegex(TypeError, "validated construction"):
                type(transaction)._stopped_receipt_type()

    def test_each_sidecar_checkpoint_fails_closed_without_source_cleanup(self) -> None:
        for checkpoint in DatabaseCheckpoint:
            with self.subTest(checkpoint=checkpoint.value), _world() as world:
                selector = DatabaseFaultSelectorV1.sidecar(checkpoint, "-wal")
                transaction = world.transaction()
                with self.assertRaisesRegex(ValueError, "database_sidecar_present"):
                    transaction.execute(selector)
                recovery = transaction.recover()
                sidecar = world.source.with_name(world.source.name + "-wal")
                self.assertTrue(sidecar.is_file())
                self.assertEqual(world.source.read_bytes(), world.source_bytes)
                self.assertEqual(
                    recovery.status,
                    DatabaseTransactionStatus.INCIDENT_STOP,
                )

    def test_prepare_and_publish_each_have_durable_four_fact_chain(self) -> None:
        with _world() as world:
            transaction = world.transaction()
            transaction.execute(DatabaseFaultSelectorV1.none())
            records = transaction.records
            for boundary in ("database_prepare", "database_publish"):
                self.assertEqual(
                    [record.fact for record in records if record.boundary == boundary],
                    ["intent", "effect_observed", "stable_verified", "committed"],
                )

    def test_every_crash_gap_is_classified_and_exactly_recoverable(self) -> None:
        for boundary in ("database_prepare", "database_publish"):
            for gap in DatabaseCrashGap:
                with self.subTest(boundary=boundary, gap=gap.value), _world() as world:
                    transaction = world.transaction()
                    selector = DatabaseFaultSelectorV1.crash(boundary, gap)
                    with self.assertRaisesRegex(RuntimeError, "database_transaction_interrupted"):
                        transaction.execute(selector)
                    recovery = transaction.recover()
                    self.assertIn(
                        recovery.status,
                        {
                            DatabaseTransactionStatus.RECOVERED,
                            DatabaseTransactionStatus.INCIDENT_STOP,
                        },
                    )
                    self.assertEqual(world.source.read_bytes(), world.source_bytes)
                    if recovery.status is DatabaseTransactionStatus.RECOVERED:
                        self.assertFalse(world.target.exists())

    def test_collision_drift_and_partial_staging_are_retained(self) -> None:
        for selector in (
            DatabaseFaultSelectorV1.collision(),
            DatabaseFaultSelectorV1.source_drift(),
            DatabaseFaultSelectorV1.partial_staging(),
        ):
            with self.subTest(selector=selector.kind), _world() as world:
                transaction = world.transaction()
                with self.assertRaises((ValueError, RuntimeError)):
                    transaction.execute(selector)
                recovery = transaction.recover()
                self.assertTrue(world.staging.exists() or world.target.exists())
                self.assertNotEqual(recovery.retained_artifact_count, 0)


class _World:
    def __init__(self, directory: Path | None = None) -> None:
        self._temporary = tempfile.TemporaryDirectory(
            dir=str(directory) if directory is not None else None
        )
        self.root = Path(self._temporary.name)
        self.source = self.root / "legacy.sqlite3"
        self.target = self.root / "LocalData" / "analysis.sqlite3"
        self.staging = self.root / "LocalData" / "analysis.sqlite3.prepare"
        self.journal = self.root / "database.journal"
        self.service_state = self.root / "legacy-service.state"
        self.target.parent.mkdir()
        connection = sqlite3.connect(self.source)
        connection.execute("CREATE TABLE analysis (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO analysis(value) VALUES ('synthetic')")
        connection.commit()
        connection.close()
        self.source_bytes = self.source.read_bytes()
        self.service_state.write_text("running", encoding="ascii")
        self._transactions = []
        self.prerequisites = QuiescencePrerequisitesV1.create(
            preflight_fingerprint="1" * 64,
            evidence_fingerprint="2" * 64,
            fresh_gate_fingerprint="3" * 64,
        )

    def transaction(self):
        controller = bind_test_legacy_service_controller(self.service_state)
        transaction = bind_test_database_transaction(
            source=self.source,
            staging=self.staging,
            target=self.target,
            journal=self.journal,
            prerequisites=self.prerequisites,
            service_controller=controller,
        )
        self._transactions.append(transaction)
        return transaction

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        for transaction in self._transactions:
            transaction.close()
        self._temporary.cleanup()


def _world() -> _World:
    return _World()


if __name__ == "__main__":
    unittest.main()
