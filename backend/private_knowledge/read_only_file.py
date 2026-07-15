"""Bounded ordinary-file reader kept separate from all write helpers."""

from __future__ import annotations

import stat
from pathlib import Path

from .errors import PrivateKnowledgeError


def read_snapshot_file(path: Path, *, maximum: int = 4 * 1024 * 1024) -> bytes:
    try:
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise OSError
        if not 1 <= metadata.st_size <= maximum:
            raise OSError
        value = path.read_bytes()
    except FileNotFoundError:
        raise PrivateKnowledgeError("snapshot_missing") from None
    except OSError:
        raise PrivateKnowledgeError("snapshot_unavailable") from None
    if len(value) != metadata.st_size:
        raise PrivateKnowledgeError("snapshot_unavailable")
    return value
