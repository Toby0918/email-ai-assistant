"""Fail-closed external path policy for read-only knowledge snapshots."""

from __future__ import annotations

import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.project_layout import ProtectedLocationPolicy

from .errors import PrivateKnowledgeError


@dataclass(frozen=True, slots=True)
class _AnchorIdentity:
    path: Path
    device: int
    inode: int
    mode: int


def validate_snapshot_path(
    value: Path,
    *,
    project_root: Path,
    forbidden_roots: tuple[Path, ...] = (),
) -> Path:
    path = Path(value)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or path.suffix != ".pksnap"
    ):
        raise PrivateKnowledgeError("snapshot_path_invalid")
    try:
        anchor_before = _existing_anchor_identity(path)
        before = _path_identity(path)
        _test_path_hook("after_anchor_identity", path)
        _reject_reparse_components(path)
        resolved = path.resolve(strict=False)
        _reject_reparse_components(resolved)
        roots = tuple(Path(root).resolve(strict=False) for root in forbidden_roots)
        temporary = Path(tempfile.gettempdir()).resolve(strict=False)
        policy = ProtectedLocationPolicy.for_repository(Path(project_root))
        after = _path_identity(path)
        anchor_after = _existing_anchor_identity(path)
    except Exception:
        raise PrivateKnowledgeError("snapshot_path_invalid") from None
    if (
        before != after
        or anchor_before != anchor_after
        or resolved != path
    ):
        raise PrivateKnowledgeError("snapshot_path_invalid")
    if (
        policy.contains(original_path=path, resolved_path=resolved)
        or _inside_roots(path, resolved, roots)
        or _inside_roots(path, resolved, (temporary,))
        or _contains_onedrive(path, resolved)
        or _inside_raw_vault(path)
        or _inside_raw_vault(resolved)
        or _inside_private_store(path)
        or _inside_private_store(resolved)
    ):
        raise PrivateKnowledgeError("snapshot_path_invalid")
    if before is not None and not stat.S_ISREG(before[2]):
        raise PrivateKnowledgeError("snapshot_path_invalid")
    return resolved


def _existing_anchor_identity(path: Path) -> _AnchorIdentity:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for candidate in (path, *path.parents):
        try:
            metadata = candidate.lstat()
        except FileNotFoundError:
            continue
        mode = getattr(metadata, "st_mode", None)
        device = getattr(metadata, "st_dev", None)
        inode = getattr(metadata, "st_ino", None)
        if (
            type(mode) is not int
            or type(device) is not int
            or type(inode) is not int
            or stat.S_ISLNK(mode)
            or getattr(metadata, "st_file_attributes", 0) & reparse
        ):
            raise OSError
        expected = stat.S_ISREG(mode) if candidate == path else stat.S_ISDIR(mode)
        if not expected:
            raise OSError
        return _AnchorIdentity(candidate, device, inode, mode)
    raise OSError


def _path_identity(path: Path) -> tuple[int, int, int] | None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        raise PrivateKnowledgeError("snapshot_path_invalid") from None
    device = getattr(metadata, "st_dev", None)
    inode = getattr(metadata, "st_ino", None)
    mode = getattr(metadata, "st_mode", None)
    if type(device) is not int or type(inode) is not int or type(mode) is not int:
        raise PrivateKnowledgeError("snapshot_path_invalid")
    return device, inode, mode


def _inside_roots(
    original: Path,
    resolved: Path,
    roots: tuple[Path, ...],
) -> bool:
    return any(
        candidate == root or root in candidate.parents
        for root in roots
        for candidate in (original, resolved)
    )


def _contains_onedrive(original: Path, resolved: Path) -> bool:
    return any(
        part.casefold().startswith("onedrive")
        for path in (original, resolved)
        for part in path.parts
    )


def _test_path_hook(_stage: str, _path: Path) -> None:
    """No-op seam; tests may mutate paths and identity checks still run."""
    return None


def _inside_raw_vault(path: Path) -> bool:
    for parent in path.parents:
        if (_marker_exists(parent / "vault-index.sqlite3")
                or _marker_exists(parent / "keys" / "recovery-state.json")):
            return True
    return False


def _inside_private_store(path: Path) -> bool:
    markers = {"candidate-key.pkenv", "authority-keys.pkenv"}
    return any(
        any(_marker_exists(parent / marker) for marker in markers)
        for parent in path.parents
    )


def _reject_reparse_components(path: Path) -> None:
    for component in reversed((path, *path.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise PrivateKnowledgeError("snapshot_path_invalid") from None
        attributes = getattr(metadata, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or attributes & reparse:
            raise PrivateKnowledgeError("snapshot_path_invalid")


def _marker_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateKnowledgeError("snapshot_path_invalid") from None
    return True
