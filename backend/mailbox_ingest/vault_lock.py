"""Exclusive mailbox-vault mutation lock."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from .errors import VaultError


class VaultMutationLock:
    """Fail closed when another mutation is in progress or left a stale lock."""

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
        descriptor: int | None = None
        try:
            descriptor = os.open(
                self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            os.fsync(descriptor)
        except (FileExistsError, OSError):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
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
                os.close(descriptor)
            finally:
                try:
                    self._path.unlink(missing_ok=True)
                except OSError:
                    pass

    def __repr__(self) -> str:
        return "VaultMutationLock(<redacted>)"
