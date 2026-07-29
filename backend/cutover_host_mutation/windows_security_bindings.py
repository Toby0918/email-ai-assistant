"""ctypes signatures for read-only Windows security capture."""

from __future__ import annotations

import ctypes


def bind_security(kernel, advapi, control_type) -> None:
    _bind_kernel(kernel)
    _bind_token(advapi)
    _bind_descriptor(advapi, control_type)
    _bind_acl(advapi)


def _bind_kernel(kernel) -> None:
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p


def _bind_token(advapi) -> None:
    advapi.OpenProcessToken.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi.OpenProcessToken.restype = ctypes.c_int
    advapi.GetTokenInformation.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    )
    advapi.GetTokenInformation.restype = ctypes.c_int


def _bind_descriptor(advapi, control_type) -> None:
    advapi.GetSecurityInfo.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi.GetSecurityInfo.restype = ctypes.c_uint32
    advapi.GetSecurityDescriptorLength.argtypes = (ctypes.c_void_p,)
    advapi.GetSecurityDescriptorLength.restype = ctypes.c_uint32
    advapi.GetSecurityDescriptorControl.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(control_type),
        ctypes.POINTER(ctypes.c_uint32),
    )
    advapi.GetSecurityDescriptorControl.restype = ctypes.c_int


def _bind_acl(advapi) -> None:
    advapi.IsValidSid.argtypes = (ctypes.c_void_p,)
    advapi.IsValidSid.restype = ctypes.c_int
    advapi.GetLengthSid.argtypes = (ctypes.c_void_p,)
    advapi.GetLengthSid.restype = ctypes.c_uint32
    advapi.GetAce.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi.GetAce.restype = ctypes.c_int
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32),
    )
    advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = (
        ctypes.c_int
    )
