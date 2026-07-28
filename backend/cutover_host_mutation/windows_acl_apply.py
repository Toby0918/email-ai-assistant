"""Direct Windows API application of the exact new-Container DACL."""

from __future__ import annotations

import ctypes
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from .errors import CutoverHostMutationError
from .roles import AclRole
from .windows_acl_apply_bindings import bind_acl_apply
from .windows_handles import (
    WindowsHandleApi,
    _NativeWindowsFailure,
)
from .windows_security import (
    CapturedSecurityDescriptor,
    WindowsSecurityApi,
)


_OWNER_SECURITY_INFORMATION = 0x00000001
_GROUP_SECURITY_INFORMATION = 0x00000002
_DACL_SECURITY_INFORMATION = 0x00000004
_SACL_SECURITY_INFORMATION = 0x00000008
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_APPLY_SECURITY_INFORMATION = (
    _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION
)

_SE_FILE_OBJECT = 1
_SET_ACCESS = 2
_TRUSTEE_IS_SID = 0
_TRUSTEE_IS_UNKNOWN = 0
_OBJECT_INHERIT_ACE = 0x01
_CONTAINER_INHERIT_ACE = 0x02
_INHERITED_ACE = 0x10
_ACCESS_ALLOWED_ACE_TYPE = 0
_FILE_ALL_ACCESS = 0x001F01FF
_WIN_LOCAL_SYSTEM_SID = 22
_WIN_BUILTIN_ADMINISTRATORS_SID = 26
_SECURITY_MAX_SID_SIZE = 68


class _TrusteeW(ctypes.Structure):
    _fields_ = [
        ("multiple_trustee", ctypes.c_void_p),
        ("multiple_trustee_operation", ctypes.c_int),
        ("trustee_form", ctypes.c_int),
        ("trustee_type", ctypes.c_int),
        ("name", ctypes.c_void_p),
    ]


class _ExplicitAccessW(ctypes.Structure):
    _fields_ = [
        ("access_permissions", ctypes.c_uint32),
        ("access_mode", ctypes.c_int),
        ("inheritance", ctypes.c_uint32),
        ("trustee", _TrusteeW),
    ]


@dataclass(frozen=True, slots=True, repr=False)
class AppliedAclProof:
    before: CapturedSecurityDescriptor
    after: CapturedSecurityDescriptor
    principal_sids: tuple[bytes, ...]


