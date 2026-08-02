"""Handle-bound DACL projection and authoritative reparse-free scans."""

from __future__ import annotations

import ctypes
import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from backend.cutover_host_mutation.roles import AclRole
from backend.cutover_host_mutation.windows_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    READ_CONTROL,
    WRITE_DAC,
    WindowsHandleApi,
)
from backend.cutover_host_mutation.windows_security import WindowsSecurityApi

from .canonical import fingerprint
from .contracts import ExpectedInheritedDaclProjectionV1, _projection

_DACL_SECURITY_INFORMATION = 0x00000004
_UNPROTECTED_DACL_SECURITY_INFORMATION = 0x20000000
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_SE_FILE_OBJECT = 1


@dataclass(frozen=True, slots=True, repr=False)
class SecurityObservation:
    logical_key_fingerprint: str = field(repr=False)
    identity_fingerprint: str = field(repr=False)
    owner_fingerprint: str = field(repr=False)
    group_fingerprint: str = field(repr=False)
    dacl_fingerprint: str = field(repr=False)
    dacl_protected: bool
    directory: bool


@dataclass(frozen=True, slots=True, repr=False)
class _CapturedItem:
    path: Path = field(repr=False)
    relative: str = field(repr=False)
    observation: SecurityObservation
    dacl: bytes = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class CapturedTree:
    items: tuple[_CapturedItem, ...] = field(repr=False)
    inventory_fingerprint: str = field(repr=False)

    @property
    def observations(self) -> tuple[SecurityObservation, ...]:
        return tuple(item.observation for item in self.items)


@dataclass(frozen=True, slots=True, repr=False)
class BoundDaclProjection:
    contract: ExpectedInheritedDaclProjectionV1
    root_dacl: bytes = field(repr=False)
    directory_dacl: bytes = field(repr=False)
    file_dacl: bytes = field(repr=False)


def capture_tree(root: Path) -> CapturedTree:
    pending = [root]
    items = []
    while pending:
        path = pending.pop()
        item = _capture_item(root, path)
        items.append(item)
        if item.observation.directory:
            pending.extend(reversed(_children(path)))
    items.sort(key=lambda item: item.relative.casefold())
    return CapturedTree(
        items=tuple(items),
        inventory_fingerprint=_inventory(items),
    )


def bind_projection(
    *,
    main: Path,
    directory_probe: Path,
    file_probe: Path,
) -> BoundDaclProjection:
    root = _capture_item(main, main)
    directory = _capture_item(main, directory_probe)
    file = _capture_item(main, file_probe)
    if (
        root.observation.dacl_protected
        or directory.observation.dacl_protected
        or file.observation.dacl_protected
    ):
        raise ValueError("main_acl_projection_invalid")
    contract = _projection(
        root_dacl_fingerprint=root.observation.dacl_fingerprint,
        directory_dacl_fingerprint=directory.observation.dacl_fingerprint,
        file_dacl_fingerprint=file.observation.dacl_fingerprint,
    )
    return BoundDaclProjection(contract, root.dacl, directory.dacl, file.dacl)


def conforms(tree: CapturedTree, projection: BoundDaclProjection) -> bool:
    return all(
        item.observation.dacl_fingerprint
        == _expected_fingerprint(item, projection.contract)
        and item.observation.dacl_protected is False
        for item in tree.items
    )


def apply_projection(tree: CapturedTree, projection: BoundDaclProjection) -> None:
    for item in tree.items:
        expected = _expected_bytes(item, projection)
        if (
            item.observation.dacl_fingerprint != _hash(expected)
            or item.observation.dacl_protected
        ):
            apply_exact_dacl(
                item.path,
                expected_identity=item.observation.identity_fingerprint,
                dacl=expected,
                protected=False,
            )


def restore_tree_dacls(
    current: CapturedTree,
    baseline: CapturedTree,
) -> None:
    expected = {
        item.observation.logical_key_fingerprint: item for item in baseline.items
    }
    for item in current.items:
        saved = expected.get(item.observation.logical_key_fingerprint)
        if saved is None or saved.observation.identity_fingerprint != (
            item.observation.identity_fingerprint
        ):
            raise ValueError("main_publication_rollback_ambiguous")
        apply_exact_dacl(
            item.path,
            expected_identity=item.observation.identity_fingerprint,
            dacl=saved.dacl,
            protected=saved.observation.dacl_protected,
        )


