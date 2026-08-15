"""Narrow held-identity Windows primitives owned only by the Issue #39 binder."""

from __future__ import annotations

import contextlib
import os

from backend.cutover_host_mutation.windows_handles import (
    DELETE_ACCESS,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
)
from backend.real_host_preflight.windows_paths import expected_final_path
from backend.cutover_managed_activation.windows_file_handles import WindowsReadHandleApi
from backend.cutover_managed_activation.windows_publication_io import WindowsCreateOnlyApi


def create_directory_no_replace(parent, target):
    if target.parent != parent or os.path.lexists(target):
        raise ValueError("R2_ISSUE39_DIRECTORY_COLLISION")
    from .durable_io import guard_directory

    with guard_directory(parent, flush=True):
        reader = WindowsReadHandleApi()
        creator = WindowsCreateOnlyApi()
        parent_handle = created_handle = None
        try:
            parent_handle = reader.open_existing(parent, deny_write=False)
            parent_before = reader.observe(parent_handle)
            reader.require_stable(parent_handle, parent_before, parent)
            created_handle = creator.create_directory(parent_handle, target.name)
            created = reader.observe(created_handle)
            if (
                created.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
                or created.filesystem_name != "NTFS"
                or not created.fixed_drive
            ):
                raise ValueError("R2_ISSUE39_DIRECTORY_IDENTITY_INVALID")
            reader.require_stable(created_handle, created, target)
            reader.require_stable(parent_handle, parent_before, parent)
            return created.object_identity_fingerprint
        finally:
            if created_handle is not None:
                reader.close(created_handle)
            if parent_handle is not None:
                reader.close(parent_handle)


def move_no_replace(source, target):
    if os.path.lexists(target):
        raise ValueError("R2_ISSUE39_MOVE_COLLISION")
    from .durable_io import guard_directory

    parents = tuple(sorted(
        {source.parent, target.parent}, key=lambda item: str(item).casefold()
    ))
    with contextlib.ExitStack() as guards:
        for parent in parents:
            guards.enter_context(guard_directory(parent, flush=True))
        api = WindowsHandleApi()
        source_handle = parent_handle = None
        try:
            source_handle = api.open_existing(
                source,
                access=DELETE_ACCESS | FILE_READ_ATTRIBUTES,
                share_delete=True,
            )
            parent_handle = api.open_existing(
                target.parent, access=FILE_READ_ATTRIBUTES
            )
            source_before = api.observe(source_handle)
            parent_before = api.observe(parent_handle)
            _require_move_compatible(source_before, parent_before)
            api.require_stable(source_handle, source_before, source)
            api.require_stable(parent_handle, parent_before, target.parent)
            if os.path.lexists(target):
                raise ValueError("R2_ISSUE39_MOVE_COLLISION")
            api.rename_no_replace(source_handle, parent_handle, target.name)
            moved = api.observe(source_handle)
            if (
                moved.object_identity_fingerprint
                != source_before.object_identity_fingerprint
                or moved.normalized_path.casefold()
                != expected_final_path(target).casefold()
                or os.path.lexists(source)
            ):
                raise ValueError("R2_ISSUE39_MOVE_IDENTITY_INVALID")
            api.require_stable(parent_handle, parent_before, target.parent)
            return moved.object_identity_fingerprint
        finally:
            if parent_handle is not None:
                api.close(parent_handle)
            if source_handle is not None:
                api.close(source_handle)


def _require_move_compatible(source, parent):
    if (
        source.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or parent.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or source.filesystem_name != "NTFS"
        or parent.filesystem_name != "NTFS"
        or source.drive_type != "fixed"
        or parent.drive_type != "fixed"
        or source.volume_serial_number != parent.volume_serial_number
    ):
        raise ValueError("R2_ISSUE39_MOVE_IDENTITY_INVALID")
