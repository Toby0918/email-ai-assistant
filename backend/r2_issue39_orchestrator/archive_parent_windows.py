"""Fixed create-only archive hierarchy for Issue 39 incident retention."""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass, field

from backend.cutover_host_mutation.windows_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WindowsHandleApi,
)
from backend.real_host_preflight.windows_paths import expected_final_path

from .incident_binding import _IncidentBinding, _fixed_incident_binding
from .incident_security import _capture_dacl_sddl, _sid_string
from .archive_parent_native import SecurityDescriptor, create_directory


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39ArchiveParentReadinessV1:
    state: str
    readiness_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39ArchiveParentReadinessV1 is observer-owned")


@dataclass(slots=True, repr=False)
class _ArchiveParentLease:
    api: object = field(repr=False)
    handles: list[int] = field(repr=False)
    paths: tuple[object, ...] = field(repr=False)
    sddl: str = field(repr=False)

    @property
    def parent_handle(self):
        return self.handles[-1]

    def close(self):
        while self.handles:
            handle = self.handles.pop()
            try:
                self.api.close(handle)
            except Exception:
                pass


def provision_fixed_archive_parent_v1() -> bool:
    """Provision only the code-fixed archive parent; accept no caller input."""

    return _provision_archive_parent_v1(_fixed_incident_binding())


def observe_fixed_archive_parent_readiness_v1():
    """Observe only the code-fixed archive hierarchy; accept no caller input."""

    return _observe_archive_parent_readiness_v1(_fixed_incident_binding())


def _observe_archive_parent_readiness_v1(binding):
    if sys.platform != "win32" or not _valid_binding(binding):
        return _allocate_readiness("BLOCKED", "0" * 64)
    api = WindowsHandleApi()
    handles = []
    try:
        sddl = _expected_archive_parent_sddl()
        _open_anchor(api, binding, handles)
        identities = [api.observe(handles[0]).object_identity_fingerprint]
        current = binding.archive_anchor
        missing = False
        presence = []
        for component in binding.archive_components:
            current /= component
            if missing or not os.path.lexists(current):
                missing = True
                presence.append(0)
                continue
            handle = api.open_existing(
                current,
                access=READ_CONTROL | FILE_READ_ATTRIBUTES,
            )
            handles.append(handle)
            observed = api.observe(handle)
            _require_identity(api, handle, observed, current, sddl)
            identities.append(observed.object_identity_fingerprint)
            presence.append(1)
        state = "PROVISIONABLE" if missing else "READY"
        return _allocate_readiness(
            state, _parent_fingerprint(state, sddl, presence, identities)
        )
    except Exception:
        return _allocate_readiness("BLOCKED", "0" * 64)
    finally:
        for handle in reversed(handles):
            try:
                api.close(handle)
            except Exception:
                pass


def _parent_fingerprint(state, sddl, presence, identities):
    digest = hashlib.sha256(b"r2-issue39-archive-parent-readiness-v1\0")
    digest.update(state.encode("ascii") + b"\0")
    digest.update(hashlib.sha256(sddl.encode("ascii")).digest())
    digest.update(bytes(presence))
    for identity in identities:
        digest.update(bytes.fromhex(identity))
    return digest.hexdigest()


def _allocate_readiness(state, fingerprint):
    value = object.__new__(Issue39ArchiveParentReadinessV1)
    object.__setattr__(value, "state", state)
    object.__setattr__(value, "readiness_fingerprint", fingerprint)
    return value


def _provision_archive_parent_v1(binding, *, expected=None) -> bool:
    if sys.platform != "win32" or not _valid_binding(binding):
        return False
    lease = None
    try:
        if expected is None:
            expected = _observe_archive_parent_readiness_v1(binding)
        lease = _acquire_archive_parent_v1(binding, expected)
        return True
    except Exception:
        return False
    finally:
        if lease is not None:
            lease.close()


def _acquire_archive_parent_v1(binding, expected):
    if (
        sys.platform != "win32"
        or not _valid_binding(binding)
        or type(expected) is not Issue39ArchiveParentReadinessV1
        or expected.state not in {"PROVISIONABLE", "READY"}
    ):
        raise _ArchiveParentFailure()
    api = WindowsHandleApi()
    handles = []
    try:
        sddl = _expected_archive_parent_sddl()
        presence, identities, paths = _open_archive_prefix(
            api, binding, handles, sddl
        )
        _require_expected_snapshot(expected, sddl, presence, identities)
        _create_missing_archive_components(binding, handles, presence, sddl)
        if not _complete_chain_matches(api, binding, handles, sddl):
            raise _ArchiveParentFailure()
        lease = _ArchiveParentLease(api, handles, tuple(paths), sddl)
        handles = []
        return lease
    except Exception:
        for handle in reversed(handles):
            try:
                api.close(handle)
            except Exception:
                pass
        raise


