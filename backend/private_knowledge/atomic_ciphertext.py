"""Bounded same-directory ciphertext replacement and exclusive mutation lock."""

from __future__ import annotations

import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from .checked_reader import read_bounded_checked, validate_read_path
from .errors import PrivateKnowledgeError


def read_ciphertext(path: Path, *, maximum: int, code: str) -> bytes:
    return read_bounded_checked(
        Path(path),
        maximum,
        lambda value: validate_read_path(value, error_code=code),
        _test_read_race_hook,
        error_code=code,
    )


def _test_read_race_hook(_stage: str, _path: Path) -> None:
    """No-op seam; tests may mutate paths and all identity checks still run."""
    return None


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
    lock = root / name
    descriptor: int | None = None
    acquired = False
    try:
        root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(
            lock,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0),
            0o600,
        )
        _prepare_lock_file(lock, descriptor)
        _acquire_file_lock(descriptor)
        acquired = True
        yield
    except PrivateKnowledgeError:
        raise
    except OSError:
        raise PrivateKnowledgeError(error_code) from None
    finally:
        if descriptor is not None:
            if acquired:
                try:
                    _release_file_lock(descriptor)
                except OSError:
                    pass
            try:
                os.close(descriptor)
            except OSError:
                pass


def _prepare_lock_file(path: Path, descriptor: int) -> None:
    opened = os.fstat(descriptor)
    linked = path.lstat()
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (not stat.S_ISREG(opened.st_mode) or not stat.S_ISREG(linked.st_mode)
            or stat.S_ISLNK(linked.st_mode)
            or getattr(linked, "st_file_attributes", 0) & reparse):
        raise OSError
    if opened.st_size == 0:
        os.lseek(descriptor, 0, os.SEEK_SET)
        _write_all(descriptor, b"\0")
        os.fsync(descriptor)
    os.lseek(descriptor, 0, os.SEEK_SET)


def _acquire_file_lock(descriptor: int) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _release_file_lock(descriptor: int) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


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
