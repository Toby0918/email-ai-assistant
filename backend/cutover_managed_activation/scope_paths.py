"""Private path and source validation for the synthetic activation scope."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from .canonical import fail
from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)
from .windows_publication_io import require_safe_component

MARKER_NAME = ".codex-managed-activation-test-sandbox"
MARKER_BYTES = b"issue57-synthetic-marker-v1"
_ERROR = "managed_activation_scope_invalid"
_REPARSE_ATTRIBUTE = 0x400


def scenario_paths(scenario: object) -> dict[str, object]:
    names = (
        "root",
        "marker",
        "python_source",
        "python_source_manifest",
        "wheelhouse",
        "dependency_lock",
        "runtime_target",
        "database_source",
        "database_target",
        "crx_source",
        "crx_target",
        "config_target",
    )
    try:
        values = {name: getattr(scenario, name) for name in names}
    except Exception:
        fail(_ERROR)
    if any(type(value) is not type(Path()) for value in values.values()):
        fail(_ERROR)
    try:
        values["config_values"] = getattr(scenario, "config_values")
    except Exception:
        fail(_ERROR)
    return values


def validate_owned_paths(paths: dict[str, object]) -> None:
    root = paths["root"]
    marker = paths["marker"]
    target = paths["runtime_target"]
    if not _root_and_targets_are_valid(paths, root, marker, target):
        fail(_ERROR)
    for name in (
        "python_source",
        "python_source_manifest",
        "wheelhouse",
        "dependency_lock",
        "database_source",
        "crx_source",
    ):
        path = paths[name]
        if root not in path.parents:
            fail(_ERROR)
        require_no_reparse_chain(path, root)
    for parent in (
        target.parent,
        paths["database_target"].parent,
        paths["crx_target"].parent,
        paths["config_target"].parent,
    ):
        require_no_reparse_chain(parent, root)


def _root_and_targets_are_valid(paths, root, marker, target) -> bool:
    targets = (
        target,
        paths["database_target"],
        paths["crx_target"],
        paths["config_target"],
    )
    return (
        root.is_absolute()
        and root.is_dir()
        and not reparse(root)
        and marker.parent == root
        and marker.name == MARKER_NAME
        and marker.read_bytes() == MARKER_BYTES
        and target.parent.parent == root
        and all(_safe_target_name(item.name) for item in targets)
        and all(not item.exists() for item in targets)
        and all(not item.is_symlink() for item in targets)
    )


def _safe_target_name(value: str) -> bool:
    try:
        require_safe_component(value)
    except Exception:
        return False
    return True


def identity(path: Path) -> str:
    try:
        metadata = path.stat()
    except OSError:
        fail(_ERROR)
    return hashlib.sha256(
        b"issue57-object-v1\0"
        + str(metadata.st_dev).encode("ascii")
        + b"\0"
        + str(metadata.st_ino).encode("ascii")
        + b"\0"
        + str(stat.S_IFMT(metadata.st_mode)).encode("ascii")
    ).hexdigest()


def sqlite_schema_fingerprint(payload: bytes) -> str:
    if len(payload) < 100 or payload[:16] != b"SQLite format 3\x00":
        fail("managed_activation_database_invalid")
    return hashlib.sha256(
        b"issue57-sqlite-header-v1\0"
        + payload[:24]
        + payload[28:48]
        + payload[56:100]
    ).hexdigest()


def native_file_identity(path: Path) -> str:
    api = WindowsReadHandleApi()
    handle = None
    try:
        handle = api.open_existing(path, deny_write=False)
        observed = api.observe(handle)
        if not _native_observation_is_allowed(observed):
            fail(_ERROR)
        return observed.object_identity_fingerprint
    except Exception:
        fail(_ERROR)
    finally:
        if handle is not None:
            api.close(handle)


def _native_observation_is_allowed(observed) -> bool:
    return not (
        observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or not observed.fixed_drive
    )


def crx_format_version(payload: bytes) -> int:
    if len(payload) < 12 or payload[:4] != b"Cr24":
        fail("managed_activation_crx_invalid")
    version = int.from_bytes(payload[4:8], "little")
    if version == 2:
        if len(payload) < 16:
            fail("managed_activation_crx_invalid")
        header_end = (
            16
            + int.from_bytes(payload[8:12], "little")
            + int.from_bytes(payload[12:16], "little")
        )
    elif version == 3:
        header_end = 12 + int.from_bytes(payload[8:12], "little")
    else:
        fail("managed_activation_crx_invalid")
    if header_end >= len(payload):
        fail("managed_activation_crx_invalid")
    return version


def require_no_reparse_chain(path: Path, root: Path) -> None:
    current = path
    while True:
        if reparse(current):
            fail(_ERROR)
        if current == root:
            return
        if root not in current.parents:
            fail(_ERROR)
        current = current.parent


def reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        fail(_ERROR)
    return bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE
    ) or path.is_symlink()
