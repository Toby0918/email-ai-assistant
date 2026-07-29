"""ctypes signatures for the fixed new-Container ACL effect."""

from __future__ import annotations

import ctypes


def bind_acl_apply(kernel, advapi, explicit_access_type) -> None:
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p
    advapi.CreateWellKnownSid.argtypes = (
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    )
    advapi.CreateWellKnownSid.restype = ctypes.c_int
    advapi.SetEntriesInAclW.argtypes = (
        ctypes.c_uint32,
        ctypes.POINTER(explicit_access_type),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    )
    advapi.SetEntriesInAclW.restype = ctypes.c_uint32
    advapi.SetSecurityInfo.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    advapi.SetSecurityInfo.restype = ctypes.c_uint32
