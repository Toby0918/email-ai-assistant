"""External-volume revalidation for commands that do not need recovery media."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .drive_policy import (
    FixedWindowsVolumeProbe,
    LocalPathComponentProbe,
    PathComponentProbe,
    VolumeProbe,
)
from .errors import VaultError
from .models import VaultVolumeEvidence, VolumeInfo


def validate_existing_vault_location(
    vault_root: Path,
    project_root: Path,
    *,
    probe: VolumeProbe | None = None,
    component_probe: PathComponentProbe | None = None,
    system_temp: Path | None = None,
) -> VaultVolumeEvidence:
    """Revalidate an existing vault without requiring recovery media online."""

    vault = _validated_path(Path(vault_root), component_probe)
    project = _validated_path(Path(project_root), component_probe)
    temp = _validated_path(
        Path(tempfile.gettempdir()) if system_temp is None else Path(system_temp),
        component_probe,
    )
    if _inside(vault, project) or _inside(vault, temp):
        raise VaultError("prohibited_vault_location")
    if any(part.casefold().startswith("onedrive") for part in vault.parts):
        raise VaultError("prohibited_vault_location")
    selected_probe = FixedWindowsVolumeProbe() if probe is None else probe
    try:
        information = selected_probe.inspect(vault)
    except VaultError:
        raise
    except Exception:
        raise VaultError("volume_probe_failed") from None
    _validate_vault_evidence(information)
    return VaultVolumeEvidence(information.stable_volume_id)


def _validated_path(
    path: Path,
    component_probe: PathComponentProbe | None,
) -> Path:
    if not path.is_absolute():
        raise VaultError("path_not_absolute")
    selected = LocalPathComponentProbe() if component_probe is None else component_probe
    try:
        for component in (*reversed(path.parents), path):
            evidence = selected.inspect(component)
            fields = (
                getattr(evidence, "exists", None),
                getattr(evidence, "is_symlink", None),
                getattr(evidence, "is_junction", None),
                getattr(evidence, "is_reparse_point", None),
            )
            if any(type(value) is not bool for value in fields):
                raise VaultError("invalid_path")
            exists, *reparse = fields
            if any(reparse) and not exists:
                raise VaultError("invalid_path")
            if exists and any(reparse):
                raise VaultError("reparse_point_forbidden")
        if not path.exists():
            raise VaultError("path_missing")
        return path.resolve(strict=True)
    except VaultError:
        raise
    except OSError:
        raise VaultError("invalid_path") from None


def _inside(path: Path, ancestor: Path) -> bool:
    return path == ancestor or ancestor in path.parents


def _validate_vault_evidence(information: VolumeInfo) -> None:
    if information.is_reparse_point:
        raise VaultError("reparse_point_forbidden")
    if information.filesystem.upper() != "NTFS":
        raise VaultError("vault_filesystem_not_ntfs")
    if not information.is_removable:
        raise VaultError("vault_not_removable")
    if not information.is_fully_encrypted or information.encryption_percentage != 100:
        raise VaultError("bitlocker_not_fully_encrypted")
    if not information.protection_on:
        raise VaultError("bitlocker_protection_off")
    if information.is_locked:
        raise VaultError("bitlocker_locked")


__all__ = ["validate_existing_vault_location"]
