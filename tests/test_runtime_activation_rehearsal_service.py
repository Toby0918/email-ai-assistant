"""Provider-disabled synthetic service activation tests."""

from __future__ import annotations

from dataclasses import replace
import unittest

from backend.runtime_activation_rehearsal import (
    COMPLETED_RESULT,
    FAILED_RESULT,
    ManagedActivationAdapters,
    rehearse_managed_runtime_activation,
)
from backend.runtime_activation_rehearsal.adapters import (
    AnalysisProbeEvidence,
    AnalysisProbeRequest,
    DatabaseAdapter,
    HealthProbeEvidence,
    HealthProbeRequest,
    LifecycleAdapter,
    LifecycleStopRequest,
    LifecycleStopEvidence,
    ProbeAdapter,
    ServiceStartEvidence,
    ServiceStartRequest,
    SqliteSnapshot,
    StoppedProbeEvidence,
    StoppedServiceGate,
)
from tests.test_runtime_activation_rehearsal_managed_zones import (
    _artifact_bundle,
)
from tests.test_runtime_activation_rehearsal_sqlite import (
    _destination_snapshot,
    _lifecycle_stop,
    _publication,
    _source_snapshot,
    _stopped_probe,
    _target,
)


class RuntimeActivationRehearsalServiceTests(unittest.TestCase):
    def test_provider_disabled_loopback_analysis_completes(self) -> None:
        events: list[str] = []
        starts: list[ServiceStartRequest] = []
        adapters = _service_bundle(events=events, starts=starts)

        result = rehearse_managed_runtime_activation(adapters=adapters)

        self.assertEqual(result, COMPLETED_RESULT)
        self.assertEqual(len(starts), 1)
        request = starts[0]
        self.assertEqual(request.runtime_identity, "runtime-1")
        self.assertEqual(request.venv_identity, "venv-1")
        self.assertEqual(request.executable_identity, "python-1")
        self.assertEqual(request.llm_provider, "disabled")
        self.assertEqual(
            request.text_fallback_provider,
            "disabled",
        )
        self.assertFalse(request.provider_keys_present)
        self.assertFalse(request.private_knowledge_enabled)
        self.assertEqual(request.loopback_host, "127.0.0.1")
        activation_events = events[events.index("lifecycle.start"):]
        self.assertEqual(
            activation_events,
            [
                "lifecycle.start",
                "probe.health",
                "probe.analyze",
                "lifecycle.stop",
                "probe.stopped",
                "database.destination",
                "database.source",
                "filesystem.layout",
            ],
        )

    def test_start_evidence_cannot_enable_provider_or_external_access(
        self,
    ) -> None:
        cases = {
            "primary": {"llm_provider": "openai"},
            "fallback": {"text_fallback_provider": "deepseek"},
            "key": {"provider_keys_present": True},
            "private": {"private_knowledge_enabled": True},
            "provider_client": {"provider_client_created": True},
            "external_network": {"external_network_used": True},
            "wrong_host": {"loopback_host": "localhost"},
            "boolean_schema": {"schema_version": True},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _service_bundle(
                    events=events,
                    start_changes=changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertNotIn("probe.health", events)
                self.assertGreaterEqual(
                    events.count("lifecycle.stop"),
                    2,
                )

    def test_health_failure_stops_service_without_analysis(self) -> None:
        cases = {
            "unhealthy": {"healthy": False},
            "not_loopback": {"loopback_only": False},
            "provider_enabled": {"llm_provider": "openai"},
            "external_network": {"external_network_used": True},
            "boolean_schema": {"schema_version": True},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _service_bundle(
                    events=events,
                    health_changes=changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertNotIn("probe.analyze", events)
                self.assertGreaterEqual(
                    events.count("lifecycle.stop"),
                    2,
                )

    def test_analysis_must_be_one_persisted_rule_fallback(self) -> None:
        cases = {
            "not_confirmed": {"user_confirmed": False},
            "two_calls": {"analysis_calls": 2},
            "provider_route": {"route": "openai"},
            "not_persisted": {"persisted": False},
            "bad_id": {"saved_id": 0},
            "provider_call": {"primary_provider_calls": 1},
            "mailbox": {"mailbox_accessed": True},
            "vault": {"vault_accessed": True},
            "private_store": {"private_store_accessed": True},
            "boolean_schema": {"schema_version": True},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _service_bundle(
                    events=events,
                    analysis_changes=changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertEqual(events.count("probe.analyze"), 1)
                self.assertGreaterEqual(
                    events.count("lifecycle.stop"),
                    2,
                )

    def test_final_stop_and_persisted_count_are_mandatory(self) -> None:
        cases = {
            "final_stop": (
                {"stopped": False, "process_present": True},
                {},
                {},
            ),
            "final_probe": (
                {},
                {"pid_present": True},
                {},
            ),
            "count": (
                {},
                {},
                {"aggregate_count": 4},
            ),
            "destination_integrity": (
                {},
                {},
                {"integrity_ok": False},
            ),
            "boolean_count": (
                {},
                {},
                {"aggregate_count": True},
            ),
        }
        for name, (stop_changes, probe_changes, post_changes) in (
            cases.items()
        ):
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _service_bundle(
                    events=events,
                    final_stop_changes=stop_changes,
                    final_probe_changes=probe_changes,
                    post_destination_changes=post_changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                if name in {"final_stop", "final_probe"}:
                    final_probe_index = max(
                        index
                        for index, event in enumerate(events)
                        if event == "probe.stopped"
                    )
                    self.assertFalse(
                        any(
                            event.startswith("database.")
                            for event in events[final_probe_index + 1:]
                        )
                    )

    def test_invalid_start_and_wrong_final_service_forbid_db_recheck(
        self,
    ) -> None:
        events: list[str] = []
        adapters = _service_bundle(
            events=events,
            start_changes={"llm_provider": "openai"},
            final_stop_changes={
                "service_identity": "unrelated-service",
            },
            final_probe_changes={
                "service_identity": "unrelated-service",
            },
        )

        result = rehearse_managed_runtime_activation(adapters=adapters)

        self.assertEqual(result, FAILED_RESULT)
        final_probe_index = max(
            index
            for index, event in enumerate(events)
            if event == "probe.stopped"
        )
        self.assertFalse(
            any(
                event.startswith("database.")
                for event in events[final_probe_index + 1:]
            )
        )


def _service_bundle(
    *,
    events: list[str],
    starts: list[ServiceStartRequest] | None = None,
    start_changes: dict[str, object] | None = None,
    health_changes: dict[str, object] | None = None,
    analysis_changes: dict[str, object] | None = None,
    final_stop_changes: dict[str, object] | None = None,
    final_probe_changes: dict[str, object] | None = None,
    post_destination_changes: dict[str, object] | None = None,
    source_after_changes: dict[str, object] | None = None,
) -> ManagedActivationAdapters:
    base = _artifact_bundle(events=events)
    source = _source_snapshot()
    destination_before = _destination_snapshot()
    destination_values: dict[str, object] = {
        "size_bytes": 16384,
        "sha256": "5" * 64,
        "aggregate_count": 3,
    }
    destination_values.update(post_destination_changes or {})
    destination_after = replace(
        destination_before,
        **destination_values,
    )
    source_after = replace(source, **(source_after_changes or {}))
    stop_calls = 0
    stopped_calls = 0
    source_calls = 0
    destination_calls = 0

    def stop(request: LifecycleStopRequest) -> LifecycleStopEvidence:
        nonlocal stop_calls
        events.append("lifecycle.stop")
        final = stop_calls > 0
        value = _lifecycle_stop(
            stop_token="stop-2" if final else "stop-1",
            phase=request.phase,
            activation_token=request.activation_token,
        )
        if final:
            value = replace(value, **(final_stop_changes or {}))
        stop_calls += 1
        return value

    def prove_stopped(
        request: LifecycleStopRequest,
    ) -> StoppedProbeEvidence:
        nonlocal stopped_calls
        events.append("probe.stopped")
        final = stopped_calls > 0
        value = _stopped_probe(
            stop_token="stop-2" if final else "stop-1",
            phase=request.phase,
            activation_token=request.activation_token,
        )
        if final:
            value = replace(value, **(final_probe_changes or {}))
        stopped_calls += 1
        return value

    def observe_source() -> SqliteSnapshot:
        nonlocal source_calls
        events.append("database.source")
        source_calls += 1
        return source if source_calls < 3 else source_after

    def observe_target() -> object:
        events.append("database.target")
        return _target()

    def publish(gate: StoppedServiceGate) -> object:
        events.append("database.publish")
        if gate.stop_token != "stop-1":
            raise AssertionError("wrong initial stop gate")
        return _publication()

    def observe_destination() -> SqliteSnapshot:
        nonlocal destination_calls
        events.append("database.destination")
        destination_calls += 1
        if destination_calls == 1:
            return destination_before
        return destination_after

    def start(request: ServiceStartRequest) -> ServiceStartEvidence:
        events.append("lifecycle.start")
        if starts is not None:
            starts.append(request)
        return replace(
            _service_start(request),
            **(start_changes or {}),
        )

    def health(request: HealthProbeRequest) -> HealthProbeEvidence:
        events.append("probe.health")
        return replace(
            _health(request),
            **(health_changes or {}),
        )

    def analyze(request: AnalysisProbeRequest) -> AnalysisProbeEvidence:
        events.append("probe.analyze")
        return replace(
            _analysis(request),
            **(analysis_changes or {}),
        )

    return replace(
        base,
        database=DatabaseAdapter(
            observe_source=observe_source,
            observe_destination_target=observe_target,
            publish_create_only=publish,
            observe_destination=observe_destination,
        ),
        lifecycle=LifecycleAdapter(stop=stop, start=start),
        probe=ProbeAdapter(
            observe_runtime=base.probe.observe_runtime,
            prove_stopped=prove_stopped,
            reviewed_artifact=base.probe.reviewed_artifact,
            observe_artifact_destination=(
                base.probe.observe_artifact_destination
            ),
            health=health,
            analyze=analyze,
        ),
    )


def _service_start(
    request: ServiceStartRequest,
) -> ServiceStartEvidence:
    return ServiceStartEvidence(
        schema_version=1,
        started=True,
        activation_token=request.activation_token,
        service_identity=request.service_identity,
        runtime_identity=request.runtime_identity,
        venv_identity=request.venv_identity,
        executable_identity=request.executable_identity,
        database_identity=request.database_identity,
        attachment_temp_identity=request.attachment_temp_identity,
        log_identity=request.log_identity,
        pid_identity=request.pid_identity,
        config_identity=request.config_identity,
        llm_provider="disabled",
        text_fallback_provider="disabled",
        provider_keys_present=False,
        private_knowledge_enabled=False,
        provider_client_created=False,
        external_network_used=False,
        loopback_host="127.0.0.1",
    )


def _health(request: HealthProbeRequest) -> HealthProbeEvidence:
    return HealthProbeEvidence(
        schema_version=1,
        activation_token=request.activation_token,
        service_identity=request.service_identity,
        loopback_host=request.loopback_host,
        healthy=True,
        loopback_only=True,
        llm_provider="disabled",
        text_fallback_provider="disabled",
        provider_calls=0,
        external_network_used=False,
    )


def _analysis(
    request: AnalysisProbeRequest,
) -> AnalysisProbeEvidence:
    return AnalysisProbeEvidence(
        schema_version=1,
        activation_token=request.activation_token,
        service_identity=request.service_identity,
        database_identity=request.database_identity,
        user_confirmed=True,
        synthetic=True,
        analysis_calls=1,
        route="rule_fallback",
        saved_id=3,
        persisted=True,
        primary_provider_calls=0,
        fallback_provider_calls=0,
        mailbox_accessed=False,
        vault_accessed=False,
        private_store_accessed=False,
        credentials_accessed=False,
        external_network_used=False,
    )


if __name__ == "__main__":
    unittest.main()
