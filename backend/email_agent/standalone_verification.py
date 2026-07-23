"""Safe operational state for repository-only standalone verification."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.project_layout import (
    OperationalLayout,
    PlacementError,
    RepositoryPlacement,
    StandaloneStateKind,
)

from .config import AppConfig, build_standalone_verification_config


DirectoryInspector = Callable[[Path], object]


@dataclass(frozen=True, slots=True)
class StandaloneRuntime:
    """Validated writable paths and deterministic provider-disabled config."""

    state_root: Path
    database_path: Path
    attachment_temp_dir: Path
    log_file: Path
    pid_file: Path
    config: AppConfig


def prepare_standalone_runtime(
    *,
    repository_root: Path,
    state_root: Path,
    inspect_directory: DirectoryInspector | None = None,
) -> StandaloneRuntime:
    """Create then validate ordinary directories under explicit temporary state."""
    placement = RepositoryPlacement.standalone(
        repository_root=repository_root,
        state_root=state_root,
        state_kind=StandaloneStateKind.TEMPORARY,
        inspect_directory=inspect_directory,
    )
    layout = OperationalLayout.for_placement(placement)
    attachment_temp_dir = layout.temporary_root / "attachment_temp"
    directories = (
        layout.data_root,
        layout.temporary_root,
        attachment_temp_dir,
        layout.log_root,
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        _validate_operational_directory(
            repository_root=repository_root,
            directory=directory,
            inspect_directory=inspect_directory,
        )
    database_path = layout.data_root / "email_agent.sqlite3"
    log_file = layout.log_root / "local_debug_service.log"
    pid_file = layout.log_root / "local_debug_service.pid"
    _reject_reparse_file_targets((database_path, log_file, pid_file))
    config = build_standalone_verification_config(
        sqlite_path=database_path,
        attachment_temp_dir=attachment_temp_dir,
    )
    return StandaloneRuntime(
        state_root=layout.data_root.parent,
        database_path=database_path,
        attachment_temp_dir=attachment_temp_dir,
        log_file=log_file,
        pid_file=pid_file,
        config=config,
    )


def _validate_operational_directory(
    *,
    repository_root: Path,
    directory: Path,
    inspect_directory: DirectoryInspector | None,
) -> None:
    RepositoryPlacement.standalone(
        repository_root=repository_root,
        state_root=directory,
        state_kind=StandaloneStateKind.TEMPORARY,
        inspect_directory=inspect_directory,
    )


def _reject_reparse_file_targets(paths: tuple[Path, ...]) -> None:
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    for path in paths:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            continue
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        if (
            stat.S_ISLNK(metadata.st_mode)
            or attributes & reparse_mask
            or not stat.S_ISREG(metadata.st_mode)
        ):
            raise PlacementError("placement_reparse_forbidden")
