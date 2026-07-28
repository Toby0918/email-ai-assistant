"""Direct advapi32 capture of token SID and file security descriptors."""
from __future__ import annotations
import ctypes
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .acl_contracts import AclDescriptorObservationV1
from .errors import CutoverHostMutationError
from .roles import AclRole
from .windows_handles import (
    READ_CONTROL,
    NativeObjectIdentity,
    WindowsHandleApi,
    _NativeWindowsFailure,
)
from .windows_security_bindings import bind_security
_OWNER_SECURITY_INFORMATION = 0x00000001
_GROUP_SECURITY_INFORMATION = 0x00000002
_DACL_SECURITY_INFORMATION = 0x00000004
_CAPTURE_INFORMATION = (
    _OWNER_SECURITY_INFORMATION
    | _GROUP_SECURITY_INFORMATION
    | _DACL_SECURITY_INFORMATION
)
_SE_FILE_OBJECT = 1
_SDDL_REVISION_1 = 1
_SE_DACL_PROTECTED = 0x1000
_INHERITED_ACE = 0x10
_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1


class _Acl(ctypes.Structure):
    _fields_ = [
        ("revision", ctypes.c_ubyte),
        ("sbz1", ctypes.c_ubyte),
        ("size", ctypes.c_ushort),
        ("ace_count", ctypes.c_ushort),
        ("sbz2", ctypes.c_ushort),
    ]


class _SecurityDescriptorControl(ctypes.c_ushort):
    pass


class _SidAndAttributes(ctypes.Structure):
    _fields_ = [
        ("sid", ctypes.c_void_p),
        ("attributes", ctypes.c_uint32),
    ]


class _TokenUser(ctypes.Structure):
    _fields_ = [("user", _SidAndAttributes)]


@dataclass(frozen=True, slots=True, repr=False)
class CapturedAce:
    ace_type: int
    ace_flags: int
    access_mask: int
    sid: bytes


@dataclass(frozen=True, slots=True, repr=False)
class CapturedSecurityDescriptor:
    native_identity: NativeObjectIdentity
    observation: AclDescriptorObservationV1
    owner_sid: bytes
    group_sid: bytes
    dacl: bytes
    aces: tuple[CapturedAce, ...]


