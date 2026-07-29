"""Direct advapi32 capture of token SID and file security descriptors."""
from __future__ import annotations
import ctypes
from dataclasses import dataclass
from pathlib import Path

from backend.real_host_preflight.windows_paths import expected_final_path

from .acl_contracts import AclDescriptorObservationV1
from .errors import CutoverHostMutationError
from .roles import AclRole
from .windows_handles import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    READ_CONTROL,
    NativeObjectIdentity,
    WindowsHandleApi,
    _NativeWindowsFailure,
)
from .windows_security_bindings import bind_security
from .windows_security_projection import (
    descriptor_observation,
    hash_bytes,
)
from .windows_sid import current_token_sid, sid_bytes
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
        return current_token_sid(self._kernel, self._advapi)

    def capture(
        self,
        path: Path,
        *,
        role: AclRole,
        _allow_reparse: bool = False,
    ) -> CapturedSecurityDescriptor:
        handle = self._handles.open_existing(path, access=READ_CONTROL)
        try:
            return self.capture_handle(
                handle,
                path=path,
                role=role,
                _allow_reparse=_allow_reparse,
            )
        finally:
            self._handles.close(handle)

    def capture_handle(
        self,
        handle: int,
        *,
        path: Path,
        role: AclRole,
        _allow_reparse: bool = False,
    ) -> CapturedSecurityDescriptor:
        descriptor = ctypes.c_void_p()
        try:
            native = self._handles.observe(handle)
            _require_capture_stable(
                self._handles,
                handle,
                native,
                path,
                allow_reparse=_allow_reparse,
            )
            owner, group, dacl = _security_info(
                self._advapi,
                handle,
                descriptor,
            )
            captured = self._project(
                native=native,
                role=role,
                descriptor=descriptor,
                owner=owner,
                group=group,
                dacl=dacl,
            )
            _require_capture_stable(
                self._handles,
                handle,
                native,
                path,
                allow_reparse=_allow_reparse,
            )
            return captured
        finally:
            if descriptor.value:
                self._kernel.LocalFree(descriptor)

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
        owner_bytes = sid_bytes(self._advapi, owner)
        group_bytes = sid_bytes(self._advapi, group)
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
        observation = descriptor_observation(
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
            sid = sid_bytes(
                self._advapi,
                ctypes.c_void_p(ace.value + 8),
            )
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
        return hash_bytes(WindowsSecurityApi().current_token_sid())
    except CutoverHostMutationError:
        raise
    except Exception:
        raise CutoverHostMutationError("acl_descriptor_invalid") from None


def _require_capture_stable(
    handles, handle, expected, path, *, allow_reparse
) -> None:
    current = handles.observe(handle)
    if (
        current != expected
        or current.filesystem_name != "NTFS"
        or current.drive_type != "fixed"
        or (
            not allow_reparse
            and current.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        )
        or current.normalized_path.casefold()
        != expected_final_path(path).casefold()
    ):
        raise CutoverHostMutationError("acl_identity_changed") from None


def _security_info(advapi, handle, descriptor):
    owner = ctypes.c_void_p()
    group = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    result = advapi.GetSecurityInfo(
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
    return owner, group, dacl
