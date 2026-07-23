"""Exclusive mailbox-vault mutation lock."""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path

from .errors import VaultError

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class VaultMutationLock:
    """Fail closed for a live holder; the OS releases the lock after a crash."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._descriptor: int | None = None
        self._owner: threading.Thread | None = None
        self._depth = 0

    def __enter__(self) -> "VaultMutationLock":
        if self._descriptor is not None:
            if self._owner is threading.current_thread():
                self._depth += 1
                return self
            raise VaultError("vault_busy")
        try:
            descriptor = _open_and_lock(self._path)
        except OSError:
            raise VaultError("vault_busy") from None
        self._descriptor = descriptor
        self._owner = threading.current_thread()
        self._depth = 1
        return self

    def __exit__(self, *_args: object) -> None:
        if self._owner is not threading.current_thread():
            raise VaultError("vault_busy")
        self._depth -= 1
        if self._depth:
            return
        descriptor, self._descriptor = self._descriptor, None
        self._owner = None
        if descriptor is not None:
            try:
                _unlock(descriptor)
            finally:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def __repr__(self) -> str:
        return "VaultMutationLock(<redacted>)"


def _open_and_lock(path: Path) -> int:
    descriptor = os.open(
        path,
        os.O_RDWR | os.O_CREAT
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOINHERIT", 0)
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        opened = os.fstat(descriptor)
        selected = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or path.is_symlink()
            or (opened.st_dev, opened.st_ino)
            != (selected.st_dev, selected.st_ino)
            or opened.st_size not in (0, 1)
        ):
            raise OSError
        if opened.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        _lock(descriptor)
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _lock(descriptor: int) -> None:
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.name == "nt":
        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
    else:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(descriptor: int) -> None:
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        pass
