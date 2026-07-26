"""Temporary synthetic end-to-end activation rehearsal tests."""

from __future__ import annotations

from dataclasses import replace
import platform
import sqlite3
import unittest

from backend.runtime_activation_rehearsal import (
    COMPLETED_RESULT,
    FAILED_RESULT,
    rehearse_managed_runtime_activation,
)
from tests.runtime_activation_rehearsal_fixtures import (
    SyntheticActivationWorld,
)


class RuntimeActivationRehearsalIntegrationTests(unittest.TestCase):
    def test_temporary_synthetic_activation_completes(self) -> None:
        self.assertEqual(platform.python_version(), "3.12.13")
        self.assertEqual(sqlite3.sqlite_version, "3.50.4")
        with SyntheticActivationWorld() as world:
            source_before = world.source_state()
            legacy_before = world.legacy_state()
            runtime_source_before = world.runtime_source_state()

            result = rehearse_managed_runtime_activation(
                adapters=world.adapters()
            )

            self.assertEqual(result, COMPLETED_RESULT)
            world.assert_source_preserved(source_before)
            world.assert_legacy_preserved(legacy_before)
            world.assert_runtime_source_preserved(
                runtime_source_before
            )
            world.assert_successful_activation()
            world.assert_no_forbidden_access()

    def test_required_failure_matrix_preserves_every_source(self) -> None:
        failures = (
            "runtime_existing",
            "runtime_race",
            "database_race",
            "artifact_existing",
            "dependency",
            "reparse",
            "integrity",
            "health",
        )
        for failure in failures:
            with self.subTest(failure=failure):
                with SyntheticActivationWorld(
                    failure=failure
                ) as world:
                    source_before = world.source_state()
                    legacy_before = world.legacy_state()
                    runtime_source_before = world.runtime_source_state()
                    competitor_before = world.competitor_state()

                    result = rehearse_managed_runtime_activation(
                        adapters=world.adapters()
                    )

                    self.assertEqual(result, FAILED_RESULT)
                    world.assert_source_preserved(source_before)
                    world.assert_legacy_preserved(legacy_before)
                    world.assert_runtime_source_preserved(
                        runtime_source_before
                    )
                    world.assert_competitor_preserved(
                        competitor_before
                    )
                    world.assert_failure_stopped()
                    world.assert_no_forbidden_access()

    def test_stop_proof_precedes_actual_synthetic_sqlite_copy(
        self,
    ) -> None:
        with SyntheticActivationWorld() as world:
            result = rehearse_managed_runtime_activation(
                adapters=world.adapters()
            )

            self.assertEqual(result, COMPLETED_RESULT)
            stop_index = world.events.index("lifecycle.stop")
            stopped_index = world.events.index("probe.stopped")
            copy_index = world.events.index("database.copy")
            self.assertLess(stop_index, stopped_index)
            self.assertLess(stopped_index, copy_index)

    def test_artifact_source_tamper_cannot_redefine_review(self) -> None:
        with SyntheticActivationWorld() as world:
            source_before = world.source_state()
            world.artifact_source.write_bytes(
                b"tampered after independent review"
            )

            result = rehearse_managed_runtime_activation(
                adapters=world.adapters()
            )

            self.assertEqual(result, FAILED_RESULT)
            self.assertFalse(world.artifact_target.exists())
            self.assertNotIn("lifecycle.start", world.events)
            world.assert_source_preserved(source_before)

    def test_initial_stop_identity_must_match_activated_service(self) -> None:
        with SyntheticActivationWorld() as world:
            adapters = world.adapters()
            original_stop = adapters.lifecycle.stop
            original_start = adapters.lifecycle.start
            original_probe = adapters.probe.prove_stopped
            stop_calls = 0
            probe_calls = 0

            def stop(request: object) -> object:
                nonlocal stop_calls
                stop_calls += 1
                value = original_stop(request)
                if stop_calls == 1:
                    return replace(
                        value,
                        service_identity="unrelated-service",
                    )
                return value

            def prove_stopped(request: object) -> object:
                nonlocal probe_calls
                probe_calls += 1
                value = original_probe(request)
                if probe_calls == 1:
                    return replace(
                        value,
                        service_identity="unrelated-service",
                    )
                return value

            def start(request: object) -> object:
                return replace(
                    original_start(request),
                    service_identity="service-1",
                )

            hostile = replace(
                adapters,
                lifecycle=replace(
                    adapters.lifecycle,
                    stop=stop,
                    start=start,
                ),
                probe=replace(
                    adapters.probe,
                    prove_stopped=prove_stopped,
                ),
            )

            result = rehearse_managed_runtime_activation(adapters=hostile)

            self.assertEqual(result, FAILED_RESULT)
            self.assertNotIn("probe.health", world.events)
            self.assertNotIn("probe.analyze", world.events)

    def test_final_stop_cannot_replay_initial_stopped_evidence(self) -> None:
        with SyntheticActivationWorld() as world:
            adapters = world.adapters()
            original_stop = adapters.lifecycle.stop
            original_probe = adapters.probe.prove_stopped
            cached_stop: object | None = None
            cached_probe: object | None = None

            def stop(request: object) -> object:
                nonlocal cached_stop
                if cached_stop is None:
                    cached_stop = original_stop(request)
                else:
                    world.events.append("lifecycle.stop")
                    return replace(
                        cached_stop,
                        stop_token="old-stop-0",
                    )
                return cached_stop

            def prove_stopped(request: object) -> object:
                nonlocal cached_probe
                if cached_probe is None:
                    cached_probe = original_probe(request)
                else:
                    world.events.append("probe.stopped")
                    return replace(
                        cached_probe,
                        stop_token="old-stop-0",
                    )
                return cached_probe

            hostile = replace(
                adapters,
                lifecycle=replace(adapters.lifecycle, stop=stop),
                probe=replace(
                    adapters.probe,
                    prove_stopped=prove_stopped,
                ),
            )

            result = rehearse_managed_runtime_activation(adapters=hostile)

            self.assertEqual(result, FAILED_RESULT)
            self.assertTrue(world.running)
            self.assertTrue(world.pid_file.exists())

    def test_final_stop_cannot_replay_a_prior_activation(self) -> None:
        captured_stop: object | None = None
        captured_probe: object | None = None
        with SyntheticActivationWorld() as first_world:
            first = first_world.adapters()
            first_stop = first.lifecycle.stop
            first_probe = first.probe.prove_stopped
            stop_calls = 0
            probe_calls = 0

            def capture_stop(request: object) -> object:
                nonlocal captured_stop, stop_calls
                stop_calls += 1
                value = first_stop(request)
                if stop_calls == 2:
                    captured_stop = value
                return value

            def capture_probe(request: object) -> object:
                nonlocal captured_probe, probe_calls
                probe_calls += 1
                value = first_probe(request)
                if probe_calls == 2:
                    captured_probe = value
                return value

            recording = replace(
                first,
                lifecycle=replace(first.lifecycle, stop=capture_stop),
                probe=replace(
                    first.probe,
                    prove_stopped=capture_probe,
                ),
            )
            self.assertEqual(
                rehearse_managed_runtime_activation(adapters=recording),
                COMPLETED_RESULT,
            )

        self.assertIsNotNone(captured_stop)
        self.assertIsNotNone(captured_probe)
        with SyntheticActivationWorld() as second_world:
            second = second_world.adapters()
            second_stop = second.lifecycle.stop
            second_probe = second.probe.prove_stopped
            stop_calls = 0
            probe_calls = 0

            def replay_stop(request: object) -> object:
                nonlocal stop_calls
                stop_calls += 1
                if stop_calls == 1:
                    return second_stop(request)
                second_world.events.append("lifecycle.stop")
                return captured_stop

            def replay_probe(request: object) -> object:
                nonlocal probe_calls
                probe_calls += 1
                if probe_calls == 1:
                    return second_probe(request)
                second_world.events.append("probe.stopped")
                return captured_probe

            replaying = replace(
                second,
                lifecycle=replace(second.lifecycle, stop=replay_stop),
                probe=replace(
                    second.probe,
                    prove_stopped=replay_probe,
                ),
            )

            result = rehearse_managed_runtime_activation(
                adapters=replaying
            )

            self.assertEqual(result, FAILED_RESULT)
            self.assertTrue(second_world.running)
            self.assertTrue(second_world.pid_file.exists())

    def test_unknown_reobservations_cannot_spoof_equality(self) -> None:
        for boundary in (
            "layout",
            "runtime",
            "runtime_field",
            "database_source",
            "artifact_source",
            "artifact_probe",
        ):
            with self.subTest(boundary=boundary):
                with SyntheticActivationWorld() as world:
                    adapters = _spoofed_reobservation(
                        world,
                        world.adapters(),
                        boundary,
                    )

                    result = rehearse_managed_runtime_activation(
                        adapters=adapters
                    )

                    self.assertEqual(result, FAILED_RESULT)

