"""Closed state-machine vocabulary for one representative main tracer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MainPublicationBoundary(str, Enum):
    LEGACY_ANCHOR_RENAME = "legacy_anchor_rename"
    MAIN_CREATE = "main_create"
    PROJECTION_BUILD = "projection_build"
    DIRECTORY_RELOCATION = "directory_relocation"
    FILE_RELOCATION = "file_relocation"
    REPOSITORY_RELOCATION = "repository_relocation"
    PRESERVED_DACL_SCAN = "preserved_dacl_scan"
    ACL_WHOLE_TREE_CONFORMANCE = "acl_whole_tree_conformance"
    MAIN_PUBLISHED = "main_published"


class MainPublicationCrashGap(str, Enum):
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_SCAN = "after_scan"
    AFTER_OBSERVATION = "after_observation"
    AFTER_COMMIT = "after_commit"


class MainPublicationRestartOutcome(str, Enum):
    SAFE_ABORT = "SAFE_ABORT"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False)
class MainPublicationSelectorV1:
    boundary: MainPublicationBoundary | None
    gap: MainPublicationCrashGap | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("MainPublicationSelectorV1 requires a factory")

    @classmethod
    def none(cls) -> MainPublicationSelectorV1:
        return _selector(None, None)

    @classmethod
    def create(
        cls,
        *,
        boundary: MainPublicationBoundary,
        gap: MainPublicationCrashGap,
    ) -> MainPublicationSelectorV1:
        if (
            type(boundary) is not MainPublicationBoundary
            or type(gap) is not MainPublicationCrashGap
        ):
            raise ValueError("main_publication_selector_invalid")
        return _selector(boundary, gap)

    def matches(self, boundary: object, gap: object) -> bool:
        return self.boundary is boundary and self.gap is gap


def _selector(boundary, gap) -> MainPublicationSelectorV1:
    value = object.__new__(MainPublicationSelectorV1)
    object.__setattr__(value, "boundary", boundary)
    object.__setattr__(value, "gap", gap)
    return value
