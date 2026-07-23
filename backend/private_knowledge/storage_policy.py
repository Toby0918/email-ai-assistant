"""External path policy shared by private authority and staging stores."""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.project_layout import ProtectedLocationPolicy

from .errors import PrivateKnowledgeError


@dataclass(frozen=True, slots=True)
class _PathViews:
    original: Path
    resolved: Path


@dataclass(frozen=True, slots=True)
class _AnchorIdentity:
    path: Path
    device: int
    inode: int
    mode: int


def validate_stage_storage(
    candidate_root: Path,
    vault_root: Path,
    project_root: Path,
) -> None:
    candidate = _external_root(candidate_root)
    vault = _absolute_root(vault_root)
    policy = _protected_policy(project_root)
    forbidden = [Path(tempfile.gettempdir()).resolve()]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        forbidden.append(Path(one_drive).resolve())
    if (
        policy.contains(
            original_path=candidate.original,
            resolved_path=candidate.resolved,
        )
        or _inside_any(candidate, forbidden)
        or _overlaps(candidate.resolved, vault)
        or _contains_onedrive(candidate)
    ):
        raise PrivateKnowledgeError("private_storage_path_invalid")


def validate_private_storage(project_root: Path, *paths: Path) -> None:
    reviewed = tuple(_external_root(path) for path in paths)
    policy = _protected_policy(project_root)
    forbidden = [Path(tempfile.gettempdir()).resolve()]
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        forbidden.append(Path(one_drive).resolve())
    for path in reviewed:
        if (
            policy.contains(
                original_path=path.original,
                resolved_path=path.resolved,
            )
            or _inside_any(path, forbidden)
            or _contains_onedrive(path)
        ):
            raise PrivateKnowledgeError("private_storage_path_invalid")
    resolved = tuple(path.resolved for path in reviewed)
    for index, path in enumerate(resolved):
        if any(_overlaps(path, other) for other in resolved[index + 1 :]):
            raise PrivateKnowledgeError("key_namespace_not_separate")


def _external_root(value: Path) -> _PathViews:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise PrivateKnowledgeError("private_storage_path_invalid")
    try:
        anchor_before = _existing_anchor_identity(path)
        _test_path_hook("after_anchor_identity", path)
        _reject_reparse_components(path)
        if _inside_raw_vault(path):
            raise PrivateKnowledgeError("private_storage_path_invalid")
        resolved = path.resolve(strict=False)
        _reject_reparse_components(resolved)
        if _inside_raw_vault(resolved):
            raise PrivateKnowledgeError("private_storage_path_invalid")
        anchor_after = _existing_anchor_identity(path)
        if resolved != path or anchor_after != anchor_before:
            raise PrivateKnowledgeError("private_storage_path_invalid")
        return _PathViews(path, resolved)
    except (OSError, RuntimeError):
        raise PrivateKnowledgeError("private_storage_path_invalid") from None


def _absolute_root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("private_storage_path_invalid")
    try:
        return path.resolve(strict=False)
    except (OSError, RuntimeError):
        raise PrivateKnowledgeError("private_storage_path_invalid") from None


def _protected_policy(project_root: Path) -> ProtectedLocationPolicy:
    try:
        return ProtectedLocationPolicy.for_repository(Path(project_root))
    except Exception:
        raise PrivateKnowledgeError("private_storage_path_invalid") from None


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
            or not stat.S_ISDIR(mode)
            or stat.S_ISLNK(mode)
            or getattr(metadata, "st_file_attributes", 0) & reparse
        ):
            raise OSError
        return _AnchorIdentity(candidate, device, inode, mode)
    raise OSError


def _inside_any(path: _PathViews, roots: list[Path]) -> bool:
    return any(
        _contains(root, path.original) or _contains(root, path.resolved)
        for root in roots
    )


def _contains_onedrive(path: _PathViews) -> bool:
    return any(
        part.casefold().startswith("onedrive")
        for view in (path.original, path.resolved)
        for part in view.parts
    )


def _contains(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _reject_reparse_components(path: Path) -> None:
    for component in reversed((path, *path.parents)):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            raise PrivateKnowledgeError("private_storage_path_invalid") from None
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0) & reparse):
            raise PrivateKnowledgeError("private_storage_path_invalid")


def _inside_raw_vault(path: Path) -> bool:
    for parent in (path, *path.parents):
        if (_marker_exists(parent / "vault-index.sqlite3")
                or _marker_exists(parent / "keys" / "recovery-state.json")):
            return True
    return False


def _marker_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateKnowledgeError("private_storage_path_invalid") from None
    return True


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _test_path_hook(_stage: str, _path: Path) -> None:
    """No-op seam; tests may mutate paths and identity checks still run."""
    return None
