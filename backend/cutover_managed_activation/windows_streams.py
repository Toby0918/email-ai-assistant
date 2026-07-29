"""Reject alternate data streams from synthetic Runtime trees."""

from __future__ import annotations

import ctypes
import sys

from .canonical import fail

_ERROR_HANDLE_EOF = 38
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _FindStreamData(ctypes.Structure):
    _fields_ = [
        ("stream_size", ctypes.c_int64),
        ("stream_name", ctypes.c_wchar * 296),
    ]


class WindowsStreamApi:
    """Enumerate streams without exposing names or native errors."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            fail("managed_activation_windows_required")
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        _configure(self._kernel)

    def require_default_only(self, path) -> None:
        data = _FindStreamData()
        handle = self._kernel.FindFirstStreamW(
            str(path), 0, ctypes.byref(data), 0
        )
        if handle is None or handle == _INVALID_HANDLE:
            if ctypes.get_last_error() == _ERROR_HANDLE_EOF:
                return
            fail("runtime_tree_invalid")
        names = []
        try:
            names.append(data.stream_name)
            while self._kernel.FindNextStreamW(handle, ctypes.byref(data)):
                names.append(data.stream_name)
            if ctypes.get_last_error() != _ERROR_HANDLE_EOF:
                fail("runtime_tree_invalid")
        finally:
            if not self._kernel.FindClose(handle):
                fail("runtime_tree_invalid")
        if names not in ([], ["::$DATA"]):
            fail("runtime_tree_invalid")


def _configure(kernel) -> None:
    kernel.FindFirstStreamW.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.POINTER(_FindStreamData),
        ctypes.c_uint32,
    )
    kernel.FindFirstStreamW.restype = ctypes.c_void_p
    kernel.FindNextStreamW.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(_FindStreamData),
    )
    kernel.FindNextStreamW.restype = ctypes.c_int
    kernel.FindClose.argtypes = (ctypes.c_void_p,)
    kernel.FindClose.restype = ctypes.c_int
