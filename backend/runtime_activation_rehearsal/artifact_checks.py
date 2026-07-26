"""Pure reviewed browser-extension publication validation."""

from __future__ import annotations

import re

from .adapters import (
    FilesystemAdapter,
    ManagedLayoutEvidence,
    ProbeAdapter,
)
from .artifact_evidence import (
    ArtifactDestinationEvidence,
    ArtifactPublicationEvidence,
    ArtifactSourceEvidence,
    ReviewedArtifactEvidence,
)
from .filesystem_checks import resource_identity
from .policy import ManagedResourceRole

_SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)


def rehearse_artifact_publication(
    *,
    filesystem: FilesystemAdapter,
    probe: ProbeAdapter,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Publish only the exact independently reviewed synthetic artifact."""
    source: ArtifactSourceEvidence | None = None
    source_reobserved = False
    try:
        candidate = filesystem.observe_artifact_source()
        if not valid_source(candidate):
            return False
        source = candidate
        review = probe.reviewed_artifact()
        if not valid_review(review, source):
            return False
        publication = filesystem.publish_artifact(review)
        if not valid_publication(publication, source, review, layout):
            return False
        destination = filesystem.observe_artifact_destination()
        independent = probe.observe_artifact_destination()
        if not valid_destination(
            destination,
            independent,
            source,
            publication,
            layout,
        ):
            return False
        source_after = filesystem.observe_artifact_source()
        source_reobserved = True
        return valid_source(source_after) and source_after == source
    except Exception:
        return False
    finally:
        if source is not None and not source_reobserved:
            _best_effort_source_reobservation(filesystem, source)


def valid_source(value: object) -> bool:
    """Validate a canonical synthetic artifact without content access."""
    return (
        type(value) is ArtifactSourceEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.present is True
        and _identity(value.identity)
        and _identity(value.parent_identity)
        and value.identity != value.parent_identity
        and type(value.size_bytes) is int
        and value.size_bytes > 0
        and _digest(value.sha256)
        and value.canonical is True
        and value.has_reparse_component is False
    )


def valid_review(
    value: object,
    source: ArtifactSourceEvidence,
) -> bool:
    """Bind the approved digest to the exact observed source."""
    return (
        type(value) is ReviewedArtifactEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.approved is True
        and type(value.artifact_kind) is str
        and value.artifact_kind == "browser_extension"
        and _identity(value.source_identity)
        and value.source_identity == source.identity
        and type(value.size_bytes) is int
        and value.size_bytes > 0
        and value.size_bytes == source.size_bytes
        and _digest(value.sha256)
        and value.sha256 == source.sha256
    )


def valid_publication(
    value: object,
    source: ArtifactSourceEvidence,
    review: ReviewedArtifactEvidence,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Require a create-only copy into the approved artifact zone."""
    return (
        type(value) is ArtifactPublicationEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.created is True
        and value.create_only is True
        and value.target_was_absent is True
        and _identity(value.source_identity)
        and value.source_identity == source.identity
        and _identity(value.destination_identity)
        and value.destination_identity != source.identity
        and _digest(value.source_sha256)
        and value.source_sha256 == review.sha256
        and _digest(value.destination_sha256)
        and value.destination_sha256 == review.sha256
        and _identity(value.destination_parent_identity)
        and value.destination_parent_identity
        == resource_identity(
            layout,
            ManagedResourceRole.BROWSER_EXTENSION,
        )
        and value.source_preserved is True
        and value.parent_has_reparse_component is False
    )


def valid_destination(
    value: object,
    independent: object,
    source: ArtifactSourceEvidence,
    publication: ArtifactPublicationEvidence,
    layout: ManagedLayoutEvidence,
) -> bool:
    """Cross-check destination identity, parent, size and digest."""
    return (
        _valid_destination_value(value, source, publication, layout)
        and _valid_destination_value(
            independent,
            source,
            publication,
            layout,
        )
        and independent == value
    )


def _valid_destination_value(
    value: object,
    source: ArtifactSourceEvidence,
    publication: ArtifactPublicationEvidence,
    layout: ManagedLayoutEvidence,
) -> bool:
    return (
        type(value) is ArtifactDestinationEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.present is True
        and _identity(value.identity)
        and value.identity == publication.destination_identity
        and value.identity != source.identity
        and _identity(value.parent_identity)
        and value.parent_identity
        == resource_identity(
            layout,
            ManagedResourceRole.BROWSER_EXTENSION,
        )
        and type(value.size_bytes) is int
        and value.size_bytes > 0
        and value.size_bytes == source.size_bytes
        and _digest(value.sha256)
        and value.sha256 == source.sha256
        and value.canonical is True
        and value.has_reparse_component is False
    )


def _best_effort_source_reobservation(
    filesystem: FilesystemAdapter,
    source: ArtifactSourceEvidence,
) -> None:
    try:
        observed = filesystem.observe_artifact_source()
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


def _digest(value: object) -> bool:
    return (
        type(value) is str
        and _SHA256.fullmatch(value) is not None
    )
