"""Held-handle durable filesystem primitives for the Issue #39 ledger."""

from __future__ import annotations

import contextlib
import ctypes
import os
import stat
from pathlib import Path


MAX_SEGMENT_BYTES = 32 * 1024 * 1024


@contextlib.contextmanager
def guard_directory(path: Path, *, flush: bool):
    """Hold one exact non-reparse directory against replacement."""

    if os.name == "nt":
        from backend.cutover_host_mutation.windows_handles import (
            FILE_ATTRIBUTE_DIRECTORY,
            FILE_ATTRIBUTE_REPARSE_POINT,
            FILE_READ_ATTRIBUTES,
            WindowsHandleApi,
        )

        api = WindowsHandleApi()
        handle = api.open_existing(
            path,
            access=FILE_READ_ATTRIBUTES | (0x00000002 if flush else 0),
            share_delete=False,
        )
        try:
            identity = api.observe(handle)
            if (
                not identity.file_attributes & FILE_ATTRIBUTE_DIRECTORY
                or identity.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
                or identity.filesystem_name != "NTFS"
                or identity.drive_type != "fixed"
            ):
                raise ValueError
            yield
            api.require_stable(handle, identity, path)
            if flush and not _flush_windows(handle):
                raise OSError
            api.require_stable(handle, identity, path)
        finally:
            api.close(handle)
        return
    before = _safe_directory_metadata(path)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            raise ValueError
        yield
        if flush:
            os.fsync(descriptor)
        after = _safe_directory_metadata(path)
        if _identity(opened) != _identity(after):
            raise ValueError
    finally:
        os.close(descriptor)


def write_segment(path: Path, payload: bytes) -> None:
    if not 1 <= len(payload) <= MAX_SEGMENT_BYTES:
        raise ValueError
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written < 1:
                raise OSError
            offset += written
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError
        os.lseek(descriptor, 0, os.SEEK_SET)
        if _read_descriptor(descriptor, len(payload)) != payload:
            raise ValueError
        if _identity(os.fstat(descriptor)) != _identity(metadata):
            raise ValueError
    finally:
        os.close(descriptor)


def read_segment(path: Path) -> bytes:
    before = _safe_file_metadata(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if _identity(opened) != _identity(before):
            raise ValueError
        payload = _read_descriptor(descriptor, MAX_SEGMENT_BYTES)
        if len(payload) != opened.st_size:
            raise ValueError
        if _identity(os.fstat(descriptor)) != _identity(opened):
            raise ValueError
    finally:
        os.close(descriptor)
    after = _safe_file_metadata(path)
    if _identity(after) != _identity(before):
        raise ValueError
    return payload


def _read_descriptor(descriptor: int, maximum: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(1024 * 1024, maximum + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum:
            raise ValueError


def _safe_directory_metadata(path: Path):
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or _is_reparse(metadata) or path.is_symlink():
        raise ValueError
    return metadata


def _safe_file_metadata(path: Path):
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or _is_reparse(metadata)
        or not 1 <= metadata.st_size <= MAX_SEGMENT_BYTES
    ):
        raise ValueError
    return metadata


def _identity(metadata):
    return metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_size


def _is_reparse(metadata) -> bool:
    return bool(getattr(metadata, "st_file_attributes", 0) & 0x400)


def _flush_windows(handle: int) -> bool:
    kernel = ctypes.windll.kernel32
    kernel.FlushFileBuffers.argtypes = (ctypes.c_void_p,)
    kernel.FlushFileBuffers.restype = ctypes.c_int
    return kernel.FlushFileBuffers(handle) == 1
