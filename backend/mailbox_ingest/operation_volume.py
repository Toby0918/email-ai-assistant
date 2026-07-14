"""Execute-time binding for prepared removable-volume evidence."""

from __future__ import annotations

from pathlib import Path

from .errors import VaultError
from .models import VolumeEvidence


def revalidate_preflight_volume(
    validator: object,
    vault: Path,
    project_root: Path,
    recovery: Path,
    expected: object,
) -> VolumeEvidence:
    try:
        actual = validator(vault, project_root, recovery)
    except VaultError:
        raise
    except Exception:
        raise VaultError("volume_probe_failed") from None
    if (
        not isinstance(expected, VolumeEvidence)
        or not isinstance(actual, VolumeEvidence)
        or expected.verified is not True
        or actual.verified is not True
        or actual.vault_volume_id != expected.vault_volume_id
        or actual.recovery_volume_id != expected.recovery_volume_id
        or actual.vault_volume_id == actual.recovery_volume_id
    ):
        raise VaultError("recovery_volume_not_separate")
    return actual


def bound_distinct_checker(
    expected_vault: Path,
    expected_recovery: Path,
    evidence: VolumeEvidence,
):
    def check(vault: Path, recovery: Path) -> bool:
        return (
            Path(vault) == expected_vault
            and Path(recovery) == expected_recovery
            and evidence.verified is True
            and evidence.vault_volume_id != evidence.recovery_volume_id
        )

    return check


__all__ = ["bound_distinct_checker", "revalidate_preflight_volume"]
