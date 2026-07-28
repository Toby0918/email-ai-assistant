"""Shortest-context Windows token SID acquisition and copying."""

from __future__ import annotations

import ctypes

from .windows_handles import _NativeWindowsFailure


_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [
        ("sid", ctypes.c_void_p),
        ("attributes", ctypes.c_uint32),
    ]


class _TokenUser(ctypes.Structure):
    _fields_ = [("user", _SidAndAttributes)]


def current_token_sid(kernel, advapi) -> bytes:
    token = ctypes.c_void_p()
    if not advapi.OpenProcessToken(
        kernel.GetCurrentProcess(),
        _TOKEN_QUERY,
        ctypes.byref(token),
    ):
        raise _NativeWindowsFailure()
    try:
        required = ctypes.c_uint32()
        advapi.GetTokenInformation(
            token,
            _TOKEN_USER,
            None,
            0,
            ctypes.byref(required),
        )
        if required.value == 0:
            raise _NativeWindowsFailure()
        buffer = ctypes.create_string_buffer(required.value)
        if not advapi.GetTokenInformation(
            token,
            _TOKEN_USER,
            buffer,
            required.value,
            ctypes.byref(required),
        ):
            raise _NativeWindowsFailure()
        sid = ctypes.cast(
            buffer,
            ctypes.POINTER(_TokenUser),
        ).contents.user.sid
        return sid_bytes(advapi, sid)
    finally:
        if not kernel.CloseHandle(token):
            raise _NativeWindowsFailure()


def sid_bytes(advapi, sid: ctypes.c_void_p) -> bytes:
    if not sid or not advapi.IsValidSid(sid):
        raise _NativeWindowsFailure()
    length = advapi.GetLengthSid(sid)
    if length <= 0 or length > 1024:
        raise _NativeWindowsFailure()
    return ctypes.string_at(sid, length)
