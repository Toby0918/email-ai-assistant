"""DACL-only native helpers for the fixed incident disposition."""

from __future__ import annotations

import ctypes

from backend.cutover_host_mutation.windows_security import WindowsSecurityApi


_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_SECURITY_INFORMATION = (
    _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION
)


def _temporary_sddl(before_sddl):
    sid = _sid_string(WindowsSecurityApi().current_token_sid())
    dacl = before_sddl.split("D:", 1)[1]
    prefix = dacl.split("(", 1)[0]
    aces = dacl[len(prefix):]
    return f"D:{prefix}{aces}(A;;SD;;;{sid})"


def _set_dacl(handle, sddl):
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = (
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    )
    convert.restype = ctypes.c_int
    get_dacl = advapi.GetSecurityDescriptorDacl
    get_dacl.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_int),
    )
    get_dacl.restype = ctypes.c_int
    setter = advapi.SetSecurityInfo
    setter.argtypes = (
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    )
    setter.restype = ctypes.c_uint32
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    descriptor = ctypes.c_void_p()
    length = ctypes.c_uint32()
    present = ctypes.c_int()
    dacl = ctypes.c_void_p()
    defaulted = ctypes.c_int()
    try:
        if not convert(sddl, 1, ctypes.byref(descriptor), ctypes.byref(length)):
            _fail()
        if not get_dacl(
            descriptor, ctypes.byref(present), ctypes.byref(dacl),
            ctypes.byref(defaulted),
        ) or not present.value or not dacl.value or defaulted.value:
            _fail()
        if setter(handle, 1, _SECURITY_INFORMATION, None, None, dacl, None) != 0:
            _fail()
    finally:
        if descriptor.value:
            kernel.LocalFree(descriptor)


def _capture_dacl_sddl(handle):
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_info = advapi.GetSecurityInfo
    get_info.argtypes = (
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )
    get_info.restype = ctypes.c_uint32
    convert = advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
    convert.argtypes = (
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32),
    )
    convert.restype = ctypes.c_int
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    descriptor = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    text = ctypes.c_void_p()
    length = ctypes.c_uint32()
    try:
        if get_info(
            handle, 1, _DACL_SECURITY_INFORMATION, None, None,
            ctypes.byref(dacl), None, ctypes.byref(descriptor),
        ) != 0:
            _fail()
        if not convert(
            descriptor, 1, _DACL_SECURITY_INFORMATION,
            ctypes.byref(text), ctypes.byref(length),
        ):
            _fail()
        return ctypes.wstring_at(text).rstrip("\x00")
    finally:
        if text.value:
            kernel.LocalFree(text)
        if descriptor.value:
            kernel.LocalFree(descriptor)


def _sid_string(sid_bytes):
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = advapi.ConvertSidToStringSidW
    operation.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
    operation.restype = ctypes.c_int
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    buffer = ctypes.create_string_buffer(sid_bytes)
    text = ctypes.c_void_p()
    try:
        if not operation(buffer, ctypes.byref(text)) or not text.value:
            _fail()
        return ctypes.wstring_at(text)
    finally:
        if text.value:
            kernel.LocalFree(text)


def _fail():
    from .incident_windows import _DaclFailure

    raise _DaclFailure()