class WindowsSecurityApi:
    """The exact read-only security API used by descriptor capture."""

    def __init__(self) -> None:
        self._handles = WindowsHandleApi()
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        bind_security(
            self._kernel,
            self._advapi,
            _SecurityDescriptorControl,
        )

    def current_token_sid(self) -> bytes:
        token = ctypes.c_void_p()
        if not self._advapi.OpenProcessToken(
            self._kernel.GetCurrentProcess(),
            _TOKEN_QUERY,
            ctypes.byref(token),
        ):
            raise _NativeWindowsFailure()
        try:
            required = ctypes.c_uint32()
            self._advapi.GetTokenInformation(
                token, _TOKEN_USER, None, 0, ctypes.byref(required)
            )
            if required.value == 0:
                raise _NativeWindowsFailure()
            buffer = ctypes.create_string_buffer(required.value)
            if not self._advapi.GetTokenInformation(
                token,
                _TOKEN_USER,
                buffer,
                required.value,
                ctypes.byref(required),
            ):
                raise _NativeWindowsFailure()
            sid = ctypes.cast(buffer, ctypes.POINTER(_TokenUser)).contents.user.sid
            return self._sid_bytes(sid)
        finally:
            if not self._kernel.CloseHandle(token):
                raise _NativeWindowsFailure()

    def capture(
        self,
        path: Path,
        *,
        role: AclRole,
    ) -> CapturedSecurityDescriptor:
        handle = self._handles.open_existing(path, access=READ_CONTROL)
        descriptor = ctypes.c_void_p()
        try:
            native = self._handles.observe(handle)
            self._handles.require_stable(handle, native, path)
            owner = ctypes.c_void_p()
            group = ctypes.c_void_p()
            dacl = ctypes.c_void_p()
            result = self._advapi.GetSecurityInfo(
                handle,
                _SE_FILE_OBJECT,
                _CAPTURE_INFORMATION,
                ctypes.byref(owner),
                ctypes.byref(group),
                ctypes.byref(dacl),
                None,
                ctypes.byref(descriptor),
            )
            if result != 0 or not descriptor.value or not dacl.value:
                raise _NativeWindowsFailure()
            captured = self._project(
                native=native,
                role=role,
                descriptor=descriptor,
                owner=owner,
                group=group,
                dacl=dacl,
            )
            self._handles.require_stable(handle, native, path)
            return captured
        finally:
            if descriptor.value:
                self._kernel.LocalFree(descriptor)
            self._handles.close(handle)

    def _project(
        self,
        *,
        native: NativeObjectIdentity,
        role: AclRole,
        descriptor: ctypes.c_void_p,
        owner: ctypes.c_void_p,
        group: ctypes.c_void_p,
        dacl: ctypes.c_void_p,
    ) -> CapturedSecurityDescriptor:
        owner_bytes = self._sid_bytes(owner)
        group_bytes = self._sid_bytes(group)
        acl = ctypes.cast(dacl, ctypes.POINTER(_Acl)).contents
        dacl_bytes = ctypes.string_at(dacl, acl.size)
        descriptor_length = self._advapi.GetSecurityDescriptorLength(descriptor)
        if descriptor_length == 0 or acl.ace_count > 4096:
            raise _NativeWindowsFailure()
        descriptor_bytes = ctypes.string_at(descriptor, descriptor_length)
        control = _SecurityDescriptorControl()
        revision = ctypes.c_uint32()
        if not self._advapi.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision)
        ):
            raise _NativeWindowsFailure()
        aces = self._aces(dacl, acl.ace_count)
        inherited_count = sum(
            bool(ace.ace_flags & _INHERITED_ACE) for ace in aces
        )
        sddl = self._canonical_sddl(descriptor)
        observation = _descriptor_observation(
            role=role,
            native=native,
            sddl=sddl,
            descriptor_bytes=descriptor_bytes,
            owner_bytes=owner_bytes,
            group_bytes=group_bytes,
            dacl_bytes=dacl_bytes,
            protected=bool(control.value & _SE_DACL_PROTECTED),
            ace_count=acl.ace_count,
            inherited_count=inherited_count,
        )
        return CapturedSecurityDescriptor(
            native_identity=native,
            observation=observation,
            owner_sid=owner_bytes,
            group_sid=group_bytes,
            dacl=dacl_bytes,
            aces=aces,
        )

    def _sid_bytes(self, sid: ctypes.c_void_p) -> bytes:
        if not sid or not self._advapi.IsValidSid(sid):
            raise _NativeWindowsFailure()
        length = self._advapi.GetLengthSid(sid)
        if length == 0 or length > 1024:
            raise _NativeWindowsFailure()
        return ctypes.string_at(sid, length)

    def _aces(
        self, dacl: ctypes.c_void_p, ace_count: int
    ) -> tuple[CapturedAce, ...]:
        result = []
        for index in range(ace_count):
            ace = ctypes.c_void_p()
            if not self._advapi.GetAce(dacl, index, ctypes.byref(ace)):
                raise _NativeWindowsFailure()
            ace_type = ctypes.c_ubyte.from_address(ace.value).value
            flags = ctypes.c_ubyte.from_address(ace.value + 1).value
            size = ctypes.c_ushort.from_address(ace.value + 2).value
            if size < 8:
                raise _NativeWindowsFailure()
            mask = ctypes.c_uint32.from_address(ace.value + 4).value
            sid = self._sid_bytes(ctypes.c_void_p(ace.value + 8))
            result.append(CapturedAce(ace_type, flags, mask, sid))
        return tuple(result)

    def _canonical_sddl(self, descriptor: ctypes.c_void_p) -> str:
        text = ctypes.c_void_p()
        length = ctypes.c_uint32()
        if not self._advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor,
            _SDDL_REVISION_1,
            _CAPTURE_INFORMATION,
            ctypes.byref(text),
            ctypes.byref(length),
        ):
            raise _NativeWindowsFailure()
        try:
            if not text.value or length.value == 0:
                raise _NativeWindowsFailure()
            return ctypes.wstring_at(text, length.value - 1)
        finally:
            self._kernel.LocalFree(text)


def current_operator_sid_fingerprint() -> str:
    try:
        return _hash_bytes(WindowsSecurityApi().current_token_sid())
    except CutoverHostMutationError:
        raise
    except Exception:
        raise CutoverHostMutationError("acl_descriptor_invalid") from None


def _descriptor_observation(
    *,
    role,
    native,
    sddl,
    descriptor_bytes,
    owner_bytes,
    group_bytes,
    dacl_bytes,
    protected,
    ace_count,
    inherited_count,
):
    return AclDescriptorObservationV1.create(
        role=role,
        object_identity_fingerprint=native.object_identity_fingerprint,
        canonical_sddl_fingerprint=_hash_text(sddl),
        binary_descriptor_fingerprint=_hash_bytes(descriptor_bytes),
        owner_fingerprint=_hash_bytes(owner_bytes),
        group_fingerprint=_hash_bytes(group_bytes),
        dacl_fingerprint=_hash_bytes(dacl_bytes),
        dacl_protected=protected,
        ace_count=ace_count,
        inherited_ace_count=inherited_count,
        complete=True,
        content_observed=False,
    )


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
