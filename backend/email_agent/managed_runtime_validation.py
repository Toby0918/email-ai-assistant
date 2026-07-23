"""Stable path and bounded-settings validation for Managed runtime."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .managed_runtime_errors import ManagedRuntimeError


MAX_MANAGED_SETTINGS_BYTES = 16 * 1024
DirectoryIdentity = tuple[int, int, int, int]
FileIdentity = tuple[int, int, int, int, int, int]
WritableTargetIdentity = DirectoryIdentity | None


def read_managed_settings(path: Path) -> dict[str, str]:
    """Read one stable bounded settings file, or return an empty mapping."""
    try:
        path.lstat()
    except FileNotFoundError:
        return {}
    except OSError:
        raise ManagedRuntimeError("managed_config_invalid") from None
    expected_identity = validate_file(
        path,
        code="managed_config_invalid",
    )
    payload = _read_stable_bounded_file(path, expected_identity)
    if (
        validate_file(path, code="managed_config_invalid")
        != expected_identity
    ):
        raise ManagedRuntimeError("managed_config_invalid")
    return _parse_managed_settings(payload)


def _read_stable_bounded_file(
    path: Path,
    expected_identity: FileIdentity,
) -> bytes:
    try:
        with path.open("rb") as settings_file:
            opened_identity = file_identity_tuple(
                os.fstat(settings_file.fileno())
            )
            if opened_identity != expected_identity:
                raise ManagedRuntimeError("managed_config_invalid")
            payload = settings_file.read(MAX_MANAGED_SETTINGS_BYTES + 1)
            if (
                file_identity_tuple(os.fstat(settings_file.fileno()))
                != opened_identity
            ):
                raise ManagedRuntimeError("managed_config_invalid")
    except OSError:
        raise ManagedRuntimeError("managed_config_invalid") from None
    if len(payload) > MAX_MANAGED_SETTINGS_BYTES:
        raise ManagedRuntimeError("managed_config_invalid")
    return payload


def _parse_managed_settings(payload: bytes) -> dict[str, str]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeError:
        raise ManagedRuntimeError("managed_config_invalid") from None
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


def validate_directory(
    path: Path,
    *,
    code: str = "managed_operational_layout_invalid",
) -> DirectoryIdentity:
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
        or identity_tuple(before) != identity_tuple(after)
    ):
        raise ManagedRuntimeError(code)
    return identity_tuple(before)


def validate_file(
    path: Path,
    *,
    code: str,
) -> FileIdentity:
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
        or file_identity_tuple(before) != file_identity_tuple(after)
    ):
        raise ManagedRuntimeError(code)
    return file_identity_tuple(before)


def validate_writable_directory(path: Path) -> DirectoryIdentity:
    identity = validate_directory(path)
    try:
        writable = os.access(path, os.W_OK)
    except OSError:
        writable = False
    if not writable:
        raise ManagedRuntimeError("managed_operational_layout_invalid")
    return identity


def validate_file_target(path: Path) -> WritableTargetIdentity:
    try:
        path.lstat()
    except FileNotFoundError:
        if not _path_is_writable(path.parent):
            raise ManagedRuntimeError(
                "managed_operational_layout_invalid"
            )
        return None
    except OSError:
        raise ManagedRuntimeError(
            "managed_operational_layout_invalid"
        ) from None
    identity = validate_file(
        path,
        code="managed_operational_layout_invalid",
    )
    if not _path_is_writable(path) or not _path_is_writable(path.parent):
        raise ManagedRuntimeError("managed_operational_layout_invalid")
    return identity[:4]


def _path_is_writable(path: Path) -> bool:
    try:
        return os.access(path, os.W_OK)
    except OSError:
        return False


def ensure_directory(path: Path) -> DirectoryIdentity:
    try:
        path.mkdir()
    except FileExistsError:
        pass
    except OSError:
        raise ManagedRuntimeError(
            "managed_operational_layout_invalid"
        ) from None
    return validate_directory(path)


def identity_tuple(metadata: object) -> DirectoryIdentity:
    return (
        int(getattr(metadata, "st_dev")),
        int(getattr(metadata, "st_ino")),
        int(getattr(metadata, "st_mode")),
        int(getattr(metadata, "st_file_attributes", 0)),
    )


def file_identity_tuple(metadata: object) -> FileIdentity:
    return (
        *identity_tuple(metadata),
        int(getattr(metadata, "st_size")),
        int(getattr(metadata, "st_mtime_ns")),
    )
