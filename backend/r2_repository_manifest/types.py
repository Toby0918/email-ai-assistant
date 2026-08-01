"""Closed categories, boundaries, gaps, and selector for Issue #75."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ManifestCategory(str, Enum):
    GIT = "git"
    TRACKED = "tracked"
    APPROVED_UNTRACKED = "approved_untracked"


class ManifestBoundary(str, Enum):
    WORKTREE_PRESERVATION = "worktree_preservation"
    LEGACY_ANCHOR_RENAME = "legacy_anchor_rename"
    CONTAINER_PUBLICATION = "container_publication"
    MAIN_SKELETON = "main_skeleton"
    MANIFEST_RELOCATION = "manifest_relocation"
    ACL_CONFORMANCE = "acl_conformance"
    WORKTREE_RECONSTRUCTION = "worktree_reconstruction"
    FINAL_VERIFICATION = "final_verification"


class ManifestCrashGap(str, Enum):
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_SCAN = "after_scan"
    AFTER_OBSERVATION = "after_observation"
    AFTER_COMMIT = "after_commit"


@dataclass(frozen=True, slots=True, init=False)
class ManifestSelectorV1:
    boundary: ManifestBoundary | None
    item_index: int
    gap: ManifestCrashGap | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ManifestSelectorV1 requires a factory")

    @classmethod
    def none(cls) -> ManifestSelectorV1:
        return _selector(None, 0, None)

    @classmethod
    def create(
        cls,
        *,
        boundary: ManifestBoundary,
        item_index: int,
        gap: ManifestCrashGap,
    ) -> ManifestSelectorV1:
        if (
            type(boundary) is not ManifestBoundary
            or type(item_index) is not int
            or not 1 <= item_index <= 100
            or type(gap) is not ManifestCrashGap
        ):
            raise ValueError("manifest_selector_invalid")
        return _selector(boundary, item_index, gap)

    def matches(self, boundary, item_index, gap) -> bool:
        return (
            self.boundary is boundary
            and self.item_index == item_index
            and self.gap is gap
        )


def _selector(boundary, item_index, gap) -> ManifestSelectorV1:
    value = object.__new__(ManifestSelectorV1)
    object.__setattr__(value, "boundary", boundary)
    object.__setattr__(value, "item_index", item_index)
    object.__setattr__(value, "gap", gap)
    return value
