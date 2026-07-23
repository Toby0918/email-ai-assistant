"""Provider-disabled operational state for Managed Container Mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.project_layout import OperationalLayout, RepositoryPlacement

from .config import AppConfig, build_managed_container_config
from .managed_runtime_errors import (
    ManagedRuntimeError,
    managed_failure_code,
)
from .managed_runtime_validation import (
    DirectoryIdentity,
    FileIdentity,
    WritableTargetIdentity,
    ensure_directory,
    read_managed_settings,
    validate_directory,
    validate_file,
    validate_file_target,
    validate_writable_directory,
)


@dataclass(frozen=True, slots=True)
class ManagedRuntime:
    """Resolved ordinary Managed paths without private capabilities."""

    placement: RepositoryPlacement
    layout: OperationalLayout
    database_path: Path
    attachment_temp_dir: Path
    log_file: Path
    pid_file: Path
    python_executable: Path
    config: AppConfig


@dataclass(frozen=True, slots=True)
class _ManagedPreflight:
    zone_identities: tuple[tuple[Path, DirectoryIdentity], ...]
    database_path: Path
    attachment_temp_dir: Path
    log_file: Path
    pid_file: Path
    python_executable: Path
    python_identity: FileIdentity
    target_identities: tuple[
        tuple[Path, WritableTargetIdentity],
        ...,
    ]


def prepare_managed_runtime(
    *,
    repository_root: Path,
    project_container: Path,
) -> ManagedRuntime:
    """Validate exact Managed placement before any operational work."""
    placement = RepositoryPlacement.managed(
        repository_root=repository_root,
        project_container=project_container,
    )
    layout = OperationalLayout.for_placement(placement)
    preflight = _preflight_managed_layout(layout)
    config = _load_managed_config(layout=layout, preflight=preflight)
    attachment_identity = ensure_directory(
        preflight.attachment_temp_dir
    )
    _revalidate_managed_preflight(
        preflight=preflight,
        attachment_temp_identity=attachment_identity,
    )
    return ManagedRuntime(
        placement=placement,
        layout=layout,
        database_path=preflight.database_path,
        attachment_temp_dir=preflight.attachment_temp_dir,
        log_file=preflight.log_file,
        pid_file=preflight.pid_file,
        python_executable=preflight.python_executable,
        config=config,
    )


def _preflight_managed_layout(
    layout: OperationalLayout,
) -> _ManagedPreflight:
    zone_identities = _validate_managed_zone_roots(layout)
    for writable_root in (
        layout.data_root,
        layout.temporary_root,
        layout.log_root,
    ):
        validate_writable_directory(writable_root)
    python_executable, python_identity = _managed_python_executable(layout)
    database_path = layout.data_root / "email_agent.sqlite3"
    attachment_temp_dir = layout.temporary_root / "attachment_temp"
    log_file = layout.log_root / "local_debug_service.log"
    pid_file = layout.log_root / "local_debug_service.pid"
    target_identities = tuple(
        (file_target, validate_file_target(file_target))
        for file_target in (database_path, log_file, pid_file)
    )
    return _ManagedPreflight(
        zone_identities=zone_identities,
        database_path=database_path,
        attachment_temp_dir=attachment_temp_dir,
        log_file=log_file,
        pid_file=pid_file,
        python_executable=python_executable,
        python_identity=python_identity,
        target_identities=target_identities,
    )


def _validate_managed_zone_roots(
    layout: OperationalLayout,
) -> tuple[tuple[Path, DirectoryIdentity], ...]:
    directories = (
        layout.runtime_root,
        layout.data_root,
        layout.temporary_root,
        layout.log_root,
        layout.artifact_root,
        layout.worktree_root,
        layout.configuration_root,
    )
    return tuple(
        (directory, validate_directory(directory))
        for directory in directories
    )


def _managed_python_executable(
    layout: OperationalLayout,
) -> tuple[Path, FileIdentity]:
    python_executable = (
        layout.runtime_root
        / "venv"
        / "Scripts"
        / "python.exe"
    )
    validate_directory(
        python_executable.parent.parent,
        code="managed_runtime_invalid",
    )
    validate_directory(
        python_executable.parent,
        code="managed_runtime_invalid",
    )
    identity = validate_file(
        python_executable,
        code="managed_runtime_invalid",
    )
    return python_executable, identity


def _revalidate_managed_preflight(
    *,
    preflight: _ManagedPreflight,
    attachment_temp_identity: DirectoryIdentity,
) -> None:
    for path, expected_identity in preflight.zone_identities:
        if validate_directory(path) != expected_identity:
            raise ManagedRuntimeError(
                "managed_operational_layout_invalid"
            )
    if (
        validate_file(
            preflight.python_executable,
            code="managed_runtime_invalid",
        )
        != preflight.python_identity
    ):
        raise ManagedRuntimeError("managed_runtime_invalid")
    for path, expected_identity in preflight.target_identities:
        if validate_file_target(path) != expected_identity:
            raise ManagedRuntimeError(
                "managed_operational_layout_invalid"
            )
    if (
        validate_directory(preflight.attachment_temp_dir)
        != attachment_temp_identity
    ):
        raise ManagedRuntimeError("managed_operational_layout_invalid")


def _load_managed_config(
    *,
    layout: OperationalLayout,
    preflight: _ManagedPreflight,
) -> AppConfig:
    settings = read_managed_settings(
        layout.configuration_root / "settings.env"
    )
    try:
        config = build_managed_container_config(
            sqlite_path=preflight.database_path,
            attachment_temp_dir=preflight.attachment_temp_dir,
            settings=settings,
        )
    except (TypeError, ValueError):
        raise ManagedRuntimeError("managed_config_invalid") from None
    return config
