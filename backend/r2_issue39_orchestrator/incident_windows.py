"""DACL-safe no-replace disposition of the exact retained closure stage."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from backend.cutover_host_mutation.windows_handles import (
    DELETE_ACCESS,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WRITE_DAC,
    WindowsHandleApi,
)
from .incident_binding import _IncidentBinding, _fixed_incident_binding
from .incident_contracts import (
    IncidentDispositionResultV1,
    IncidentDispositionStatusV1,
)
from .durable_io import guard_directory, read_segment
from .incident_security import _capture_dacl_sddl, _set_dacl, _temporary_sddl


_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_SECURITY_INFORMATION = (
    _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION
)


def dispose_fixed_incident_stage_v1():
    """Archive only the code-fixed incident stage; accept no caller input."""

    return _dispose_incident_stage_v1(_fixed_incident_binding())


def _dispose_incident_stage_v1(binding):
    if sys.platform != "win32" or type(binding) is not _IncidentBinding:
        return _result(IncidentDispositionStatusV1.INCIDENT_STOP)
    if not os.path.lexists(binding.source):
        return _result(IncidentDispositionStatusV1.ABSENT)
    if os.path.lexists(binding.destination):
        return _result(IncidentDispositionStatusV1.BLOCKED_DESTINATION)
    try:
        _require_artifacts(binding)
    except Exception:
        return _result(IncidentDispositionStatusV1.BLOCKED_ARTIFACT)
    try:
        _move_with_restored_dacl(binding)
        _require_artifacts(binding, destination=True)
        return _result(
            IncidentDispositionStatusV1.ARCHIVED,
            artifacts=2,
            moves=1,
        )
    except _DaclFailure:
        return _result(IncidentDispositionStatusV1.BLOCKED_DACL)
    except _DestinationFailure:
        return _result(IncidentDispositionStatusV1.BLOCKED_DESTINATION)
    except Exception:
        return _result(IncidentDispositionStatusV1.INCIDENT_STOP)


def _move_with_restored_dacl(binding):
    api = WindowsHandleApi()
    handles = []
    try:
        security_handle = api.open_existing(
            binding.source,
            access=READ_CONTROL | WRITE_DAC | FILE_READ_ATTRIBUTES,
            share_delete=True,
        )
        handles.append(security_handle)
        before_identity = api.observe(security_handle)
        before_sddl = _capture_dacl_sddl(security_handle)
        if before_sddl != binding.source_dacl:
            raise _DaclFailure()
        move_handle = _open_move_handle_with_restored_dacl(
            api, binding, security_handle, before_sddl
        )
        handles.append(move_handle)
        parent_handle = api.open_existing(
            binding.destination.parent,
            access=FILE_READ_ATTRIBUTES,
        )
        handles.append(parent_handle)
        _require_move_objects(api, binding, move_handle, parent_handle)
        api.rename_no_replace(
            move_handle,
            parent_handle,
            binding.destination.name,
        )
        moved = api.observe(move_handle)
        if moved.object_identity_fingerprint != before_identity.object_identity_fingerprint:
            raise _DestinationFailure()
        if _capture_dacl_sddl(security_handle) != before_sddl:
            raise _DaclFailure()
    finally:
        for handle in reversed(handles):
            try:
                api.close(handle)
            except Exception:
                pass


def _open_move_handle_with_restored_dacl(
    api, binding, security_handle, before_sddl
):
    widened = False
    try:
        _set_dacl(security_handle, _temporary_sddl(before_sddl))
        widened = True
        return api.open_existing(
            binding.source,
            access=DELETE_ACCESS | FILE_READ_ATTRIBUTES,
            share_delete=True,
        )
    finally:
        if widened:
            _set_dacl(security_handle, before_sddl)
            if _capture_dacl_sddl(security_handle) != before_sddl:
                raise _DaclFailure()

def _require_move_objects(api, binding, source_handle, parent_handle):
    source = api.observe(source_handle)
    parent = api.observe(parent_handle)
    if (
        source.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or parent.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or source.filesystem_name != "NTFS"
        or parent.filesystem_name != "NTFS"
        or source.volume_serial_number != parent.volume_serial_number
        or os.path.lexists(binding.destination)
    ):
        raise _DestinationFailure()

def _require_artifacts(binding, *, destination=False):
    directory = binding.destination if destination else binding.source
    with guard_directory(directory, flush=False):
        names = tuple(sorted(item.name for item in directory.iterdir()))
        expected = tuple(sorted(item.name for item in binding.artifacts))
        if names != expected:
            raise ValueError
        for artifact in binding.artifacts:
            payload = read_segment(directory / artifact.name)
            if (
                len(payload) != artifact.length
                or hashlib.sha256(payload).hexdigest() != artifact.sha256
            ):
                raise ValueError


def _result(status, *, artifacts=0, moves=0):
    return IncidentDispositionResultV1(status, artifacts, moves, 0)


class _DaclFailure(Exception):
    pass


class _DestinationFailure(Exception):
    pass
