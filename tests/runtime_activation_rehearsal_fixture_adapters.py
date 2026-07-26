"""Injected adapters operating only on caller-owned synthetic fixtures."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import os
import sqlite3

from backend.runtime_activation_rehearsal import ManagedActivationAdapters
from backend.runtime_activation_rehearsal.adapters import (
    ArtifactDestinationEvidence,
    ArtifactPublicationEvidence,
    ArtifactSourceEvidence,
    DatabaseAdapter,
    DatabasePublicationEvidence,
    FilesystemAdapter,
    LifecycleAdapter,
    LifecycleStopRequest,
    LifecycleStopEvidence,
    ManagedLayoutEvidence,
    ManagedResourceEvidence,
    ProbeAdapter,
    ReviewedArtifactEvidence,
    RuntimeAdapter,
    RuntimeBuildEvidence,
    RuntimeBuildRequest,
    RuntimeProbeEvidence,
    SqliteSnapshot,
    StoppedProbeEvidence,
    StoppedServiceGate,
    TargetEvidence,
    ZoneEvidence,
)
from backend.runtime_activation_rehearsal.policy import (
    CONFIG_KEYS,
    ManagedResourceRole,
    ManagedZone,
)
from backend.runtime_activation_rehearsal.service_evidence import (
    AnalysisProbeEvidence,
    AnalysisProbeRequest,
    HealthProbeEvidence,
    HealthProbeRequest,
    ServiceStartEvidence,
    ServiceStartRequest,
)
from tests.runtime_activation_rehearsal_fixtures import (
    SyntheticActivationWorld,
)
from tests.test_runtime_activation_rehearsal_runtime import (
    _runtime_build,
    _runtime_probe,
)
from tests.test_runtime_activation_rehearsal_service import (
    _analysis,
    _health,
    _service_start,
)


def build_synthetic_adapters(
    world: SyntheticActivationWorld,
) -> ManagedActivationAdapters:
    """Compose five exact adapters without any real-host default."""
    runtime = _RuntimeFixtureAdapter(world)
    return ManagedActivationAdapters(
        runtime=RuntimeAdapter(
            activate=runtime.activate,
            observe=runtime.observe,
        ),
        filesystem=_filesystem_adapter(world),
        database=_database_adapter(world),
        lifecycle=_lifecycle_adapter(world),
        probe=_probe_adapter(world, runtime),
    )


class _RuntimeFixtureAdapter:
    def __init__(self, world: SyntheticActivationWorld) -> None:
        self.world = world
        self.build: RuntimeBuildEvidence | None = None

    def activate(
        self,
        request: RuntimeBuildRequest,
    ) -> RuntimeBuildEvidence:
        self.world.events.append("runtime.activate")
        if self.world.failure == "dependency":
            return replace(_runtime_build(), lock_sha256="0" * 64)
        self.world.runtime_target.mkdir()
        runtime_executable = self.world.runtime_target / "python.exe"
        runtime_executable.write_bytes(
            self.world.read_bytes(self.world.runtime_source)
        )
        self.world.venv_target.mkdir()
        self.world.scripts_target.mkdir()
        self.world.venv_executable.write_bytes(
            self.world.read_bytes(self.world.runtime_source)
        )
        (self.world.venv_target / "locked-dependencies.txt").write_text(
            "\n".join(request.locked_dependencies) + "\n",
            encoding="utf-8",
        )
        legacy_identity = self.world.identity(self.world.legacy_venv)
        source_identity = self.world.identity(self.world.runtime_source)
        lock_identity = self.world.identity(self.world.dependency_lock)
        lock_sha256 = _sha256(
            self.world,
            self.world.dependency_lock,
        )
        self.build = replace(
            _runtime_build(),
            runtime_identity=self.world.identity(self.world.runtime_target),
            runtime_parent_identity=self.world.identity(
                self.world.zones["runtimes"]
            ),
            venv_identity=self.world.identity(self.world.venv_target),
            venv_parent_identity=self.world.identity(
                self.world.zones["runtimes"]
            ),
            scripts_identity=self.world.identity(
                self.world.scripts_target
            ),
            scripts_parent_identity=self.world.identity(
                self.world.venv_target
            ),
            executable_identity=self.world.identity(
                self.world.venv_executable
            ),
            executable_parent_identity=self.world.identity(
                self.world.scripts_target
            ),
            lock_identity_before=lock_identity,
            lock_identity_after=lock_identity,
            lock_sha256_before=lock_sha256,
            lock_sha256_after=lock_sha256,
            source_identity_before=source_identity,
            source_identity_after=source_identity,
            legacy_venv_identity_before=legacy_identity,
            legacy_venv_identity_after=legacy_identity,
        )
        return self.build

    def observe(self) -> RuntimeBuildEvidence:
        self.world.events.append("runtime.observe")
        if self.build is None:
            raise RuntimeError("runtime not built")
        if self.world.failure == "runtime_race":
            original = self.world.scripts_target / "python.original"
            self.world.venv_executable.rename(original)
            self.world.venv_executable.write_bytes(b"synthetic racer")
        return self._current_build()

    def probe(self) -> RuntimeProbeEvidence:
        self.world.events.append("probe.runtime")
        if self.build is None:
            raise RuntimeError("runtime not built")
        current = self._current_build()
        return replace(
            _runtime_probe(),
            runtime_identity=current.runtime_identity,
            venv_identity=current.venv_identity,
            scripts_identity=current.scripts_identity,
            executable_identity=current.executable_identity,
        )

    def _current_build(self) -> RuntimeBuildEvidence:
        if self.build is None:
            raise RuntimeError("runtime not built")
        return replace(
            self.build,
            runtime_identity=self.world.identity(
                self.world.runtime_target
            ),
            venv_identity=self.world.identity(self.world.venv_target),
            scripts_identity=self.world.identity(
                self.world.scripts_target
            ),
            executable_identity=self.world.identity(
                self.world.venv_executable
            ),
        )


def _layout_evidence(
    world: SyntheticActivationWorld,
) -> ManagedLayoutEvidence:
    zone_paths = {
        ManagedZone.MAIN: world.main,
        **{
            role: world.zones[role.value]
            for role in ManagedZone
            if role is not ManagedZone.MAIN
        },
    }
    parent_roles = {
        ManagedResourceRole.ATTACHMENT_TEMP: ManagedZone.RUNTIME_TEMP,
        ManagedResourceRole.SERVICE_LOG: ManagedZone.LOGS,
        ManagedResourceRole.PID_STATE: ManagedZone.LOGS,
        ManagedResourceRole.NON_SECRET_CONFIG: ManagedZone.CONFIG,
        ManagedResourceRole.BROWSER_EXTENSION: ManagedZone.ARTIFACTS,
    }
    return ManagedLayoutEvidence(
        schema_version=1,
        synthetic=True,
        scope_identity=world.identity(world.root),
        container_identity=world.identity(world.container),
        zones=tuple(
            ZoneEvidence(
                role=role,
                identity=world.identity(zone_paths[role]),
                direct_child=True,
                canonical=True,
                has_reparse_component=False,
            )
            for role in ManagedZone
        ),
        resources=tuple(
            ManagedResourceEvidence(
                role=role,
                identity=world.path_identity(world.resources[role]),
                parent_identity=world.identity(
                    zone_paths[parent_roles[role]]
                ),
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


def _filesystem_adapter(
    world: SyntheticActivationWorld,
) -> FilesystemAdapter:
    source_calls = 0

    def observe_layout() -> object:
        world.events.append("filesystem.layout")
        value = _layout_evidence(world)
        if world.failure == "reparse":
            zone = next(
                item
                for item in value.zones
                if item.role is ManagedZone.LOCAL_DATA
            )
            changed = replace(zone, has_reparse_component=True)
            return replace(
                value,
                zones=tuple(
                    changed if item.role is zone.role else item
                    for item in value.zones
                ),
            )
        return value

    def observe_source() -> ArtifactSourceEvidence:
        nonlocal source_calls
        source_calls += 1
        world.events.append("filesystem.artifact_source")
        state = world._file_state(world.artifact_source)
        return ArtifactSourceEvidence(
            schema_version=1,
            present=True,
            identity=state.identity,
            parent_identity="synthetic-review-source",
            size_bytes=state.size_bytes,
            sha256=state.sha256,
            canonical=True,
            has_reparse_component=False,
        )

    def publish(
        review: ReviewedArtifactEvidence,
    ) -> ArtifactPublicationEvidence:
        world.events.append("filesystem.artifact_publish")
        _exclusive_copy(
            world,
            world.artifact_source,
            world.artifact_target,
        )
        return ArtifactPublicationEvidence(
            schema_version=1,
            created=True,
            create_only=True,
            target_was_absent=True,
            source_identity=review.source_identity,
            destination_identity=world.identity(world.artifact_target),
            source_sha256=review.sha256,
            destination_sha256=_sha256(world, world.artifact_target),
            destination_parent_identity=world.path_identity(
                world.browser_extension_dir
            ),
            source_preserved=True,
            parent_has_reparse_component=False,
        )

    def destination() -> ArtifactDestinationEvidence:
        world.events.append("filesystem.artifact_destination")
        return _artifact_destination(world)

    return FilesystemAdapter(
        observe_layout=observe_layout,
        observe_artifact_source=observe_source,
        publish_artifact=publish,
        observe_artifact_destination=destination,
    )


def _database_adapter(
    world: SyntheticActivationWorld,
) -> DatabaseAdapter:
    def source() -> SqliteSnapshot:
        world.events.append("database.source")
        return _sqlite_snapshot(
            world,
            world.source_database,
            world.identity(world.source_database.parent),
        )

    def target() -> TargetEvidence:
        world.events.append("database.target")
        return TargetEvidence(
            schema_version=1,
            parent_identity=world.identity(world.zones["local_data"]),
            absent=not world.database_target.exists(),
            canonical=True,
            parent_has_reparse_component=False,
        )

    def publish(
        gate: StoppedServiceGate,
    ) -> DatabasePublicationEvidence:
        if gate.stop_token != world.stop_token:
            raise RuntimeError("stale stopped gate")
        if world.failure == "database_race":
            world.database_target.write_bytes(
                b"synthetic database competitor"
            )
        world.events.append("database.copy")
        source_identity = world.identity(world.source_database)
        _exclusive_copy(
            world,
            world.source_database,
            world.database_target,
        )
        return DatabasePublicationEvidence(
            schema_version=1,
            created=True,
            create_only=True,
            target_was_absent=True,
            service_identity=gate.service_identity,
            stop_token=gate.stop_token,
            source_identity=source_identity,
            destination_identity=world.identity(world.database_target),
            source_preserved=True,
        )

    def destination() -> SqliteSnapshot:
        world.events.append("database.destination")
        value = _sqlite_snapshot(
            world,
            world.database_target,
            world.identity(world.zones["local_data"]),
        )
        if world.failure == "integrity":
            return replace(value, integrity_ok=False)
        return value

    return DatabaseAdapter(
        observe_source=source,
        observe_destination_target=target,
        publish_create_only=publish,
        observe_destination=destination,
    )


def _lifecycle_adapter(
    world: SyntheticActivationWorld,
) -> LifecycleAdapter:
    def stop(request: LifecycleStopRequest) -> LifecycleStopEvidence:
        world.events.append("lifecycle.stop")
        world.running = False
        world.pid_file.unlink(missing_ok=True)
        world.stop_count += 1
        world.stop_token = f"stop-{world.stop_count}"
        return LifecycleStopEvidence(
            schema_version=1,
            service_identity="service-1",
            stop_token=world.stop_token,
            phase=request.phase,
            activation_token=request.activation_token,
            stopped=True,
            process_present=False,
            health_reachable=False,
            pid_present=False,
        )

    def start(request: ServiceStartRequest) -> ServiceStartEvidence:
        world.events.append("lifecycle.start")
        world.running = True
        world.pid_file.write_text("synthetic-active", encoding="ascii")
        return _service_start(request)

    return LifecycleAdapter(stop=stop, start=start)


def _probe_adapter(
    world: SyntheticActivationWorld,
    runtime: _RuntimeFixtureAdapter,
) -> ProbeAdapter:
    def stopped(request: LifecycleStopRequest) -> StoppedProbeEvidence:
        world.events.append("probe.stopped")
        return StoppedProbeEvidence(
            schema_version=1,
            service_identity="service-1",
            stop_token=world.stop_token,
            phase=request.phase,
            activation_token=request.activation_token,
            stopped=not world.running,
            process_present=world.running,
            health_reachable=world.running,
            pid_present=world.pid_file.exists(),
        )

    def review() -> ReviewedArtifactEvidence:
        world.events.append("probe.artifact_review")
        source = world.reviewed_artifact_state
        return ReviewedArtifactEvidence(
            schema_version=1,
            approved=True,
            artifact_kind="browser_extension",
            source_identity=source.identity,
            size_bytes=source.size_bytes,
            sha256=source.sha256,
        )

    def artifact_destination() -> ArtifactDestinationEvidence:
        world.events.append("probe.artifact_destination")
        return _artifact_destination(world)

    def health(request: HealthProbeRequest) -> HealthProbeEvidence:
        world.events.append("probe.health")
        value = _health(request)
        if world.failure == "health":
            return replace(value, healthy=False)
        return value

    def analyze(
        request: AnalysisProbeRequest,
    ) -> AnalysisProbeEvidence:
        world.events.append("probe.analyze")
        connection = sqlite3.connect(world.database_target)
        try:
            cursor = connection.execute(
                "INSERT INTO email_analysis(subject) VALUES (?)",
                ("synthetic activated analysis",),
            )
            connection.commit()
            saved_id = int(cursor.lastrowid)
        finally:
            connection.close()
        return replace(_analysis(request), saved_id=saved_id)

    return ProbeAdapter(
        observe_runtime=runtime.probe,
        prove_stopped=stopped,
        reviewed_artifact=review,
        observe_artifact_destination=artifact_destination,
        health=health,
        analyze=analyze,
    )


def _artifact_destination(
    world: SyntheticActivationWorld,
) -> ArtifactDestinationEvidence:
    state = world._file_state(world.artifact_target)
    return ArtifactDestinationEvidence(
        schema_version=1,
        present=True,
        identity=state.identity,
        parent_identity=world.path_identity(
            world.browser_extension_dir
        ),
        size_bytes=state.size_bytes,
        sha256=state.sha256,
        canonical=True,
        has_reparse_component=False,
    )


def _sqlite_snapshot(
    world: SyntheticActivationWorld,
    path: object,
    parent_identity: str,
) -> SqliteSnapshot:
    state = world._file_state(path, database=True)
    sidecars = tuple(
        suffix
        for suffix in ("-wal", "-shm", "-journal")
        if path.with_name(path.name + suffix).exists()
    )
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
    finally:
        connection.close()
    return SqliteSnapshot(
        schema_version=1,
        present=True,
        identity=state.identity,
        parent_identity=parent_identity,
        size_bytes=state.size_bytes,
        sha256=state.sha256,
        canonical=True,
        has_reparse_component=False,
        sidecars=sidecars,
        integrity_ok=integrity == "ok",
        schema_complete=True,
        aggregate_count=int(state.aggregate_count),
        query_only=True,
    )


def _exclusive_copy(
    world: SyntheticActivationWorld,
    source: object,
    destination: object,
) -> None:
    descriptor = os.open(
        destination,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(world.read_bytes(source))
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _sha256(
    world: SyntheticActivationWorld,
    path: object,
) -> str:
    return hashlib.sha256(world.read_bytes(path)).hexdigest()
