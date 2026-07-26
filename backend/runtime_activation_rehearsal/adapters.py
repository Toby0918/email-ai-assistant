"""Injected adapter values for the synthetic activation rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .artifact_evidence import (
    ArtifactDestinationEvidence,
    ArtifactPublicationEvidence,
    ArtifactSourceEvidence,
    ReviewedArtifactEvidence,
)
from .policy import ManagedResourceRole, ManagedZone
from .runtime_evidence import (
    RuntimeBuildEvidence,
    RuntimeBuildRequest,
    RuntimeProbeEvidence,
)
from .service_evidence import (
    AnalysisProbeEvidence,
    AnalysisProbeRequest,
    HealthProbeEvidence,
    HealthProbeRequest,
    ServiceStartEvidence,
    ServiceStartRequest,
)


@dataclass(frozen=True, slots=True, repr=False)
class ZoneEvidence:
    """One content-free synthetic Managed zone observation."""

    role: ManagedZone
    identity: str
    direct_child: bool
    canonical: bool
    has_reparse_component: bool


@dataclass(frozen=True, slots=True, repr=False)
class ManagedResourceEvidence:
    """One ordinary resource bound to an approved Managed zone."""

    role: ManagedResourceRole
    identity: str
    parent_identity: str
    direct_child: bool
    canonical: bool
    has_reparse_component: bool


@dataclass(frozen=True, slots=True, repr=False)
class ManagedLayoutEvidence:
    """A complete synthetic Managed layout observation."""

    schema_version: int
    synthetic: bool
    scope_identity: str
    container_identity: str
    zones: tuple[ZoneEvidence, ...]
    resources: tuple[ManagedResourceEvidence, ...]
    config_keys: tuple[str, ...]
    config_values_observed: bool
    signing_material_observed: bool


@dataclass(frozen=True, slots=True, repr=False)
class LifecycleStopRequest:
    """Code-fixed lifecycle phase and activation binding."""

    schema_version: int
    phase: str
    activation_token: str


@dataclass(frozen=True, slots=True, repr=False)
class LifecycleStopEvidence:
    """Lifecycle-manager observation after a synthetic stop request."""

    schema_version: int
    service_identity: str
    stop_token: str
    phase: str
    activation_token: str
    stopped: bool
    process_present: bool
    health_reachable: bool
    pid_present: bool


@dataclass(frozen=True, slots=True, repr=False)
class StoppedProbeEvidence:
    """Independent proof that the same synthetic service is stopped."""

    schema_version: int
    service_identity: str
    stop_token: str
    phase: str
    activation_token: str
    stopped: bool
    process_present: bool
    health_reachable: bool
    pid_present: bool


@dataclass(frozen=True, slots=True, repr=False)
class StoppedServiceGate:
    """Opaque capability required by the create-only database publisher."""

    service_identity: str
    stop_token: str
    phase: str
    activation_token: str


@dataclass(frozen=True, slots=True, repr=False)
class SqliteSnapshot:
    """Content-free identity and integrity evidence for one SQLite file."""

    schema_version: int
    present: bool
    identity: str
    parent_identity: str
    size_bytes: int
    sha256: str
    canonical: bool
    has_reparse_component: bool
    sidecars: tuple[str, ...]
    integrity_ok: bool
    schema_complete: bool
    aggregate_count: int
    query_only: bool


@dataclass(frozen=True, slots=True, repr=False)
class TargetEvidence:
    """Create-only target observation within synthetic LocalData."""

    schema_version: int
    parent_identity: str
    absent: bool
    canonical: bool
    parent_has_reparse_component: bool


@dataclass(frozen=True, slots=True, repr=False)
class DatabasePublicationEvidence:
    """Content-free result from the injected SQLite publisher."""

    schema_version: int
    created: bool
    create_only: bool
    target_was_absent: bool
    service_identity: str
    stop_token: str
    source_identity: str
    destination_identity: str
    source_preserved: bool


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeAdapter:
    """Create and then re-observe one synthetic runtime."""

    activate: Callable[[RuntimeBuildRequest], RuntimeBuildEvidence]
    observe: Callable[[], RuntimeBuildEvidence]


@dataclass(frozen=True, slots=True, repr=False)
class FilesystemAdapter:
    """Observe Managed roles and publish one reviewed artifact."""

    observe_layout: Callable[[], ManagedLayoutEvidence]
    observe_artifact_source: Callable[[], ArtifactSourceEvidence]
    publish_artifact: Callable[
        [ReviewedArtifactEvidence],
        ArtifactPublicationEvidence,
    ]
    observe_artifact_destination: Callable[
        [],
        ArtifactDestinationEvidence,
    ]


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseAdapter:
    """Observe and publish one synthetic normal analysis database."""

    observe_source: Callable[[], SqliteSnapshot]
    observe_destination_target: Callable[[], TargetEvidence]
    publish_create_only: Callable[
        [StoppedServiceGate],
        DatabasePublicationEvidence,
    ]
    observe_destination: Callable[[], SqliteSnapshot]


@dataclass(frozen=True, slots=True, repr=False)
class LifecycleAdapter:
    """Stop and start the synthetic service through its manager."""

    stop: Callable[[LifecycleStopRequest], LifecycleStopEvidence]
    start: Callable[[ServiceStartRequest], ServiceStartEvidence]


@dataclass(frozen=True, slots=True, repr=False)
class ProbeAdapter:
    """Independently probe runtime, lifecycle, artifact and service state."""

    observe_runtime: Callable[[], RuntimeProbeEvidence]
    prove_stopped: Callable[[LifecycleStopRequest], StoppedProbeEvidence]
    reviewed_artifact: Callable[[], ReviewedArtifactEvidence]
    observe_artifact_destination: Callable[
        [],
        ArtifactDestinationEvidence,
    ]
    health: Callable[[HealthProbeRequest], HealthProbeEvidence]
    analyze: Callable[[AnalysisProbeRequest], AnalysisProbeEvidence]


@dataclass(frozen=True, slots=True, repr=False)
class ManagedActivationAdapters:
    """The exact five target-bound rehearsal capabilities."""

    runtime: RuntimeAdapter
    filesystem: FilesystemAdapter
    database: DatabaseAdapter
    lifecycle: LifecycleAdapter
    probe: ProbeAdapter


def has_exact_adapter_bundle(value: object) -> bool:
    """Reject custom/default capability containers before field access."""
    if type(value) is not ManagedActivationAdapters:
        return False
    return all(
        (
            type(value.runtime) is RuntimeAdapter,
            type(value.filesystem) is FilesystemAdapter,
            type(value.database) is DatabaseAdapter,
            type(value.lifecycle) is LifecycleAdapter,
            type(value.probe) is ProbeAdapter,
            callable(value.runtime.activate),
            callable(value.runtime.observe),
            callable(value.filesystem.observe_layout),
            callable(value.filesystem.observe_artifact_source),
            callable(value.filesystem.publish_artifact),
            callable(value.filesystem.observe_artifact_destination),
            callable(value.database.observe_source),
            callable(value.database.observe_destination_target),
            callable(value.database.publish_create_only),
            callable(value.database.observe_destination),
            callable(value.lifecycle.stop),
            callable(value.lifecycle.start),
            callable(value.probe.observe_runtime),
            callable(value.probe.prove_stopped),
            callable(value.probe.reviewed_artifact),
            callable(value.probe.observe_artifact_destination),
            callable(value.probe.health),
            callable(value.probe.analyze),
        )
    )
