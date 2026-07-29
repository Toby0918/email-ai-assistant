"""One-shot recursive Windows directory-change guard."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from .canonical import fail

_FILE_LIST_DIRECTORY = 0x0001
_SHARE_ALL = 0x0001 | 0x0002 | 0x0004
_OPEN_EXISTING = 3
_BACKUP_SEMANTICS = 0x02000000
_OVERLAPPED_FLAG = 0x40000000
_CHANGE_FILTER = (
    0x0001
    | 0x0002
    | 0x0004
    | 0x0008
    | 0x0040
    | 0x0100
    | 0x0200
    | 0x0400
    | 0x0800
)
_ERROR_IO_PENDING = 997
_ERROR_OPERATION_ABORTED = 995
_ERROR_NOT_FOUND = 1168
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_ERROR = "runtime_tree_changed"


class _Overlapped(ctypes.Structure):
    _fields_ = [
        ("internal", ctypes.c_void_p),
        ("internal_high", ctypes.c_void_p),
        ("offset", ctypes.c_uint32),
        ("offset_high", ctypes.c_uint32),
        ("event", ctypes.c_void_p),
    ]


class WindowsDirectoryChangeGuard:
    """Linearize success against any child mutation after guard creation."""

    __slots__ = (
        "_kernel",
        "_handle",
        "_event",
        "_overlapped",
        "_buffer",
        "_sealed",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("WindowsDirectoryChangeGuard requires open()")

    @classmethod
    def open(cls, target: Path):
        if sys.platform != "win32":
            fail("managed_activation_windows_required")
        guard = object.__new__(cls)
        guard._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        _configure(guard._kernel)
        guard._handle = None
        guard._event = None
        guard._overlapped = _Overlapped()
        guard._buffer = ctypes.create_string_buffer(64 * 1024)
        guard._sealed = False
        try:
            guard._open(target)
            guard._begin()
            return guard
        except Exception:
            guard.close(active_error=True)
            fail(_ERROR)

    def _open(self, target: Path) -> None:
        self._handle = self._kernel.CreateFileW(
            str(target),
            _FILE_LIST_DIRECTORY,
            _SHARE_ALL,
            None,
            _OPEN_EXISTING,
            _BACKUP_SEMANTICS | _OVERLAPPED_FLAG,
            None,
        )
        if self._handle in {None, _INVALID_HANDLE}:
            fail(_ERROR)
        self._event = self._kernel.CreateEventW(None, True, False, None)
        if not self._event:
            fail(_ERROR)
        self._overlapped.event = self._event

    def _begin(self) -> None:
        accepted = self._kernel.ReadDirectoryChangesW(
            self._handle,
            self._buffer,
            len(self._buffer),
            True,
            _CHANGE_FILTER,
            None,
            ctypes.byref(self._overlapped),
            None,
        )
        if not accepted and ctypes.get_last_error() != _ERROR_IO_PENDING:
            fail(_ERROR)

    def seal_unchanged(self) -> None:
        if self._sealed:
            fail(_ERROR)
        self._cancel_and_require_unchanged()
        self._sealed = True

    def _cancel_and_require_unchanged(self) -> None:
        cancelled = self._kernel.CancelIoEx(
            self._handle, ctypes.byref(self._overlapped)
        )
        if not cancelled and ctypes.get_last_error() != _ERROR_NOT_FOUND:
            fail(_ERROR)
        transferred = ctypes.c_uint32()
        completed = self._kernel.GetOverlappedResult(
            self._handle,
            ctypes.byref(self._overlapped),
            ctypes.byref(transferred),
            True,
        )
        if completed or ctypes.get_last_error() != _ERROR_OPERATION_ABORTED:
            fail(_ERROR)

    def close(self, *, active_error: bool) -> None:
        failed = False
        if self._handle and not self._sealed:
            try:
                self._cancel_and_require_unchanged()
            except Exception:
                failed = True
        for handle in (self._handle, self._event):
            if handle and handle != _INVALID_HANDLE:
                if not self._kernel.CloseHandle(handle):
                    failed = True
        self._event = None
        self._handle = None
        if failed and not active_error:
            fail(_ERROR)


def _configure(kernel) -> None:
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
    kernel.CreateEventW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_wchar_p,
    )
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.ReadDirectoryChangesW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(_Overlapped),
        ctypes.c_void_p,
    )
    kernel.ReadDirectoryChangesW.restype = ctypes.c_int
    kernel.CancelIoEx.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(_Overlapped),
    )
    kernel.CancelIoEx.restype = ctypes.c_int
    kernel.GetOverlappedResult.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(_Overlapped),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_int,
    )
    kernel.GetOverlappedResult.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
