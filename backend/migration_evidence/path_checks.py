"""Absolute path checks that reject symlink and reparse ancestors."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import MigrationEvidenceError


def require_existing_non_reparse_directory(path: Path) -> Path:
    """Return the exact existing directory after checking every component."""

    if not isinstance(path, Path) or not path.is_absolute():
        _fail()
    _require_non_reparse_chain(path)
    try:
        resolved = path.resolve(strict=True)
        metadata = os.lstat(path)
    except OSError:
        _fail()
    if resolved != path.absolute() or not stat.S_ISDIR(metadata.st_mode):
        _fail()
    return resolved


def require_non_reparse_parent(path: Path) -> Path:
    """Return an absent leaf under an existing non-reparse parent."""

    if not isinstance(path, Path) or not path.is_absolute():
        _fail()
    parent = require_existing_non_reparse_directory(path.parent)
    try:
        os.lstat(path)
    except FileNotFoundError:
        return parent / path.name
    except OSError:
        _fail()
    _fail()


def _require_non_reparse_chain(path: Path) -> None:
    values = tuple(reversed(path.absolute().parents)) + (path.absolute(),)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for value in values:
        try:
            metadata = os.lstat(value)
        except OSError:
            _fail()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & reparse
        ):
            _fail()


def _fail() -> None:
    raise MigrationEvidenceError("migration_evidence_review_failed")
