"""Cross-platform ancestor-bound opening for reviewed source files."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import MigrationEvidenceError

if os.name == "nt":
    import ctypes
    import msvcrt


_WINDOWS_INVALID_HANDLE = -1
_WINDOWS_GENERIC_READ = 0x80000000
_WINDOWS_READ_ATTRIBUTES = 0x80
_WINDOWS_SHARE_READ = 0x1
_WINDOWS_SHARE_WRITE = 0x2
_WINDOWS_OPEN_EXISTING = 0x3
_WINDOWS_REPARSE_POINT = 0x400
_WINDOWS_DIRECTORY = 0x10
_WINDOWS_OPEN_REPARSE_POINT = 0x00200000
_WINDOWS_BACKUP_SEMANTICS = 0x02000000


if os.name == "nt":
    class _WindowsFileTime(ctypes.Structure):
        _fields_ = (("low", ctypes.c_uint32), ("high", ctypes.c_uint32))


    class _WindowsFileInformation(ctypes.Structure):
        _fields_ = (
            ("attributes", ctypes.c_uint32),
            ("created", _WindowsFileTime),
            ("accessed", _WindowsFileTime),
            ("modified", _WindowsFileTime),
            ("volume", ctypes.c_uint32),
            ("size_high", ctypes.c_uint32),
            ("size_low", ctypes.c_uint32),
            ("links", ctypes.c_uint32),
            ("index_high", ctypes.c_uint32),
            ("index_low", ctypes.c_uint32),
        )


def relative_parts(relative: str) -> tuple[str, ...]:
    """Validate one bounded Git-style relative path."""

    if (
        type(relative) is not str
        or not relative
        or len(relative) > 512
        or "\\" in relative
        or ":" in relative
        or any(ord(character) < 32 for character in relative)
    ):
        _fail()
    parts = tuple(relative.split("/"))
    if any(
        part in {"", ".", ".."} or len(part) > 128
        for part in parts
    ):
        _fail()
    return parts


def open_bound_file(
    root: Path,
    parts: tuple[str, ...],
) -> tuple[int, list[int]]:
    """Open a leaf while retaining non-reparse ancestor handles."""

    if os.name == "nt":
        return _open_windows_bound_file(root, parts)
    return _open_posix_bound_file(root, parts)


def close_guards(guards: list[int]) -> None:
    """Release ancestor handles in reverse order."""

    if os.name == "nt":
        _close_windows_guards(guards)
    else:
        _close_posix_guards(guards)


def _open_posix_bound_file(
    root: Path,
    parts: tuple[str, ...],
) -> tuple[int, list[int]]:
    guards: list[int] = []
    try:
        current = os.open(
            root,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        guards.append(current)
        for part in parts[:-1]:
            current = os.open(
                part,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current,
            )
            guards.append(current)
        descriptor = os.open(
            parts[-1],
            _read_flags(),
            dir_fd=current,
        )
        return descriptor, guards
    except Exception:
        _close_posix_guards(guards)
        raise


def _open_windows_bound_file(
    root: Path,
    parts: tuple[str, ...],
) -> tuple[int, list[int]]:
    guards: list[int] = []
    final_handle = _WINDOWS_INVALID_HANDLE
    try:
        current = root
        guards.append(_open_windows_path(current, directory=True))
        for part in parts[:-1]:
            current /= part
            guards.append(_open_windows_path(current, directory=True))
        final_handle = _open_windows_path(
            current / parts[-1],
            directory=False,
        )
        descriptor = msvcrt.open_osfhandle(
            final_handle,
            os.O_RDONLY | getattr(os, "O_BINARY", 0),
        )
        final_handle = _WINDOWS_INVALID_HANDLE
        return descriptor, guards
    except Exception:
        if final_handle != _WINDOWS_INVALID_HANDLE:
            _close_windows_handle(final_handle)
        _close_windows_guards(guards)
        raise


def _open_windows_path(path: Path, *, directory: bool) -> int:
    kernel = _windows_kernel()
    access = (
        _WINDOWS_READ_ATTRIBUTES
        if directory
        else _WINDOWS_GENERIC_READ
    )
    share = _WINDOWS_SHARE_READ | (
        _WINDOWS_SHARE_WRITE if directory else 0
    )
    flags = _WINDOWS_OPEN_REPARSE_POINT | (
        _WINDOWS_BACKUP_SEMANTICS if directory else 0
    )
    handle = kernel.CreateFileW(
        str(path),
        access,
        share,
        None,
        _WINDOWS_OPEN_EXISTING,
        flags,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        _fail()
    _require_windows_handle_type(
        kernel,
        handle,
        directory=directory,
    )
    return handle


def _windows_kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandle.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(_WindowsFileInformation),
    )
    kernel.GetFileInformationByHandle.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    return kernel


def _require_windows_handle_type(
    kernel,
    handle: int,
    *,
    directory: bool,
) -> None:
    information = _WindowsFileInformation()
    if not kernel.GetFileInformationByHandle(
        handle,
        ctypes.byref(information),
    ):
        _close_windows_handle(handle)
        _fail()
    attributes = information.attributes
    if (
        attributes & _WINDOWS_REPARSE_POINT
        or bool(attributes & _WINDOWS_DIRECTORY) is not directory
        or (not directory and information.links != 1)
    ):
        _close_windows_handle(handle)
        _fail()


def _close_posix_guards(guards: list[int]) -> None:
    for descriptor in reversed(guards):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _close_windows_guards(guards: list[int]) -> None:
    for handle in reversed(guards):
        _close_windows_handle(handle)


def _close_windows_handle(handle: int) -> None:
    try:
        _windows_kernel().CloseHandle(handle)
    except Exception:
        pass


def _read_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _fail() -> None:
    raise MigrationEvidenceError("migration_evidence_create_failed")