def _open_archive_prefix(api, binding, handles, sddl):
    _open_anchor(api, binding, handles)
    identities = [api.observe(handles[0]).object_identity_fingerprint]
    paths = [binding.archive_anchor]
    presence = []
    missing = False
    current_path = binding.archive_anchor
    for component in binding.archive_components:
        current_path /= component
        paths.append(current_path)
        if missing or not os.path.lexists(current_path):
            missing = True
            presence.append(0)
            continue
        handle = api.open_existing(
            current_path,
            access=READ_CONTROL | FILE_READ_ATTRIBUTES,
        )
        handles.append(handle)
        observed = api.observe(handle)
        _require_identity(api, handle, observed, current_path, sddl)
        identities.append(observed.object_identity_fingerprint)
        presence.append(1)
    return presence, identities, paths


def _require_expected_snapshot(expected, sddl, presence, identities):
    state = "PROVISIONABLE" if 0 in presence else "READY"
    fingerprint = _parent_fingerprint(state, sddl, presence, identities)
    if state != expected.state or fingerprint != expected.readiness_fingerprint:
        raise _ArchiveParentFailure()


def _create_missing_archive_components(binding, handles, presence, sddl):
    if 0 not in presence:
        return
    descriptor = SecurityDescriptor(sddl)
    try:
        parent = handles[-1]
        for component in binding.archive_components[presence.index(0):]:
            child = create_directory(parent, component, descriptor.pointer)
            handles.append(child)
            parent = child
    finally:
        descriptor.close()


def _valid_binding(binding) -> bool:
    return (
        type(binding) is _IncidentBinding
        and type(binding.archive_components) is tuple
        and binding.archive_components
        and all(type(item) is str and item for item in binding.archive_components)
        and binding.destination.parent
        == binding.archive_anchor.joinpath(*binding.archive_components)
    )


def _open_anchor(api, binding, handles):
    handle = api.open_existing(binding.archive_anchor, access=FILE_READ_ATTRIBUTES)
    handles.append(handle)
    observed = api.observe(handle)
    _require_identity(api, handle, observed, binding.archive_anchor, None)
    return handle


def _require_identity(api, handle, observed, path, sddl):
    if (
        not observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or observed.drive_type != "fixed"
        or observed.normalized_path.casefold()
        != expected_final_path(path).casefold()
        or sddl is not None and _capture_dacl_sddl(handle) != sddl
    ):
        raise _ArchiveParentFailure()
    api.require_stable(handle, observed, path)


def _revalidate_archive_parent_lease(lease, binding):
    if (
        type(lease) is not _ArchiveParentLease
        or not _valid_binding(binding)
        or len(lease.handles) != len(lease.paths)
    ):
        raise _ArchiveParentFailure()
    volume = None
    for index, (handle, path) in enumerate(zip(lease.handles, lease.paths, strict=True)):
        observed = lease.api.observe(handle)
        _require_identity(
            lease.api,
            handle,
            observed,
            path,
            None if index == 0 else lease.sddl,
        )
        volume = observed.volume_serial_number if volume is None else volume
        if observed.volume_serial_number != volume:
            raise _ArchiveParentFailure()


def _complete_chain_matches(api, binding, handles, sddl):
    paths = [binding.archive_anchor]
    current = binding.archive_anchor
    for component in binding.archive_components:
        current /= component
        paths.append(current)
    if len(paths) != len(handles):
        return False
    volume = None
    for index, (handle, path) in enumerate(zip(handles, paths, strict=True)):
        observed = api.observe(handle)
        _require_identity(api, handle, observed, path, None if index == 0 else sddl)
        volume = observed.volume_serial_number if volume is None else volume
        if observed.volume_serial_number != volume:
            return False
    return True


def _expected_archive_parent_sddl() -> str:
    from backend.cutover_host_mutation.windows_security import WindowsSecurityApi

    operator = _sid_string(WindowsSecurityApi().current_token_sid())
    return f"D:P(A;OICI;FA;;;{operator})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)"


class _ArchiveParentFailure(Exception):
    pass
