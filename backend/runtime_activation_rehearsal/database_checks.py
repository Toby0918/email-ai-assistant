"""Pure create-only SQLite publication validation."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .adapters import (
    DatabaseAdapter,
    DatabasePublicationEvidence,
    ManagedLayoutEvidence,
    SqliteSnapshot,
    StoppedServiceGate,
    TargetEvidence,
)
from .filesystem_checks import zone_identity
from .policy import ManagedZone

_SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseActivationState:
    """Validated source and pre-activation destination snapshots."""

    source: SqliteSnapshot
    destination: SqliteSnapshot
    stopped_gate: StoppedServiceGate


def rehearse_database_publication(
    *,
    adapter: DatabaseAdapter,
    layout: ManagedLayoutEvidence,
    gate: StoppedServiceGate,
) -> DatabaseActivationState | None:
    """Publish one SQLite copy and re-observe its unchanged source."""
    source: SqliteSnapshot | None = None
    source_reobserved = False
    try:
        candidate = adapter.observe_source()
        if not valid_source(candidate):
            return None
        source = candidate
        target = adapter.observe_destination_target()
        if not valid_target(target, layout):
            return None
        publication = adapter.publish_create_only(gate)
        if not valid_publication(publication, source, gate):
            return None
        destination = adapter.observe_destination()
        if not valid_destination(
            destination,
            source,
            publication,
            layout,
        ):
            return None
        source_after = adapter.observe_source()
        source_reobserved = True
        if not valid_source(source_after) or source_after != source:
            return None
        return DatabaseActivationState(
            source=source,
            destination=destination,
            stopped_gate=gate,
        )
    except Exception:
        return None
    finally:
        if source is not None and not source_reobserved:
            _best_effort_source_reobservation(adapter, source)


def valid_source(value: object) -> bool:
    """Validate the stopped, query-only synthetic source database."""
    return _valid_snapshot(value) and (
        value.sidecars == ()
        and value.integrity_ok is True
        and value.schema_complete is True
        and value.query_only is True
    )


def valid_target(
    value: object,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Require an absent canonical target directly under LocalData."""
    return (
        type(value) is TargetEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and _identity(value.parent_identity)
        and value.parent_identity
        == zone_identity(layout, ManagedZone.LOCAL_DATA)
        and value.absent is True
        and value.canonical is True
        and value.parent_has_reparse_component is False
    )


def valid_publication(
    value: object,
    source: SqliteSnapshot,
    gate: StoppedServiceGate,
) -> bool:
    """Require an atomic create-only result bound to the stop token."""
    return (
        type(value) is DatabasePublicationEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.created is True
        and value.create_only is True
        and value.target_was_absent is True
        and _identity(value.service_identity)
        and value.service_identity == gate.service_identity
        and _identity(value.stop_token)
        and value.stop_token == gate.stop_token
        and _identity(value.source_identity)
        and value.source_identity == source.identity
        and _identity(value.destination_identity)
        and value.destination_identity != source.identity
        and value.source_preserved is True
    )


def valid_destination(
    value: object,
    source: SqliteSnapshot,
    publication: DatabasePublicationEvidence,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Match identity, bytes, integrity and aggregate counts."""
    return (
        _valid_snapshot(value)
        and value.identity == publication.destination_identity
        and value.identity != source.identity
        and value.parent_identity
        == zone_identity(layout, ManagedZone.LOCAL_DATA)
        and value.size_bytes == source.size_bytes
        and value.sha256 == source.sha256
        and value.sidecars == source.sidecars == ()
        and value.integrity_ok is source.integrity_ok is True
        and value.schema_complete is source.schema_complete is True
        and value.aggregate_count == source.aggregate_count
        and value.query_only is source.query_only is True
    )


def _valid_snapshot(value: object) -> bool:
    return (
        type(value) is SqliteSnapshot
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.present is True
        and _identity(value.identity)
        and _identity(value.parent_identity)
        and value.identity != value.parent_identity
        and type(value.size_bytes) is int
        and value.size_bytes > 0
        and type(value.sha256) is str
        and _SHA256.fullmatch(value.sha256) is not None
        and value.canonical is True
        and value.has_reparse_component is False
        and type(value.sidecars) is tuple
        and all(type(sidecar) is str for sidecar in value.sidecars)
        and type(value.aggregate_count) is int
        and value.aggregate_count >= 0
    )


def _best_effort_source_reobservation(
    adapter: DatabaseAdapter,
    source: SqliteSnapshot,
) -> None:
    try:
        observed = adapter.observe_source()
        if valid_source(observed):
            observed == source
    except Exception:
        pass


def _identity(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and value.strip() == value
    )
