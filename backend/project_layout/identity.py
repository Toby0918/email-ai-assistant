"""Read-only directory identity evidence for placement validation."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .errors import PlacementError


@dataclass(frozen=True, slots=True)
class DirectoryIdentity:
    canonical_path: Path
    device: int
    inode: int
    has_reparse_component: bool = False


DirectoryInspector = Callable[[Path], object]


def inspect_local_directory(path: Path) -> DirectoryIdentity:
    try:
        source = Path(path)
        if not source.is_absolute():
            raise PlacementError("placement_identity_unavailable")
        has_reparse_component = _has_reparse_component(source)
        canonical = source.resolve(strict=True)
        metadata = canonical.lstat()
        if not stat.S_ISDIR(metadata.st_mode):
            raise PlacementError("placement_identity_unavailable")
        device = getattr(metadata, "st_dev", None)
        inode = getattr(metadata, "st_ino", None)
        if (
            type(device) is not int
            or type(inode) is not int
            or device < 0
            or inode <= 0
        ):
            raise PlacementError("placement_identity_unavailable")
        return DirectoryIdentity(
            canonical,
            device,
            inode,
            has_reparse_component,
        )
    except PlacementError:
        raise
    except Exception:
        raise PlacementError("placement_identity_unavailable") from None


def read_directory_identity(
    path: Path,
    inspector: DirectoryInspector,
) -> DirectoryIdentity:
    try:
        source = Path(path)
        evidence = inspector(source)
        canonical = getattr(evidence, "canonical_path", None)
        device = getattr(evidence, "device", None)
        inode = getattr(evidence, "inode", None)
        has_reparse_component = getattr(
            evidence,
            "has_reparse_component",
            None,
        )
        if (
            not isinstance(canonical, Path)
            or not canonical.is_absolute()
            or type(device) is not int
            or type(inode) is not int
            or type(has_reparse_component) is not bool
            or device < 0
            or inode <= 0
        ):
            raise PlacementError("placement_identity_unavailable")
        if has_reparse_component:
            raise PlacementError("placement_reparse_forbidden")
        if ".." in source.parts or ".." in canonical.parts:
            raise PlacementError("placement_alias_invalid")
        if canonical != source:
            raise PlacementError("placement_alias_invalid")
        return DirectoryIdentity(canonical, device, inode, False)
    except PlacementError:
        raise
    except Exception:
        raise PlacementError("placement_identity_unavailable") from None


def _has_reparse_component(path: Path) -> bool:
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for component in (*reversed(path.parents), path):
        metadata = component.lstat()
        is_junction = (
            component.is_junction()
            if hasattr(component, "is_junction")
            else False
        )
        if (
            stat.S_ISLNK(metadata.st_mode)
            or is_junction
            or int(getattr(metadata, "st_file_attributes", 0)) & reparse_mask
        ):
            return True
    return False
