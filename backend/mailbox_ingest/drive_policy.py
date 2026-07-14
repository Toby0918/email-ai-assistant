"""Fail-closed external-volume policy with a lazily used Windows probe."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Protocol

from .errors import VaultError
from .models import VolumeEvidence, VolumeInfo


_POWERSHELL_VOLUME_QUERY = r"""
$item = Get-Item -LiteralPath $args[0] -Force
$root = [System.IO.Path]::GetPathRoot($item.FullName)
$volume = Get-Volume -FilePath $item.FullName
$bitlocker = Get-BitLockerVolume -MountPoint $root
[ordered]@{
 stable_volume_id = [string]$volume.UniqueId
 filesystem = [string]$volume.FileSystem
 is_removable = ([string]$volume.DriveType -eq 'Removable')
 is_fully_encrypted = ([string]$bitlocker.VolumeStatus -eq 'FullyEncrypted')
 protection_on = ([string]$bitlocker.ProtectionStatus -eq 'On')
 is_locked = ([string]$bitlocker.LockStatus -eq 'Locked')
 encryption_percentage = [int]$bitlocker.EncryptionPercentage
 is_reparse_point = (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)
} | ConvertTo-Json -Compress
""".strip()


class VolumeProbe(Protocol):
    def inspect(self, path: Path) -> VolumeInfo: ...


class FixedWindowsVolumeProbe:
    """Query structured Windows volume facts using fixed argv and no shell."""

    def __init__(
        self,
        *,
        runner: Callable[..., object] = subprocess.run,
        platform: str | None = None,
    ) -> None:
        self._runner = runner
        self._platform = sys.platform if platform is None else platform

    def inspect(self, path: Path) -> VolumeInfo:
        if not self._platform.startswith("win"):
            raise VaultError("unsupported_platform")
        argv = [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _POWERSHELL_VOLUME_QUERY,
            str(path),
        ]
        try:
            completed = self._runner(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if completed.returncode != 0:
                raise VaultError("volume_probe_failed")
            payload = json.loads(completed.stdout)
            return _parse_volume_info(payload)
        except VaultError:
            raise
        except Exception:
            raise VaultError("volume_probe_failed") from None


def _parse_volume_info(payload: object) -> VolumeInfo:
    required = {
        "stable_volume_id",
        "filesystem",
        "is_removable",
        "is_fully_encrypted",
        "protection_on",
        "is_locked",
        "encryption_percentage",
        "is_reparse_point",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise VaultError("volume_probe_failed")
    if not isinstance(payload["stable_volume_id"], str) or not payload["stable_volume_id"]:
        raise VaultError("volume_probe_failed")
    try:
        return VolumeInfo(
            stable_volume_id=payload["stable_volume_id"],
            filesystem=str(payload["filesystem"]),
            is_removable=_strict_bool(payload["is_removable"]),
            is_fully_encrypted=_strict_bool(payload["is_fully_encrypted"]),
            protection_on=_strict_bool(payload["protection_on"]),
            is_locked=_strict_bool(payload["is_locked"]),
            encryption_percentage=_strict_int(payload["encryption_percentage"]),
            is_reparse_point=_strict_bool(payload["is_reparse_point"]),
        )
    except (TypeError, ValueError):
        raise VaultError("volume_probe_failed") from None


def _strict_bool(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError
    return value


def _strict_int(value: object) -> int:
    if type(value) is not int:
        raise TypeError
    return value


def _inside(path: Path, ancestor: Path) -> bool:
    return path == ancestor or ancestor in path.parents


def _validated_path(path: Path, *, must_exist: bool) -> Path:
    if not path.is_absolute():
        raise VaultError("path_not_absolute")
    try:
        if path.is_symlink() or (
            hasattr(path, "is_junction") and path.is_junction()
        ):
            raise VaultError("reparse_point_forbidden")
        if must_exist and not path.exists():
            raise VaultError("path_missing")
        return path.resolve(strict=must_exist)
    except VaultError:
        raise
    except OSError:
        raise VaultError("invalid_path") from None


def _reject_forbidden_locations(
    vault: Path,
    recovery_parent: Path,
    project: Path,
    system_temp: Path,
) -> None:
    forbidden = (project, system_temp)
    if any(_inside(vault, root) for root in forbidden):
        raise VaultError("prohibited_vault_location")
    if any(part.casefold().startswith("onedrive") for part in vault.parts):
        raise VaultError("prohibited_vault_location")
    if _inside(recovery_parent, vault) or any(
        _inside(recovery_parent, root) for root in forbidden
    ):
        raise VaultError("prohibited_recovery_location")
    if any(part.casefold().startswith("onedrive") for part in recovery_parent.parts):
        raise VaultError("prohibited_recovery_location")


def _validate_vault_evidence(vault_info: VolumeInfo) -> None:
    if vault_info.is_reparse_point:
        raise VaultError("reparse_point_forbidden")
    if vault_info.filesystem.upper() != "NTFS":
        raise VaultError("vault_filesystem_not_ntfs")
    if not vault_info.is_removable:
        raise VaultError("vault_not_removable")
    if not vault_info.is_fully_encrypted or vault_info.encryption_percentage != 100:
        raise VaultError("bitlocker_not_fully_encrypted")
    if not vault_info.protection_on:
        raise VaultError("bitlocker_protection_off")
    if vault_info.is_locked:
        raise VaultError("bitlocker_locked")


def validate_vault_location(
    vault_root: Path,
    project_root: Path,
    recovery_key_path: Path,
    *,
    probe: VolumeProbe | None = None,
    system_temp: Path | None = None,
) -> VolumeEvidence:
    """Validate external-vault and distinct recovery-volume evidence."""

    vault = _validated_path(Path(vault_root), must_exist=True)
    project = _validated_path(Path(project_root), must_exist=True)
    recovery_path = Path(recovery_key_path)
    if not recovery_path.is_absolute():
        raise VaultError("path_not_absolute")
    recovery_parent = _validated_path(recovery_path.parent, must_exist=True)
    temp = _validated_path(
        Path(tempfile.gettempdir()) if system_temp is None else Path(system_temp),
        must_exist=True,
    )
    _reject_forbidden_locations(vault, recovery_parent, project, temp)
    selected_probe = FixedWindowsVolumeProbe() if probe is None else probe
    try:
        vault_info = selected_probe.inspect(vault)
        recovery_info = selected_probe.inspect(recovery_parent)
    except VaultError:
        raise
    except Exception:
        raise VaultError("volume_probe_failed") from None
    _validate_vault_evidence(vault_info)
    if recovery_info.is_reparse_point:
        raise VaultError("reparse_point_forbidden")
    if vault_info.stable_volume_id == recovery_info.stable_volume_id:
        raise VaultError("recovery_volume_not_separate")
    return VolumeEvidence(
        vault_volume_id=vault_info.stable_volume_id,
        recovery_volume_id=recovery_info.stable_volume_id,
    )
