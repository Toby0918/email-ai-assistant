"""External-volume revalidation for commands that do not need recovery media."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .drive_policy import (
    FixedWindowsVolumeProbe,
    PathComponentProbe,
    VolumeProbe,
    _validate_vault_evidence,
)
from .protected_storage_path import (
    RepositoryContext,
    _has_onedrive_component,
    _inside_views,
    _protected_policy,
    _validated_path,
)
from .errors import VaultError
from .models import VaultVolumeEvidence


def validate_existing_vault_location(
    vault_root: Path,
    project_root: RepositoryContext,
    *,
    probe: VolumeProbe | None = None,
    component_probe: PathComponentProbe | None = None,
    system_temp: Path | None = None,
) -> VaultVolumeEvidence:
    """Revalidate an existing vault without requiring recovery media online."""

    vault = _validated_path(
        Path(vault_root),
        must_exist=True,
        component_probe=component_probe,
    )
    protected = _protected_policy(project_root)
    _validated_path(
        protected.repository_root,
        must_exist=True,
        component_probe=component_probe,
    )
    temp = _validated_path(
        Path(tempfile.gettempdir()) if system_temp is None else Path(system_temp),
        must_exist=True,
        component_probe=component_probe,
    )
    if protected.contains(
        original_path=vault.original,
        resolved_path=vault.resolved,
    ) or _inside_views(vault, temp):
        raise VaultError("prohibited_vault_location")
    if _has_onedrive_component(vault):
        raise VaultError("prohibited_vault_location")
    selected_probe = FixedWindowsVolumeProbe() if probe is None else probe
    try:
        information = selected_probe.inspect(vault.resolved)
    except VaultError:
        raise
    except Exception:
        raise VaultError("volume_probe_failed") from None
    _validate_vault_evidence(information)
    return VaultVolumeEvidence(information.stable_volume_id)


__all__ = ["validate_existing_vault_location"]
