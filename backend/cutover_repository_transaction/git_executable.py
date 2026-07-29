"""Bounded content binding for the fixed Git executable."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .errors import RepositoryTransactionError

_MAX_EXECUTABLE_BYTES = 128 * 1024 * 1024


def resolved_executable() -> Path:
    value = shutil.which("git")
    if not value:
        _fail()
    try:
        return Path(value).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail()


def executable_content_fingerprint(path: Path) -> str:
    digest = hashlib.sha256(b"issue56-git-executable-content-v1\0")
    size = 0
    try:
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > _MAX_EXECUTABLE_BYTES:
                    _fail()
                digest.update(block)
    except RepositoryTransactionError:
        raise
    except OSError:
        _fail()
    digest.update(size.to_bytes(8, "big"))
    return digest.hexdigest()


def _fail() -> None:
    raise RepositoryTransactionError("repository_git_runner_invalid") from None
