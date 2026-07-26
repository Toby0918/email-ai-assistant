"""Stopped-service and SQLite publication rehearsal tests."""

from __future__ import annotations

from dataclasses import replace
import unittest

from backend.runtime_activation_rehearsal import (
    FAILED_RESULT,
    ManagedActivationAdapters,
    rehearse_managed_runtime_activation,
)
from backend.runtime_activation_rehearsal.adapters import (
    DatabaseAdapter,
    DatabasePublicationEvidence,
    LifecycleAdapter,
    LifecycleStopRequest,
    LifecycleStopEvidence,
    ProbeAdapter,
    SqliteSnapshot,
    StoppedProbeEvidence,
    StoppedServiceGate,
    TargetEvidence,
)
from tests.test_runtime_activation_rehearsal_runtime import _runtime_bundle


class RuntimeActivationRehearsalSqliteTests(unittest.TestCase):
    def test_stopped_proof_precedes_create_only_database_publication(
        self,
    ) -> None:
        events: list[str] = []
        adapters = _database_bundle(events=events)

        result = rehearse_managed_runtime_activation(adapters=adapters)

        self.assertEqual(result, FAILED_RESULT)
        stop_index = events.index("lifecycle.stop")
        probe_index = events.index("probe.stopped")
        first_database = min(
            index
            for index, event in enumerate(events)
            if event.startswith("database.")
        )
        self.assertLess(stop_index, probe_index)
        self.assertLess(probe_index, first_database)
        self.assertEqual(
            events[first_database:first_database + 5],
            [
                "database.source",
                "database.target",
                "database.publish",
                "database.destination",
                "database.source",
            ],
        )

    def test_unconfirmed_stop_prevents_every_database_call(self) -> None:
        cases = {
            "lifecycle_running": (
                {"health_reachable": True, "stopped": False},
                {},
            ),
            "probe_running": (
                {},
                {"process_present": True, "stopped": False},
            ),
            "token_mismatch": (
                {},
                {"stop_token": "stop-racer"},
            ),
            "boolean_schema": (
                {"schema_version": True},
                {},
            ),
        }
        for name, (lifecycle_changes, probe_changes) in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _database_bundle(
                    events=events,
                    lifecycle_changes=lifecycle_changes,
                    stopped_probe_changes=probe_changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertFalse(
                    any(
                        event.startswith("database.")
                        for event in events
                    )
                )

    def test_invalid_source_or_existing_target_prevents_publication(
        self,
    ) -> None:
        cases = {
            "source_integrity": (
                {"integrity_ok": False},
                {},
            ),
            "source_sidecar": (
                {"sidecars": ("email_agent.sqlite3-wal",)},
                {},
            ),
            "source_reparse": (
                {"has_reparse_component": True},
                {},
            ),
            "source_boolean_schema": (
                {"schema_version": True},
                {},
            ),
            "existing_target": (
                {},
                {"absent": False},
            ),
            "target_reparse": (
                {},
                {"parent_has_reparse_component": True},
            ),
        }
        for name, (source_changes, target_changes) in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _database_bundle(
                    events=events,
                    source_changes=source_changes,
                    target_changes=target_changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertNotIn("database.publish", events)

    def test_publication_and_destination_must_match_source(self) -> None:
        cases = {
            "not_create_only": (
                {"create_only": False},
                {},
                {},
            ),
            "source_not_preserved": (
                {"source_preserved": False},
                {},
                {},
            ),
            "same_identity": (
                {"destination_identity": "database-source"},
                {"identity": "database-source"},
                {},
            ),
            "hash": (
                {},
                {"sha256": "2" * 64},
                {},
            ),
            "count": (
                {},
                {"aggregate_count": 3},
                {},
            ),
            "source_race": (
                {},
                {},
                {"sha256": "3" * 64},
            ),
        }
        for name, (publication, destination, source_after) in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _database_bundle(
                    events=events,
                    publication_changes=publication,
                    destination_changes=destination,
                    source_after_changes=source_after,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertNotIn("filesystem.artifact_source", events)


def _database_bundle(
    *,
    events: list[str],
    lifecycle_changes: dict[str, object] | None = None,
    stopped_probe_changes: dict[str, object] | None = None,
    source_changes: dict[str, object] | None = None,
    target_changes: dict[str, object] | None = None,
    publication_changes: dict[str, object] | None = None,
    destination_changes: dict[str, object] | None = None,
    source_after_changes: dict[str, object] | None = None,
) -> ManagedActivationAdapters:
    base = _runtime_bundle(events=events)
    source_before = replace(
        _source_snapshot(),
        **(source_changes or {}),
    )
    source_after = replace(
        source_before,
        **(source_after_changes or {}),
    )
    target = replace(_target(), **(target_changes or {}))
    publication = replace(
        _publication(),
        **(publication_changes or {}),
    )
    destination = replace(
        _destination_snapshot(),
        **(destination_changes or {}),
    )
    source_calls = 0

    def stop(request: LifecycleStopRequest) -> LifecycleStopEvidence:
        events.append("lifecycle.stop")
        return replace(
            _lifecycle_stop(
                phase=request.phase,
                activation_token=request.activation_token,
            ),
            **(lifecycle_changes or {}),
        )

    def prove_stopped(
        request: LifecycleStopRequest,
    ) -> StoppedProbeEvidence:
        events.append("probe.stopped")
        return replace(
            _stopped_probe(
                phase=request.phase,
                activation_token=request.activation_token,
            ),
            **(stopped_probe_changes or {}),
        )

    def observe_source() -> SqliteSnapshot:
        nonlocal source_calls
        events.append("database.source")
        source_calls += 1
        return source_before if source_calls == 1 else source_after

    def observe_target() -> TargetEvidence:
        events.append("database.target")
        return target

    def publish(gate: StoppedServiceGate) -> DatabasePublicationEvidence:
        events.append("database.publish")
        self_gate = gate
        if (
            self_gate.service_identity != "service-1"
            or self_gate.stop_token != "stop-1"
        ):
            raise AssertionError("wrong stopped gate")
        return publication

    def observe_destination() -> SqliteSnapshot:
        events.append("database.destination")
        return destination

    def artifact_source() -> object:
        events.append("filesystem.artifact_source")
        raise RuntimeError("artifact boundary")

    return replace(
        base,
        filesystem=replace(
            base.filesystem,
            observe_artifact_source=artifact_source,
        ),
        database=DatabaseAdapter(
            observe_source=observe_source,
            observe_destination_target=observe_target,
            publish_create_only=publish,
            observe_destination=observe_destination,
        ),
        lifecycle=LifecycleAdapter(stop=stop, start=base.lifecycle.start),
        probe=replace(
            base.probe,
            prove_stopped=prove_stopped,
        ),
    )


def _lifecycle_stop(
    *,
    stop_token: str = "stop-1",
    phase: str = "pre_publication",
    activation_token: str = "activation-not-started",
) -> LifecycleStopEvidence:
    return LifecycleStopEvidence(
        schema_version=1,
        service_identity="service-1",
        stop_token=stop_token,
        phase=phase,
        activation_token=activation_token,
        stopped=True,
        process_present=False,
        health_reachable=False,
        pid_present=False,
    )


def _stopped_probe(
    *,
    stop_token: str = "stop-1",
    phase: str = "pre_publication",
    activation_token: str = "activation-not-started",
) -> StoppedProbeEvidence:
    return StoppedProbeEvidence(
        schema_version=1,
        service_identity="service-1",
        stop_token=stop_token,
        phase=phase,
        activation_token=activation_token,
        stopped=True,
        process_present=False,
        health_reachable=False,
        pid_present=False,
    )


def _source_snapshot() -> SqliteSnapshot:
    return SqliteSnapshot(
        schema_version=1,
        present=True,
        identity="database-source",
        parent_identity="source-parent",
        size_bytes=12288,
        sha256="1" * 64,
        canonical=True,
        has_reparse_component=False,
        sidecars=(),
        integrity_ok=True,
        schema_complete=True,
        aggregate_count=2,
        query_only=True,
    )


def _target() -> TargetEvidence:
    return TargetEvidence(
        schema_version=1,
        parent_identity="zone-local_data",
        absent=True,
        canonical=True,
        parent_has_reparse_component=False,
    )


def _publication() -> DatabasePublicationEvidence:
    return DatabasePublicationEvidence(
        schema_version=1,
        created=True,
        create_only=True,
        target_was_absent=True,
        service_identity="service-1",
        stop_token="stop-1",
        source_identity="database-source",
        destination_identity="database-destination",
        source_preserved=True,
    )


def _destination_snapshot() -> SqliteSnapshot:
    return replace(
        _source_snapshot(),
        identity="database-destination",
        parent_identity="zone-local_data",
    )


if __name__ == "__main__":
    unittest.main()
