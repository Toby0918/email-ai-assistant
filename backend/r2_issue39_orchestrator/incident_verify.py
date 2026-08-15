"""Read-only verification of the one archived Issue #38 incident stage."""

from __future__ import annotations

import os

from backend.cutover_host_mutation.windows_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WindowsHandleApi,
)

from .incident_binding import _fixed_incident_binding
from .incident_security import _capture_dacl_sddl
from .incident_windows import _require_artifacts


def verify_fixed_incident_archive_v1() -> bool:
    """Require source absence and exact destination bytes, identity, and DACL."""

    if os.name != "nt":
        return False
    binding = _fixed_incident_binding()
    if os.path.lexists(binding.source) or not os.path.lexists(binding.destination):
        return False
    api = WindowsHandleApi()
    handle = None
    try:
        handle = api.open_existing(
            binding.destination,
            access=READ_CONTROL | FILE_READ_ATTRIBUTES,
            share_delete=True,
        )
        observed = api.observe(handle)
        if (
            not observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
            or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
            or observed.filesystem_name != "NTFS"
            or observed.drive_type != "fixed"
            or _capture_dacl_sddl(handle) != binding.source_dacl
        ):
            return False
        _require_artifacts(binding, destination=True)
        return True
    except Exception:
        return False
    finally:
        if handle is not None:
            try:
                api.close(handle)
            except Exception:
                pass


def observe_fixed_incident_state_v1() -> str:
    """Return only one exact source/archive state; reject every collision."""

    if verify_fixed_incident_archive_v1():
        return "ARCHIVED"
    binding = _fixed_incident_binding()
    if (
        os.name != "nt"
        or not os.path.lexists(binding.source)
        or os.path.lexists(binding.destination)
    ):
        return "BLOCKED"
    api = WindowsHandleApi()
    handle = None
    try:
        handle = api.open_existing(
            binding.source,
            access=READ_CONTROL | FILE_READ_ATTRIBUTES,
            share_delete=True,
        )
        observed = api.observe(handle)
        if (
            not observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
            or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
            or observed.filesystem_name != "NTFS"
            or observed.drive_type != "fixed"
            or _capture_dacl_sddl(handle) != binding.source_dacl
        ):
            return "BLOCKED"
        _require_artifacts(binding)
        return "SOURCE_VERIFIED"
    except Exception:
        return "BLOCKED"
    finally:
        if handle is not None:
            try:
                api.close(handle)
            except Exception:
                pass
