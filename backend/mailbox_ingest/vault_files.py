"""Ciphertext-only same-volume staging and filesystem operations."""

from __future__ import annotations

import os
import re
import stat
import uuid
from pathlib import Path

from .errors import VaultError


_RECORD_PATH = re.compile(r"^records/[0-9a-f]{2}/[0-9a-f]{32}\.mvlt$")


class AtomicCiphertextStore:
    def __init__(self, vault_root: Path) -> None:
        self._root = Path(vault_root).resolve()

    def _resolve(self, relative_path: str, *, create_parent: bool = False) -> Path:
        if not isinstance(relative_path, str) or _RECORD_PATH.fullmatch(relative_path) is None:
            raise VaultError("ciphertext_path_invalid")
        path = self._root.joinpath(*relative_path.split("/"))
        try:
            if create_parent:
                path.parent.mkdir(parents=True, exist_ok=True)
            parent = path.parent.resolve(strict=True)
        except OSError:
            code = "ciphertext_write_failed" if create_parent else "ciphertext_path_invalid"
            raise VaultError(code) from None
        if parent != self._root and self._root not in parent.parents:
            raise VaultError("ciphertext_path_invalid")
        return path

    def write(self, relative_path: str, ciphertext: bytes) -> None:
        if type(ciphertext) is not bytes:
            raise VaultError("ciphertext_write_failed")
        path = self._resolve(relative_path, create_parent=True)
        stage = path.with_name(f".{uuid.uuid4().hex}.stage")
        descriptor: int | None = None
        try:
            if path.exists():
                raise VaultError("ciphertext_write_failed")
            descriptor = os.open(
                stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            _write_all(descriptor, ciphertext)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            if os.stat(stage).st_dev != os.stat(path.parent).st_dev:
                raise VaultError("ciphertext_write_failed")
            os.replace(stage, path)
            _fsync_directory(path.parent)
        except VaultError:
            raise
        except OSError:
            raise VaultError("ciphertext_write_failed") from None
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

    def read(self, relative_path: str, *, max_size: int) -> bytes:
        path = self._resolve(relative_path)
        try:
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
                raise VaultError("ciphertext_path_invalid")
            if metadata.st_size < 1 or metadata.st_size > max_size:
                raise VaultError("ciphertext_read_failed")
            data = path.read_bytes()
        except FileNotFoundError:
            raise VaultError("ciphertext_missing") from None
        except VaultError:
            raise
        except OSError:
            raise VaultError("ciphertext_read_failed") from None
        if len(data) != metadata.st_size:
            raise VaultError("ciphertext_read_failed")
        return data

    def unlink(self, relative_path: str) -> None:
        path = self._resolve(relative_path)
        try:
            if path.exists() and (path.is_symlink() or not path.is_file()):
                raise VaultError("ciphertext_path_invalid")
            path.unlink(missing_ok=True)
            _fsync_directory(path.parent)
        except VaultError:
            raise
        except OSError:
            raise VaultError("ciphertext_delete_failed") from None

    def exists(self, relative_path: str) -> bool:
        path = self._resolve(relative_path)
        try:
            return path.is_file() and not path.is_symlink()
        except OSError:
            return False

    def iter_paths(self) -> set[str]:
        records = self._root / "records"
        if not records.exists():
            return set()
        result: set[str] = set()
        try:
            for path in records.glob("*/*.mvlt"):
                relative = path.relative_to(self._root).as_posix()
                if _RECORD_PATH.fullmatch(relative) and path.is_file() and not path.is_symlink():
                    result.add(relative)
        except OSError:
            raise VaultError("ciphertext_read_failed") from None
        return result

    def __repr__(self) -> str:
        return "AtomicCiphertextStore(<redacted>)"


def _write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
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
