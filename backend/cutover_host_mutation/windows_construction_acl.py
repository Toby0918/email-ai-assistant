"""Protected construction DACL for the empty new Container."""

from __future__ import annotations

import ctypes
import hashlib
from dataclasses import dataclass

from .errors import CutoverHostMutationError
from .windows_handles import (
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WRITE_DAC,
    _NativeWindowsFailure,
)
from .windows_security import WindowsSecurityApi


_ACL_REVISION = 2
_SECURITY_DESCRIPTOR_REVISION = 1
_SE_DACL_PROTECTED = 0x1000
_FILE_LIST_DIRECTORY = 0x00000001
_FILE_TRAVERSE = 0x00000020
_SYNCHRONIZE = 0x00100000
_GUARD_ACCESS = (
    _FILE_LIST_DIRECTORY
    | _FILE_TRAVERSE
    | FILE_READ_ATTRIBUTES
    | READ_CONTROL
    | WRITE_DAC
    | _SYNCHRONIZE
)
_ACL_HEADER_BYTES = 8
_ACCESS_ALLOWED_ACE_FIXED_BYTES = 8
_SECURITY_DESCRIPTOR_BYTES = 64


@dataclass(frozen=True, slots=True, repr=False)
class ConstructionSecurityDescriptor:
    descriptor: ctypes.Array
    acl: ctypes.Array
    sid: ctypes.Array

    @property
    def pointer(self) -> ctypes.c_void_p:
        return ctypes.cast(self.descriptor, ctypes.c_void_p)


def guarded_descriptor(
    expected_operator_fingerprint: str,
) -> ConstructionSecurityDescriptor:
    sid = WindowsSecurityApi().current_token_sid()
    if (
        hashlib.sha256(sid).hexdigest()
        != expected_operator_fingerprint
    ):
        raise CutoverHostMutationError("filesystem_authorization_rejected")
    try:
        return _build_descriptor(sid)
    except _NativeWindowsFailure:
        raise
    except Exception:
        raise _NativeWindowsFailure() from None


def _build_descriptor(sid_bytes: bytes) -> ConstructionSecurityDescriptor:
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    _bind(advapi)
    sid = ctypes.create_string_buffer(sid_bytes)
    sid_length = advapi.GetLengthSid(sid)
    if sid_length == 0:
        raise _NativeWindowsFailure()
    acl = ctypes.create_string_buffer(
        _ACL_HEADER_BYTES + _ACCESS_ALLOWED_ACE_FIXED_BYTES + sid_length
    )
    descriptor = ctypes.create_string_buffer(_SECURITY_DESCRIPTOR_BYTES)
    _initialize(advapi, descriptor, acl, sid)
    return ConstructionSecurityDescriptor(descriptor, acl, sid)


def _initialize(advapi, descriptor, acl, sid) -> None:
    if not advapi.InitializeSecurityDescriptor(
        descriptor,
        _SECURITY_DESCRIPTOR_REVISION,
    ):
        raise _NativeWindowsFailure()
    if not advapi.InitializeAcl(
        acl,
        ctypes.sizeof(acl),
        _ACL_REVISION,
    ):
        raise _NativeWindowsFailure()
    if not advapi.AddAccessAllowedAceEx(
        acl,
        _ACL_REVISION,
        0,
        _GUARD_ACCESS,
        sid,
    ):
        raise _NativeWindowsFailure()
    if not advapi.SetSecurityDescriptorDacl(
        descriptor,
        1,
        acl,
        0,
    ):
        raise _NativeWindowsFailure()
    if not advapi.SetSecurityDescriptorControl(
        descriptor,
        _SE_DACL_PROTECTED,
        _SE_DACL_PROTECTED,
    ):
        raise _NativeWindowsFailure()


def _bind(advapi) -> None:
    advapi.GetLengthSid.argtypes = (ctypes.c_void_p,)
    advapi.GetLengthSid.restype = ctypes.c_uint32
    advapi.InitializeSecurityDescriptor.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    advapi.InitializeSecurityDescriptor.restype = ctypes.c_int
    advapi.InitializeAcl.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    )
    advapi.InitializeAcl.restype = ctypes.c_int
    advapi.AddAccessAllowedAceEx.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    advapi.AddAccessAllowedAceEx.restype = ctypes.c_int
    advapi.SetSecurityDescriptorDacl.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    )
    advapi.SetSecurityDescriptorDacl.restype = ctypes.c_int
    advapi.SetSecurityDescriptorControl.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint16,
        ctypes.c_uint16,
    )
    advapi.SetSecurityDescriptorControl.restype = ctypes.c_int