class _EqualitySpoof:
    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return False


def _spoofed_reobservation(
    world: SyntheticActivationWorld,
    adapters: object,
    boundary: str,
) -> object:
    spoof = _EqualitySpoof()
    if boundary == "runtime":
        return replace(
            adapters,
            runtime=replace(adapters.runtime, observe=lambda: spoof),
        )
    if boundary == "runtime_field":
        activate = adapters.runtime.activate
        observe_runtime = adapters.runtime.observe
        return replace(
            adapters,
            runtime=replace(
                adapters.runtime,
                activate=lambda request: replace(
                    activate(request),
                    python_version=spoof,
                ),
                observe=lambda: replace(
                    observe_runtime(),
                    python_version=spoof,
                ),
            ),
        )
    if boundary == "artifact_probe":
        return replace(
            adapters,
            probe=replace(
                adapters.probe,
                observe_artifact_destination=lambda: spoof,
            ),
        )
    if boundary == "layout":
        target = adapters.filesystem.observe_layout
        threshold = 3
        adapter_name = "filesystem"
        callback_name = "observe_layout"
    elif boundary == "database_source":
        target = adapters.database.observe_source
        threshold = 3
        adapter_name = "database"
        callback_name = "observe_source"
    else:
        target = adapters.filesystem.observe_artifact_source
        threshold = 2
        adapter_name = "filesystem"
        callback_name = "observe_artifact_source"
    calls = 0

    def observe() -> object:
        nonlocal calls
        calls += 1
        value = target()
        return spoof if calls == threshold else value

    selected = getattr(adapters, adapter_name)
    return replace(
        adapters,
        **{
            adapter_name: replace(
                selected,
                **{callback_name: observe},
            )
        },
    )


if __name__ == "__main__":
    unittest.main()