def apply_exact_dacl(
    path: Path,
    *,
    expected_identity: str,
    dacl: bytes,
    protected: bool,
) -> None:
    handles = WindowsHandleApi()
    security = WindowsSecurityApi()
    handle = handles.open_existing(path, access=READ_CONTROL | WRITE_DAC)
    try:
        before = security.capture_handle(handle, path=path, role=AclRole.SOURCE_TREE)
        if before.observation.object_identity_fingerprint != expected_identity:
            raise ValueError("main_publication_identity_changed")
        _set_dacl(handle, dacl, protected)
        after = security.capture_handle(handle, path=path, role=AclRole.SOURCE_TREE)
        _validate_dacl_result(before, after, expected_identity, dacl, protected)
    finally:
        handles.close(handle)


def _set_dacl(handle: int, dacl: bytes, protected: bool) -> None:
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
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
    buffer = ctypes.create_string_buffer(dacl)
    information = _DACL_SECURITY_INFORMATION | (
        _PROTECTED_DACL_SECURITY_INFORMATION
        if protected
        else _UNPROTECTED_DACL_SECURITY_INFORMATION
    )
    result = advapi.SetSecurityInfo(
        handle,
        _SE_FILE_OBJECT,
        information,
        None,
        None,
        ctypes.cast(buffer, ctypes.c_void_p),
        None,
    )
    if result != 0:
        raise OSError("main_publication_dacl_apply_failed")


def _validate_dacl_result(before, after, identity, dacl, protected) -> None:
    if (
        before.owner_sid != after.owner_sid
        or before.group_sid != after.group_sid
        or after.observation.object_identity_fingerprint != identity
        or after.observation.dacl_fingerprint != _hash(dacl)
        or after.observation.dacl_protected is not protected
    ):
        raise ValueError("main_publication_dacl_apply_rejected")


def _capture_item(root: Path, path: Path) -> _CapturedItem:
    captured = WindowsSecurityApi().capture(
        path,
        role=AclRole.SOURCE_TREE,
        _allow_reparse=True,
    )
    if captured.native_identity.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError("main_publication_reparse_rejected")
    relative = "." if path == root else path.relative_to(root).as_posix()
    observed = captured.observation
    return _CapturedItem(
        path=path,
        relative=relative,
        observation=SecurityObservation(
            logical_key_fingerprint=_logical_key(relative),
            identity_fingerprint=observed.object_identity_fingerprint,
            owner_fingerprint=observed.owner_fingerprint,
            group_fingerprint=observed.group_fingerprint,
            dacl_fingerprint=observed.dacl_fingerprint,
            dacl_protected=observed.dacl_protected,
            directory=bool(
                captured.native_identity.file_attributes
                & FILE_ATTRIBUTE_DIRECTORY
            ),
        ),
        dacl=captured.dacl,
    )


def _children(path: Path) -> list[Path]:
    try:
        return sorted(
            (Path(entry.path) for entry in os.scandir(path)),
            key=lambda item: item.name.casefold(),
        )
    except OSError:
        raise ValueError("main_publication_scan_failed") from None


def _expected_bytes(item, projection) -> bytes:
    if item.relative == ".":
        return projection.root_dacl
    return projection.directory_dacl if item.observation.directory else projection.file_dacl


def _expected_fingerprint(item, projection) -> str:
    if item.relative == ".":
        return projection.root_dacl_fingerprint
    return (
        projection.directory_dacl_fingerprint
        if item.observation.directory
        else projection.file_dacl_fingerprint
    )


def _inventory(items: list[_CapturedItem]) -> str:
    return fingerprint(
        "main-publication-security-inventory-v1",
        [
            {
                "key": item.observation.logical_key_fingerprint,
                "identity": item.observation.identity_fingerprint,
                "owner": item.observation.owner_fingerprint,
                "group": item.observation.group_fingerprint,
                "dacl": item.observation.dacl_fingerprint,
                "directory": item.observation.directory,
            }
            for item in items
        ],
    )


def _logical_key(relative: str) -> str:
    return hashlib.sha256(relative.casefold().encode("utf-8")).hexdigest()


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
