"""Descriptor-bound bounded reads for reviewed regular files."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .bound_file import close_guards, open_bound_file, relative_parts
from .errors import MigrationEvidenceError
from .path_checks import require_existing_non_reparse_directory


_DEFAULT_MAXIMUM = 16 * 1024 * 1024
_READ_CHUNK = 64 * 1024


def read_checked_file(
    root: Path,
    relative: str,
    *,
    maximum: int = _DEFAULT_MAXIMUM,
) -> bytes:
    """Read one bounded regular file with stable descriptor identity."""

    if type(maximum) is not int or not 1 <= maximum <= 256 * 1024 * 1024:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    parts = relative_parts(relative)
    root_resolved = require_existing_non_reparse_directory(root)
    candidate = root_resolved.joinpath(*parts)
    descriptor = -1
    guards: list[int] = []
    try:
        before = _file_identity(candidate)
        descriptor, guards = open_bound_file(root_resolved, parts)
        opened = _identity_from_stat(os.fstat(descriptor))
        if opened != before or opened[3] > maximum:
            raise MigrationEvidenceError("migration_evidence_create_failed")
        payload = _read_limit(descriptor, maximum + 1)
        if len(payload) > maximum:
            raise MigrationEvidenceError("migration_evidence_create_failed")
        if _identity_from_stat(os.fstat(descriptor)) != opened:
            raise MigrationEvidenceError("migration_evidence_create_failed")
        if _file_identity(candidate) != opened:
            raise MigrationEvidenceError("migration_evidence_create_failed")
        return payload
    except MigrationEvidenceError:
        raise
    except Exception:
        raise MigrationEvidenceError("migration_evidence_create_failed") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        close_guards(guards)


def _file_identity(path: Path) -> tuple[int, int, int, int, int]:
    try:
        metadata = os.lstat(path)
    except OSError:
        raise MigrationEvidenceError("migration_evidence_create_failed") from None
    return _identity_from_stat(metadata)


def _identity_from_stat(metadata) -> tuple[int, int, int, int, int]:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & reparse
        or metadata.st_nlink != 1
    ):
        raise MigrationEvidenceError("migration_evidence_create_failed")
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _read_limit(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while remaining:
        chunk = os.read(descriptor, min(_READ_CHUNK, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
