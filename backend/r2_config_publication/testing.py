"""Validated binder for fresh synthetic Managed Config sandboxes."""

from __future__ import annotations

from pathlib import Path

from .contracts import (
    ConfigPublicationPrerequisiteV1,
    ManagedConfigSelectionV1,
)
from .transaction import SyntheticConfigPublicationTransaction


def bind_test_config_transaction(
    *,
    selection: object,
    staging: Path,
    target: Path,
    journal: Path,
    sqlite_path: Path,
    attachment_temp_dir: Path,
    quiescence_receipt_fingerprint: str,
):
    staging, target, journal, sqlite_path, attachment_temp_dir = map(
        Path,
        (staging, target, journal, sqlite_path, attachment_temp_dir),
    )
    if staging.exists() or staging.is_symlink():
        raise ValueError("config_pending_generation")
    if (
        type(selection) is not ManagedConfigSelectionV1
        or journal.exists()
        or staging.parent != target.parent
        or staging.name != "settings.env.prepare"
        or target.name != "settings.env"
        or not sqlite_path.is_absolute()
        or not attachment_temp_dir.is_absolute()
    ):
        raise ValueError("config_test_scope_invalid")
    prerequisite = ConfigPublicationPrerequisiteV1.create(
        quiescence_receipt_fingerprint=quiescence_receipt_fingerprint
    )
    return SyntheticConfigPublicationTransaction(
        selection=selection,
        staging=staging,
        target=target,
        journal=journal,
        prerequisite=prerequisite,
        sqlite_path=sqlite_path,
        attachment_temp_dir=attachment_temp_dir,
    )
