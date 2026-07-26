"""Content-free browser-extension publication evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class ArtifactSourceEvidence:
    """Synthetic reviewed-artifact source observation."""

    schema_version: int
    present: bool
    identity: str
    parent_identity: str
    size_bytes: int
    sha256: str
    canonical: bool
    has_reparse_component: bool


@dataclass(frozen=True, slots=True, repr=False)
class ReviewedArtifactEvidence:
    """Independent reviewed identity and digest allowlist."""

    schema_version: int
    approved: bool
    artifact_kind: str
    source_identity: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class ArtifactPublicationEvidence:
    """Create-only publication outcome without path or content."""

    schema_version: int
    created: bool
    create_only: bool
    target_was_absent: bool
    source_identity: str
    destination_identity: str
    source_sha256: str
    destination_sha256: str
    destination_parent_identity: str
    source_preserved: bool
    parent_has_reparse_component: bool


@dataclass(frozen=True, slots=True, repr=False)
class ArtifactDestinationEvidence:
    """Independent destination identity and digest observation."""

    schema_version: int
    present: bool
    identity: str
    parent_identity: str
    size_bytes: int
    sha256: str
    canonical: bool
    has_reparse_component: bool
