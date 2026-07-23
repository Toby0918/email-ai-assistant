"""Provider-disabled operational state for Managed Container Mode."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from backend.project_layout import OperationalLayout, RepositoryPlacement

from .config import AppConfig, build_managed_container_config


MAX_MANAGED_SETTINGS_BYTES = 16 * 1024


class ManagedRuntimeError(ValueError):
    """A fixed, content-free Managed runtime failure."""

    def __init__(self, code: str) -> None:
        safe_code = (
            code
            if code
            in {
                "managed_config_invalid",
                "managed_operational_layout_invalid",
            }
            else "managed_runtime_invalid"
        )
        self.code = safe_code
        super().__init__(safe_code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"ManagedRuntimeError(code={self.code!r})"


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
    _validate_managed_zone_roots(layout)
    python_executable = _managed_python_executable(layout)
    database_path = layout.data_root / "email_agent.sqlite3"
    attachment_temp_dir = layout.temporary_root / "attachment_temp"
    log_file = layout.log_root / "local_debug_service.log"
    pid_file = layout.log_root / "local_debug_service.pid"
    for file_target in (database_path, log_file, pid_file):
        _validate_managed_file_target(file_target)
    config = _load_managed_config(
        layout=layout,
        database_path=database_path,
        attachment_temp_dir=attachment_temp_dir,
    )
    _ensure_managed_directory(attachment_temp_dir)
    return ManagedRuntime(
        placement=placement,
        layout=layout,
        database_path=database_path,
        attachment_temp_dir=attachment_temp_dir,
        log_file=log_file,
        pid_file=pid_file,
        python_executable=python_executable,
        config=config,
    )


def _validate_managed_zone_roots(layout: OperationalLayout) -> None:
    for directory in (
        layout.runtime_root,
        layout.data_root,
        layout.temporary_root,
        layout.log_root,
        layout.artifact_root,
        layout.worktree_root,
        layout.configuration_root,
    ):
        _validate_managed_directory(directory)


def _managed_python_executable(layout: OperationalLayout) -> Path:
    python_executable = (
        layout.runtime_root
        / "venv"
        / "Scripts"
        / "python.exe"
    )
    _validate_managed_directory(
        python_executable.parent.parent,
        code="managed_runtime_invalid",
    )
    _validate_managed_directory(
        python_executable.parent,
        code="managed_runtime_invalid",
    )
    _validate_managed_file(
        python_executable,
        code="managed_runtime_invalid",
    )
    return python_executable


def _load_managed_config(
    *,
    layout: OperationalLayout,
    database_path: Path,
    attachment_temp_dir: Path,
) -> AppConfig:
    settings = _read_managed_settings(
        layout.configuration_root / "settings.env"
    )
    try:
        config = build_managed_container_config(
            sqlite_path=database_path,
            attachment_temp_dir=attachment_temp_dir,
            settings=settings,
        )
    except (TypeError, ValueError):
        raise ManagedRuntimeError("managed_config_invalid") from None
    return config


def _read_managed_settings(path: Path) -> dict[str, str]:
    try:
        path.lstat()
    except FileNotFoundError:
        return {}
    except OSError:
        raise ManagedRuntimeError("managed_config_invalid") from None
    expected_identity = _validate_managed_file(
        path,
        code="managed_config_invalid",
    )
    try:
        with path.open("rb") as settings_file:
            opened_identity = _file_identity_tuple(
                os.fstat(settings_file.fileno())
            )
            if opened_identity != expected_identity:
                raise ManagedRuntimeError("managed_config_invalid")
            payload = settings_file.read(MAX_MANAGED_SETTINGS_BYTES + 1)
            if (
                _file_identity_tuple(os.fstat(settings_file.fileno()))
                != opened_identity
            ):
                raise ManagedRuntimeError("managed_config_invalid")
        if len(payload) > MAX_MANAGED_SETTINGS_BYTES:
            raise ManagedRuntimeError("managed_config_invalid")
        lines = payload.decode("utf-8").splitlines()
    except (OSError, UnicodeError):
        raise ManagedRuntimeError("managed_config_invalid") from None
    if (
        _validate_managed_file(path, code="managed_config_invalid")
        != expected_identity
    ):
        raise ManagedRuntimeError("managed_config_invalid")
    settings: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ManagedRuntimeError("managed_config_invalid")
        key, value = line.split("=", 1)
        key = key.strip()
        if key in settings:
            raise ManagedRuntimeError("managed_config_invalid")
        settings[key] = value.strip()
    return settings


def _validate_managed_directory(
    path: Path,
    *,
    code: str = "managed_operational_layout_invalid",
) -> None:
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    try:
        before = path.lstat()
        resolved = path.resolve(strict=True)
        after = path.lstat()
    except (OSError, RuntimeError):
        raise ManagedRuntimeError(code) from None
    before_attributes = int(
        getattr(before, "st_file_attributes", 0)
    )
    after_attributes = int(getattr(after, "st_file_attributes", 0))
    if (
        not stat.S_ISDIR(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before_attributes & reparse_mask
        or not stat.S_ISDIR(after.st_mode)
        or stat.S_ISLNK(after.st_mode)
        or after_attributes & reparse_mask
        or resolved != path
        or _identity_tuple(before) != _identity_tuple(after)
    ):
        raise ManagedRuntimeError(code)


def _validate_managed_file(
    path: Path,
    *,
    code: str,
) -> tuple[int, int, int, int, int, int]:
    reparse_mask = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    try:
        before = path.lstat()
        resolved = path.resolve(strict=True)
        after = path.lstat()
    except (OSError, RuntimeError):
        raise ManagedRuntimeError(code) from None
    before_attributes = int(getattr(before, "st_file_attributes", 0))
    after_attributes = int(getattr(after, "st_file_attributes", 0))
    if (
        not stat.S_ISREG(before.st_mode)
        or stat.S_ISLNK(before.st_mode)
        or before_attributes & reparse_mask
        or not stat.S_ISREG(after.st_mode)
        or stat.S_ISLNK(after.st_mode)
        or after_attributes & reparse_mask
        or resolved != path
        or _file_identity_tuple(before) != _file_identity_tuple(after)
    ):
        raise ManagedRuntimeError(code)
    return _file_identity_tuple(before)


def _validate_managed_file_target(path: Path) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise ManagedRuntimeError(
            "managed_operational_layout_invalid"
        ) from None
    _validate_managed_file(
        path,
        code="managed_operational_layout_invalid",
    )


def _ensure_managed_directory(path: Path) -> None:
    try:
        path.mkdir()
    except FileExistsError:
        pass
    except OSError:
        raise ManagedRuntimeError(
            "managed_operational_layout_invalid"
        ) from None
    _validate_managed_directory(path)


def _identity_tuple(metadata: object) -> tuple[int, int, int, int]:
    return (
        int(getattr(metadata, "st_dev")),
        int(getattr(metadata, "st_ino")),
        int(getattr(metadata, "st_mode")),
        int(getattr(metadata, "st_file_attributes", 0)),
    )


def _file_identity_tuple(
    metadata: object,
) -> tuple[int, int, int, int, int, int]:
    return (
        *_identity_tuple(metadata),
        int(getattr(metadata, "st_size")),
        int(getattr(metadata, "st_mtime_ns")),
    )