class WindowsAclWriter:
    """Apply only the code-fixed DACL to one verified empty directory."""

    def __init__(self) -> None:
        self._handles = WindowsHandleApi()
        self._security = WindowsSecurityApi()
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        bind_acl_apply(self._kernel, self._advapi, _ExplicitAccessW)

    def apply_new_container(
        self,
        path: Path,
        *,
        expected_identity: str,
        expected_parent_identity: str,
        parent_path: Path,
        operator_sid: bytes,
        resource,
        child_race_barrier,
    ) -> AppliedAclProof:
        _root, _marker, parent_handle, target_handle = resource.snapshot()
        parent = self._handles.observe(parent_handle)
        if parent.object_identity_fingerprint != expected_parent_identity:
            _fail("acl_identity_changed")
        self._handles.require_stable(parent_handle, parent, parent_path)
        before = self._security.capture_handle(
            target_handle,
            path=path,
            role=AclRole.PROJECT_CONTAINER,
        )
        if before.observation.object_identity_fingerprint != expected_identity:
            _fail("acl_identity_changed")
        _require_empty(path)
        principals = self._apply_handle_effect(
            target_handle,
            path=path,
            before=before,
            operator_sid=operator_sid,
            child_race_barrier=child_race_barrier,
        )
        after = self._security.capture_handle(
            target_handle,
            path=path,
            role=AclRole.PROJECT_CONTAINER,
        )
        self._handles.require_stable(parent_handle, parent, parent_path)
        _validate_after(before, after, expected_identity, principals)
        return AppliedAclProof(before, after, principals)

    def _apply_handle_effect(
        self,
        handle: int,
        path: Path,
        *,
        before: CapturedSecurityDescriptor,
        operator_sid: bytes,
        child_race_barrier,
    ) -> tuple[bytes, ...]:
        acl = ctypes.c_void_p()
        try:
            self._handles.require_stable(
                handle,
                before.native_identity,
                path,
            )
            _require_empty(path)
            principals, buffers = self._principal_sids(operator_sid)
            entries = self._entries(buffers)
            result = self._advapi.SetEntriesInAclW(
                len(entries),
                entries,
                None,
                ctypes.byref(acl),
            )
            if result != 0 or not acl.value:
                raise _NativeWindowsFailure()
            _run_child_race_barrier(child_race_barrier)
            result = self._advapi.SetSecurityInfo(
                handle,
                _SE_FILE_OBJECT,
                _APPLY_SECURITY_INFORMATION,
                None,
                None,
                acl,
                None,
            )
            if result != 0:
                raise _NativeWindowsFailure()
            self._handles.require_stable(
                handle,
                before.native_identity,
                path,
            )
            return principals
        finally:
            if acl.value:
                self._kernel.LocalFree(acl)

    def _principal_sids(
        self, operator_sid: bytes
    ) -> tuple[tuple[bytes, ...], tuple[ctypes.Array, ...]]:
        system = self._well_known_sid(_WIN_LOCAL_SYSTEM_SID)
        administrators = self._well_known_sid(
            _WIN_BUILTIN_ADMINISTRATORS_SID
        )
        principals = (operator_sid, system, administrators)
        buffers = tuple(ctypes.create_string_buffer(sid) for sid in principals)
        return principals, buffers

    def _well_known_sid(self, sid_type: int) -> bytes:
        size = ctypes.c_uint32(_SECURITY_MAX_SID_SIZE)
        buffer = ctypes.create_string_buffer(size.value)
        if not self._advapi.CreateWellKnownSid(
            sid_type, None, buffer, ctypes.byref(size)
        ):
            raise _NativeWindowsFailure()
        return bytes(buffer.raw[: size.value])

    def _entries(
        self, buffers: tuple[ctypes.Array, ...]
    ) -> ctypes.Array:
        entries = (_ExplicitAccessW * len(buffers))()
        for index, buffer in enumerate(buffers):
            entries[index] = _ExplicitAccessW(
                access_permissions=_FILE_ALL_ACCESS,
                access_mode=_SET_ACCESS,
                inheritance=_OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE,
                trustee=_TrusteeW(
                    multiple_trustee=None,
                    multiple_trustee_operation=0,
                    trustee_form=_TRUSTEE_IS_SID,
                    trustee_type=_TRUSTEE_IS_UNKNOWN,
                    name=ctypes.cast(buffer, ctypes.c_void_p),
                ),
            )
        return entries


def exact_container_policy(
    capture: CapturedSecurityDescriptor,
    principal_sids: tuple[bytes, ...],
) -> bool:
    return (
        capture.observation.dacl_protected
        and capture.observation.ace_count == 3
        and capture.observation.inherited_ace_count == 0
        and _exact_aces(capture, principal_sids, inherited=False)
    )


def _validate_after(before, after, expected_identity, principals) -> None:
    if (
        before.owner_sid != after.owner_sid
        or before.group_sid != after.group_sid
        or after.observation.object_identity_fingerprint != expected_identity
        or not exact_container_policy(after, principals)
    ):
        _fail("acl_policy_rejected")


def exact_inherited_policy(
    capture: CapturedSecurityDescriptor,
    principal_sids: tuple[bytes, ...],
) -> bool:
    return (
        not capture.observation.dacl_protected
        and capture.observation.ace_count == 3
        and capture.observation.inherited_ace_count == 3
        and _exact_aces(capture, principal_sids, inherited=True)
    )


def _exact_aces(
    capture: CapturedSecurityDescriptor,
    principal_sids: tuple[bytes, ...],
    *,
    inherited: bool,
) -> bool:
    expected_flags = _OBJECT_INHERIT_ACE | _CONTAINER_INHERIT_ACE
    if inherited:
        expected_flags |= _INHERITED_ACE
    return (
        {ace.sid for ace in capture.aces} == set(principal_sids)
        and all(
            ace.ace_type == _ACCESS_ALLOWED_ACE_TYPE
            and ace.ace_flags == expected_flags
            and ace.access_mask == _FILE_ALL_ACCESS
            for ace in capture.aces
        )
    )


def _require_empty(path: Path) -> None:
    try:
        with os.scandir(path) as entries:
            if next(entries, None) is not None:
                _fail("acl_policy_rejected")
    except CutoverHostMutationError:
        raise
    except OSError:
        _fail("acl_descriptor_invalid")


def _run_child_race_barrier(barrier) -> None:
    if barrier is None:
        return
    try:
        barrier.wait(timeout=5)
        barrier.wait(timeout=5)
    except threading.BrokenBarrierError:
        _fail("acl_policy_rejected")


def _fail(code: str) -> None:
    raise CutoverHostMutationError(code) from None
