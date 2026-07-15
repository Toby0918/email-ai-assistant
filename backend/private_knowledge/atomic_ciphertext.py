"""Bounded same-directory ciphertext replacement and exclusive mutation lock."""

from __future__ import annotations

import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from .errors import PrivateKnowledgeError


def read_ciphertext(path: Path, *, maximum: int, code: str) -> bytes:
    try:
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            raise OSError
        if not 1 <= metadata.st_size <= maximum:
            raise OSError
        value = path.read_bytes()
    except OSError:
        raise PrivateKnowledgeError(code) from None
    if len(value) != metadata.st_size:
        raise PrivateKnowledgeError(code)
    return value


def replace_ciphertext(
    path: Path,
    value: bytes,
    *,
    error_code: str,
    crash_hook: Callable[[str], None] | None = None,
) -> None:
    stage = path.with_name(f".{uuid.uuid4().hex}.stage")
    descriptor: int | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            stage,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        _write_all(descriptor, value)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        if crash_hook is not None:
            crash_hook("before_replace")
        os.replace(stage, path)
        _fsync_directory(path.parent)
    except Exception:
        raise PrivateKnowledgeError(error_code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        try:
            stage.unlink(missing_ok=True)
        except OSError:
            pass


@contextmanager
def exclusive_lock(root: Path, name: str, *, error_code: str) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    lock = root / name
    descriptor: int | None = None
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        yield
    except PrivateKnowledgeError:
        raise
    except OSError:
        raise PrivateKnowledgeError(error_code) from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                pass


def _write_all(descriptor: int, value: bytes) -> None:
    view = memoryview(value)
    offset = 0
    while offset < len(view):
        written = os.write(descriptor, view[offset:])
        if written <= 0:
            raise OSError
        offset += written


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
