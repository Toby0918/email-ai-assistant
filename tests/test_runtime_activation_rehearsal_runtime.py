"""Runtime and locked-dependency tests for activation rehearsal."""

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
    FilesystemAdapter,
    LifecycleAdapter,
    ManagedLayoutEvidence,
    ManagedResourceEvidence,
    ProbeAdapter,
    RuntimeAdapter,
    RuntimeBuildEvidence,
    RuntimeProbeEvidence,
    ZoneEvidence,
)
from backend.runtime_activation_rehearsal.policy import (
    CONFIG_KEYS,
    LOCKED_DEPENDENCIES,
    LOCK_SHA256,
    ManagedResourceRole,
    ManagedZone,
    PINNED_PYTHON_VERSION,
    PINNED_SQLITE_VERSION,
)


class RuntimeActivationRehearsalRuntimeTests(unittest.TestCase):
    def test_exact_runtime_build_reaches_stopped_service_gate(self) -> None:
        events: list[str] = []
        adapters = _runtime_bundle(events=events)

        result = rehearse_managed_runtime_activation(adapters=adapters)

        self.assertEqual(result, FAILED_RESULT)
        self.assertEqual(
            events,
            [
                "filesystem.layout",
                "runtime.activate",
                "probe.runtime",
                "runtime.observe",
                "filesystem.layout",
                "lifecycle.stop",
            ],
        )

    def test_runtime_version_mismatch_fails_before_probe_or_stop(self) -> None:
        cases = {
            "python": {"python_version": "3.12.14"},
            "sqlite": {"sqlite_version": "3.50.5"},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _runtime_bundle(
                    events=events,
                    build_changes=changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertEqual(
                    events,
                    ["filesystem.layout", "runtime.activate"],
                )

    def test_dependency_or_legacy_reuse_evidence_fails_closed(self) -> None:
        cases = {
            "dependency": {
                "locked_dependencies": LOCKED_DEPENDENCIES[:-1],
            },
            "lock": {"lock_sha256": "0" * 64},
            "lock_identity_drift": {
                "lock_identity_after": "dependency-lock-racer",
            },
            "lock_hash_drift": {
                "lock_sha256_after": "0" * 64,
            },
            "network": {"network_used": True},
            "legacy_read": {"legacy_observed": True},
            "legacy_move": {"legacy_moved": True},
            "not_rebuilt": {"venv_rebuilt": False},
            "not_create_only": {"create_only": False},
            "reparse": {"has_reparse_component": True},
            "venv_parent": {
                "venv_parent_identity": "zone-local_data",
            },
            "scripts_parent": {
                "scripts_parent_identity": "runtime-1",
            },
            "executable_parent": {
                "executable_parent_identity": "venv-1",
            },
            "boolean_schema": {"schema_version": True},
        }
        for name, changes in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _runtime_bundle(
                    events=events,
                    build_changes=changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertEqual(
                    events,
                    ["filesystem.layout", "runtime.activate"],
                )

    def test_runtime_probe_or_second_observation_drift_fails_closed(
        self,
    ) -> None:
        cases = {
            "probe": (
                {},
                {"runtime_identity": "runtime-racer"},
            ),
            "observation": (
                {"runtime_identity": "runtime-racer"},
                {},
            ),
        }
        for name, (observed_changes, probe_changes) in cases.items():
            with self.subTest(name=name):
                events: list[str] = []
                adapters = _runtime_bundle(
                    events=events,
                    observed_changes=observed_changes,
                    probe_changes=probe_changes,
                )

                result = rehearse_managed_runtime_activation(
                    adapters=adapters
                )

                self.assertEqual(result, FAILED_RESULT)
                self.assertNotIn("lifecycle.stop", events)


def _runtime_bundle(
    *,
    events: list[str],
    build_changes: dict[str, object] | None = None,
    observed_changes: dict[str, object] | None = None,
    probe_changes: dict[str, object] | None = None,
) -> ManagedActivationAdapters:
    layout = _layout()
    build = replace(_runtime_build(), **(build_changes or {}))
    observed = replace(build, **(observed_changes or {}))
    probe = replace(_runtime_probe(), **(probe_changes or {}))

    def observe_layout() -> ManagedLayoutEvidence:
        events.append("filesystem.layout")
        return layout

    def activate(request: object) -> RuntimeBuildEvidence:
        events.append("runtime.activate")
        return build

    def observe_runtime() -> RuntimeBuildEvidence:
        events.append("runtime.observe")
        return observed

    def probe_runtime() -> RuntimeProbeEvidence:
        events.append("probe.runtime")
        return probe

    def stop(*args: object) -> object:
        events.append("lifecycle.stop")
        raise RuntimeError("synthetic stop boundary")

    def never(*args: object) -> object:
        raise AssertionError("later adapter called")

    return ManagedActivationAdapters(
        runtime=RuntimeAdapter(
            activate=activate,
            observe=observe_runtime,
        ),
        filesystem=FilesystemAdapter(
            observe_layout=observe_layout,
            observe_artifact_source=never,
            publish_artifact=never,
            observe_artifact_destination=never,
        ),
        database=DatabaseAdapter(
            observe_source=never,
            observe_destination_target=never,
            publish_create_only=never,
            observe_destination=never,
        ),
        lifecycle=LifecycleAdapter(stop=stop, start=never),
        probe=ProbeAdapter(
            observe_runtime=probe_runtime,
            prove_stopped=never,
            reviewed_artifact=never,
            observe_artifact_destination=never,
            health=never,
            analyze=never,
        ),
    )


def _layout() -> ManagedLayoutEvidence:
    return ManagedLayoutEvidence(
        schema_version=1,
        synthetic=True,
        scope_identity="scope-1",
        container_identity="container-1",
        zones=tuple(
            ZoneEvidence(
                role=role,
                identity=f"zone-{role.value}",
                direct_child=True,
                canonical=True,
                has_reparse_component=False,
            )
            for role in ManagedZone
        ),
        resources=tuple(
            ManagedResourceEvidence(
                role=role,
                identity=f"resource-{role.value}",
                parent_identity=_resource_parent(role),
                direct_child=True,
                canonical=True,
                has_reparse_component=False,
            )
            for role in ManagedResourceRole
        ),
        config_keys=CONFIG_KEYS,
        config_values_observed=False,
        signing_material_observed=False,
    )


def _resource_parent(role: ManagedResourceRole) -> str:
    parents = {
        ManagedResourceRole.ATTACHMENT_TEMP: "zone-runtime_temp",
        ManagedResourceRole.SERVICE_LOG: "zone-logs",
        ManagedResourceRole.PID_STATE: "zone-logs",
        ManagedResourceRole.NON_SECRET_CONFIG: "zone-config",
        ManagedResourceRole.BROWSER_EXTENSION: "zone-artifacts",
    }
    return parents[role]


def _runtime_build() -> RuntimeBuildEvidence:
    return RuntimeBuildEvidence(
        schema_version=1,
        runtime_identity="runtime-1",
        runtime_parent_identity="zone-runtimes",
        venv_identity="venv-1",
        venv_parent_identity="zone-runtimes",
        scripts_identity="scripts-1",
        scripts_parent_identity="venv-1",
        executable_identity="python-1",
        executable_parent_identity="scripts-1",
        python_version=PINNED_PYTHON_VERSION,
        sqlite_version=PINNED_SQLITE_VERSION,
        locked_dependencies=LOCKED_DEPENDENCIES,
        lock_sha256=LOCK_SHA256,
        lock_identity_before="dependency-lock-1",
        lock_identity_after="dependency-lock-1",
        lock_sha256_before=LOCK_SHA256,
        lock_sha256_after=LOCK_SHA256,
        source_identity_before="runtime-source-1",
        source_identity_after="runtime-source-1",
        legacy_venv_identity_before="legacy-venv-1",
        legacy_venv_identity_after="legacy-venv-1",
        runtime_created=True,
        venv_rebuilt=True,
        create_only=True,
        source_preserved=True,
        legacy_preserved=True,
        legacy_observed=False,
        legacy_moved=False,
        network_used=False,
        has_reparse_component=False,
    )


def _runtime_probe() -> RuntimeProbeEvidence:
    return RuntimeProbeEvidence(
        schema_version=1,
        runtime_identity="runtime-1",
        venv_identity="venv-1",
        scripts_identity="scripts-1",
        executable_identity="python-1",
        python_version=PINNED_PYTHON_VERSION,
        sqlite_version=PINNED_SQLITE_VERSION,
        locked_dependencies=LOCKED_DEPENDENCIES,
        lock_sha256=LOCK_SHA256,
        has_reparse_component=False,
    )


if __name__ == "__main__":
    unittest.main()
