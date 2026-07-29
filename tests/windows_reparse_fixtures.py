"""Direct Win32 creation of test-owned directory junctions."""

from __future__ import annotations

import ctypes
import struct
from pathlib import Path


_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_FILE_SHARE_ALL = 0x7
_OPEN_REPARSE_DIRECTORY = 0x02200000
_FSCTL_SET_REPARSE_POINT = 0x000900A4
_MOUNT_POINT_TAG = 0xA0000003
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


def create_test_junction(link: Path, target: Path) -> None:
    """Create a junction without a shell or replayable command transcript."""
    link.mkdir()
    substitute = ("\\??\\" + str(target)).encode("utf-16-le")
    print_name = str(target).encode("utf-16-le")
    path_buffer = substitute + b"\0\0" + print_name + b"\0\0"
    payload = struct.pack(
        "<HHHH",
        0,
        len(substitute),
        len(substitute) + 2,
        len(print_name),
    ) + path_buffer
    reparse_buffer = struct.pack(
        "<IHH",
        _MOUNT_POINT_TAG,
        len(payload),
        0,
    ) + payload
    kernel = _kernel32()
    handle = kernel.CreateFileW(
        str(link),
        _GENERIC_WRITE,
        _FILE_SHARE_ALL,
        None,
        _OPEN_EXISTING,
        _OPEN_REPARSE_DIRECTORY,
        None,
    )
    if handle is None or handle == _INVALID_HANDLE_VALUE:
        raise OSError("test junction handle unavailable")
    try:
        returned = ctypes.c_uint32()
        buffer = ctypes.create_string_buffer(reparse_buffer)
        if not kernel.DeviceIoControl(
            handle,
            _FSCTL_SET_REPARSE_POINT,
            buffer,
            len(reparse_buffer),
            None,
            0,
            ctypes.byref(returned),
            None,
        ):
            raise OSError("test junction creation failed")
    finally:
        kernel.CloseHandle(handle)


def _kernel32():
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
    kernel.DeviceIoControl.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    )
    kernel.DeviceIoControl.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    return kernel
