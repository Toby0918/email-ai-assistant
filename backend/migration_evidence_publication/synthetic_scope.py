"""Marker-bound synthetic filesystem scope for Issue #54 tests."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from .canonical import fingerprint, object_identity_fingerprint
from .contracts_bridge import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)


_SCOPE_ERROR = "MIGRATION_EVIDENCE_SELECTION_REJECTED"
_MARKER_NAME = ".issue-54-migration-evidence-synthetic-sandbox"
_MARKER_BYTES = b"MIGRATION_EVIDENCE_SYNTHETIC_SANDBOX_V1\n"
_TARGET_PARENT_ANCHOR_NAME = ".issue-54-target-parent-anchor"


def synthetic_root(
    temporary_directory: tempfile.TemporaryDirectory,
) -> tuple[Path, str]:
    if type(temporary_directory) is not tempfile.TemporaryDirectory:
        raise ValueError(_SCOPE_ERROR)
    root = Path(temporary_directory.name).resolve(strict=True)
    return root, marker_fingerprint(root)


def require_test_authorization(
    value: object,
    *,
    profile: CutoverProfileV1,
    operation_fingerprint: str,
    phase: str,
    observed_at_epoch: int,
) -> None:
    if (
        type(value) is not TestSandboxAuthorizationV1
        or value.profile_fingerprint != profile.profile_fingerprint
        or value.operation_fingerprint != operation_fingerprint
        or value.phase != phase
        or type(observed_at_epoch) is not int
        or not 0 <= observed_at_epoch < value.expires_at_epoch
    ):
        raise ValueError(_SCOPE_ERROR)


def revalidate_synthetic_scope(
    *,
    temporary_directory: tempfile.TemporaryDirectory,
    sandbox_root: Path,
    marker: str,
    repository_root: Path,
    worktrees: tuple[Path, ...],
    target: Path,
    target_parent_anchor: str,
) -> None:
    root, current_marker = synthetic_root(temporary_directory)
    if (
        root != sandbox_root
        or current_marker != marker
        or inside_directory(root, repository_root) != repository_root
        or tuple(inside_directory(root, path) for path in worktrees)
        != worktrees
        or inside_absent_target(root, target) != target
        or target_parent_anchor_fingerprint(root, target.parent)
        != target_parent_anchor
    ):
        raise ValueError(_SCOPE_ERROR)


def create_target_parent_anchor(root: Path, parent: Path) -> str:
    """Create one synthetic hard-link anchor against inode reuse."""

    checked_parent = inside_directory(root, parent)
    marker = root / _MARKER_NAME
    anchor = checked_parent / _TARGET_PARENT_ANCHOR_NAME
    try:
        os.link(marker, anchor, follow_symlinks=False)
    except FileExistsError:
        pass
    except Exception:
        raise ValueError(_SCOPE_ERROR) from None
    return target_parent_anchor_fingerprint(root, checked_parent)


def target_parent_anchor_fingerprint(
    root: Path,
    parent: Path,
) -> str:
    marker = root / _MARKER_NAME
    anchor = parent / _TARGET_PARENT_ANCHOR_NAME
    try:
        marker_metadata = os.lstat(marker)
        anchor_metadata = os.lstat(anchor)
        reparse = getattr(
            stat,
            "FILE_ATTRIBUTE_REPARSE_POINT",
            0x400,
        )
        if (
            not stat.S_ISREG(marker_metadata.st_mode)
            or not stat.S_ISREG(anchor_metadata.st_mode)
            or stat.S_ISLNK(marker_metadata.st_mode)
            or stat.S_ISLNK(anchor_metadata.st_mode)
            or getattr(marker_metadata, "st_file_attributes", 0)
            & reparse
            or getattr(anchor_metadata, "st_file_attributes", 0)
            & reparse
            or marker_metadata.st_nlink != 2
            or anchor_metadata.st_nlink != 2
            or _node_identity(marker_metadata)
            != _node_identity(anchor_metadata)
            or anchor.read_bytes() != _MARKER_BYTES
        ):
            raise ValueError(_SCOPE_ERROR)
    except Exception:
        raise ValueError(_SCOPE_ERROR) from None
    return fingerprint(
        "migration-evidence-target-parent-anchor-v1",
        {
            "parent_identity": object_identity_fingerprint(parent),
            "anchor_identity": object_identity_fingerprint(anchor),
        },
    )


def marker_fingerprint(root: Path) -> str:
    marker = root / _MARKER_NAME
    metadata = os.lstat(marker)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & reparse
        or marker.read_bytes() != _MARKER_BYTES
    ):
        raise ValueError(_SCOPE_ERROR)
    return fingerprint(
        "migration-evidence-synthetic-marker-v1",
        {
            "root_identity": object_identity_fingerprint(root),
            "marker_identity": object_identity_fingerprint(marker),
            "marker_sha256": fingerprint(
                "migration-evidence-synthetic-marker-content-v1",
                _MARKER_BYTES.hex(),
            ),
        },
    )


def inside_directory(root: Path, path: Path) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError(_SCOPE_ERROR)
    resolved = path.resolve(strict=True)
    if resolved != path.absolute() or root not in resolved.parents:
        raise ValueError(_SCOPE_ERROR)
    metadata = os.lstat(resolved)
    if not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(_SCOPE_ERROR)
    return resolved


def inside_absent_target(root: Path, target: Path) -> Path:
    if not isinstance(target, Path) or not target.is_absolute():
        raise ValueError(_SCOPE_ERROR)
    parent = target.parent.resolve(strict=True)
    if parent != target.parent.absolute() or root not in parent.parents:
        raise ValueError(_SCOPE_ERROR)
    try:
        os.lstat(target)
    except FileNotFoundError:
        return parent / target.name
    raise ValueError(_SCOPE_ERROR)


def _node_identity(metadata: os.stat_result) -> tuple[int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
    )
