"""Exact fixed-volume Windows object and opaque directory fingerprints."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from backend.cutover_host_mutation.windows_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
)

from .errors import RepositoryTransactionError

_MAX_ADMIN_BYTES = 1_000_000
_MAX_ADMIN_NODES = 128


def directory_identity(path: Path) -> str:
    return directory_identity_and_volume(path)[0]


def directory_identity_and_volume(path: Path) -> tuple[str, str]:
    api = WindowsHandleApi()
    handle = _open_directory(api, path)
    try:
        observed = api.observe(handle)
    finally:
        api.close(handle)
    if (
        not observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or observed.drive_type != "fixed"
    ):
        _fail()
    return (
        observed.object_identity_fingerprint,
        observed.volume_fingerprint,
    )


def file_identity(path: Path) -> str:
    api = WindowsHandleApi()
    try:
        handle = api.open_existing(path, access=FILE_READ_ATTRIBUTES)
        observed = api.observe(handle)
    except Exception:
        _fail()
    finally:
        if "handle" in locals():
            api.close(handle)
    if (
        observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or observed.drive_type != "fixed"
    ):
        _fail()
    return observed.object_identity_fingerprint


def opaque_directory_fingerprint(path: Path) -> str:
    digest = hashlib.sha256(b"issue56-admin-object-v1\0")
    nodes = 0
    total = 0
    for child in sorted(
        path.rglob("*"), key=lambda value: str(value).casefold()
    ):
        nodes += 1
        if nodes > _MAX_ADMIN_NODES:
            _fail()
        metadata = child.lstat()
        relative = child.relative_to(path).as_posix().encode("utf-8")
        if child.is_symlink() or _is_reparse(metadata):
            _fail()
        if stat.S_ISDIR(metadata.st_mode):
            digest.update(b"D\0" + relative + b"\0")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            _fail()
        payload = child.read_bytes()
        total += len(payload)
        if total > _MAX_ADMIN_BYTES:
            _fail()
        digest.update(b"F\0" + relative + b"\0")
        digest.update(hashlib.sha256(payload).digest())
    return digest.hexdigest()


def _open_directory(api: WindowsHandleApi, path: Path) -> int:
    try:
        return api.open_existing(path, access=FILE_READ_ATTRIBUTES)
    except Exception:
        _fail()


def _is_reparse(metadata) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _fail() -> None:
    raise RepositoryTransactionError("repository_scope_invalid") from None
