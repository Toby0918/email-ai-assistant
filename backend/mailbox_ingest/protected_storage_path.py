"""Read-only Project Container path evidence for mailbox private stores."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from backend.project_layout import ProtectedLocationPolicy, RepositoryPlacement

from .errors import VaultError


RepositoryContext = Path | RepositoryPlacement


class PathComponentProbe(Protocol):
    def inspect(self, path: Path) -> object: ...


@dataclass(frozen=True)
class PathComponentEvidence:
    exists: bool
    is_symlink: bool
    is_junction: bool
    is_reparse_point: bool


@dataclass(frozen=True)
class _PathViews:
    original: Path
    resolved: Path
    identity: tuple[int, int, int]


class LocalPathComponentProbe:
    """Inspect path components without querying host-security state."""

    def inspect(self, path: Path) -> PathComponentEvidence:
        try:
            metadata = path.lstat()
            junction = (
                path.is_junction()
                if hasattr(path, "is_junction")
                else False
            )
        except FileNotFoundError:
            return PathComponentEvidence(False, False, False, False)
        except OSError:
            raise VaultError("invalid_path") from None
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        reparse_mask = int(
            getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        )
        return PathComponentEvidence(
            True,
            stat.S_ISLNK(metadata.st_mode),
            junction,
            bool(attributes & reparse_mask),
        )


def _validated_path(
    path: Path,
    *,
    must_exist: bool,
    component_probe: PathComponentProbe | None = None,
) -> _PathViews:
    if not path.is_absolute() or ".." in path.parts:
        raise VaultError("path_not_absolute")
    try:
        selected_probe = component_probe or LocalPathComponentProbe()
        _reject_reparse_path(path, selected_probe)
        if must_exist and not path.exists():
            raise VaultError("path_missing")
        identity = _path_identity(path)
        resolved = path.resolve(strict=must_exist)
        _reject_reparse_path(resolved, selected_probe)
        if resolved != path or _path_identity(path) != identity:
            raise VaultError("invalid_path")
        return _PathViews(path, resolved, identity)
    except VaultError:
        raise
    except (OSError, RuntimeError):
        raise VaultError("invalid_path") from None


def _protected_policy(
    project_root: RepositoryContext,
) -> ProtectedLocationPolicy:
    try:
        return ProtectedLocationPolicy.for_context(project_root)
    except Exception:
        raise VaultError("invalid_path") from None


def _reject_forbidden_locations(
    vault: _PathViews,
    recovery_parent: _PathViews,
    protected: ProtectedLocationPolicy,
    system_temp: _PathViews,
) -> None:
    if protected.contains(
        original_path=vault.original,
        resolved_path=vault.resolved,
    ) or _inside_views(vault, system_temp):
        raise VaultError("prohibited_vault_location")
    if _has_onedrive_component(vault):
        raise VaultError("prohibited_vault_location")
    if (
        _inside_views(recovery_parent, vault)
        or _inside_views(recovery_parent, system_temp)
        or protected.contains(
            original_path=recovery_parent.original,
            resolved_path=recovery_parent.resolved,
        )
    ):
        raise VaultError("prohibited_recovery_location")
    if _has_onedrive_component(recovery_parent):
        raise VaultError("prohibited_recovery_location")


def _inside_views(path: _PathViews, ancestor: _PathViews) -> bool:
    return any(
        _inside(candidate, root)
        for candidate in (path.original, path.resolved)
        for root in (ancestor.original, ancestor.resolved)
    )


def _has_onedrive_component(path: _PathViews) -> bool:
    return any(
        part.casefold().startswith("onedrive")
        for view in (path.original, path.resolved)
        for part in view.parts
    )


def _reject_reparse_path(path: Path, probe: PathComponentProbe) -> None:
    for component in (*reversed(path.parents), path):
        _reject_reparse_component(probe.inspect(component))


def _reject_reparse_component(evidence: object) -> None:
    fields = (
        getattr(evidence, "exists", None),
        getattr(evidence, "is_symlink", None),
        getattr(evidence, "is_junction", None),
        getattr(evidence, "is_reparse_point", None),
    )
    if any(type(value) is not bool for value in fields):
        raise VaultError("invalid_path")
    exists, *reparse_flags = fields
    if any(reparse_flags) and not exists:
        raise VaultError("invalid_path")
    if exists and any(reparse_flags):
        raise VaultError("reparse_point_forbidden")


def _path_identity(path: Path) -> tuple[int, int, int]:
    metadata = path.lstat()
    device = getattr(metadata, "st_dev", None)
    inode = getattr(metadata, "st_ino", None)
    mode = getattr(metadata, "st_mode", None)
    if type(device) is not int or type(inode) is not int or type(mode) is not int:
        raise VaultError("invalid_path")
    return device, inode, mode


def _inside(path: Path, ancestor: Path) -> bool:
    return path == ancestor or ancestor in path.parents
