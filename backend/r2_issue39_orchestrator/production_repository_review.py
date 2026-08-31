"""Filter-free index, attribute, and raw-byte review for repository relocation."""

from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath

from backend.cutover_managed_activation.windows_file_handles import (
    WindowsReadHandleApi,
)


_ABSENT_CONFIG = b"R2_ISSUE39_CONFIG_ABSENT"


def parse_index(payload):
    indexed = []
    try:
        for record in payload.split(b"\0"):
            if not record:
                continue
            prefix, raw_path = record.split(b"\t", 1)
            mode, oid, stage = prefix.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            path = PurePosixPath(relative)
            if (
                mode not in {"100644", "100755"} or stage != "0"
                or len(oid) != 40 or not _lower_hex(oid)
                or path.is_absolute()
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ValueError
            indexed.append((relative, mode, oid, path))
    except (UnicodeError, ValueError):
        raise ValueError("R2_ISSUE39_REPOSITORY_MANIFEST_INVALID") from None
    return tuple(indexed)


def require_clean_repository(root, git, indexed):
    head = git(root, ("ls-tree", "-r", "-z", "--full-tree", "HEAD"))
    expected_head = tuple(
        (relative, mode, oid) for relative, mode, oid, _ in indexed
    )
    if _parse_head(head) != expected_head:
        raise ValueError("R2_ISSUE39_REPOSITORY_NOT_CLEAN")
    flags = git(root, ("ls-files", "-v", "-z"))
    expected_flags = b"".join(
        b"H " + relative.encode("utf-8") + b"\0"
        for relative, _, _, _ in indexed
    )
    if flags != expected_flags:
        raise ValueError("R2_ISSUE39_REPOSITORY_NOT_CLEAN")
    untracked = git(root, ("ls-files", "--others", "--exclude-standard", "-z"))
    if untracked:
        raise ValueError("R2_ISSUE39_REPOSITORY_NOT_CLEAN")
    return head, flags, untracked


def require_no_attribute_sources(root, git, indexed):
    if any(path.name.casefold() == ".gitattributes" for *_, path in indexed):
        raise ValueError("R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID")
    repository_value = _config_value(
        root, git, ("config", "--no-includes"), "core.attributesFile"
    )
    system_value = _config_value(
        root, git, ("config", "--system", "--no-includes"),
        "core.attributesFile",
    )
    if repository_value != _ABSENT_CONFIG or system_value != _ABSENT_CONFIG:
        raise ValueError("R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID")
    info_attributes = root / ".git" / "info" / "attributes"
    if os.path.lexists(info_attributes):
        raise ValueError("R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID")
    return repository_value, system_value, False


def controlled_crlf_mode(root, git):
    repository_value = _config_value(
        root, git, ("config", "--no-includes"), "core.autocrlf"
    )
    system_value = git(
        root,
        (
            "config", "--system", "--no-includes", "--type=bool",
            "--default=false", "--get", "core.autocrlf",
        ),
    ).strip()
    allowed = repository_value == b"true" or (
        repository_value == _ABSENT_CONFIG and system_value == b"true"
    )
    return repository_value, system_value, allowed


def review_file(path, oid, *, limit, allow_crlf_projection):
    api = WindowsReadHandleApi()
    handle = api.open_existing(path, deny_write=True)
    try:
        observed = api.observe(handle)
        size = api.require_size_bounded(handle, limit=limit)
        payload = api.read_bounded(handle, limit=size)
        api.require_stable(handle, observed, path)
    finally:
        api.close(handle)
    if _git_blob_oid(payload) != oid:
        projected = payload.replace(b"\r\n", b"\n")
        if (
            not allow_crlf_projection
            or b"\r\n" not in payload or b"\0" in payload
            or b"\r" in projected or _git_blob_oid(projected) != oid
        ):
            raise ValueError("R2_ISSUE39_REPOSITORY_BYTE_DRIFT")
    return size, hashlib.sha256(payload).hexdigest()


def _parse_head(payload):
    entries = []
    try:
        for record in payload.split(b"\0"):
            if not record:
                continue
            prefix, raw_path = record.split(b"\t", 1)
            mode, object_type, oid = prefix.decode("ascii").split(" ")
            relative = raw_path.decode("utf-8")
            path = PurePosixPath(relative)
            if (
                mode not in {"100644", "100755"} or object_type != "blob"
                or len(oid) != 40 or not _lower_hex(oid)
                or path.is_absolute()
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ValueError
            entries.append((relative, mode, oid))
    except (UnicodeError, ValueError):
        raise ValueError("R2_ISSUE39_REPOSITORY_MANIFEST_INVALID") from None
    return tuple(entries)


def _git_blob_oid(payload):
    return hashlib.sha1(
        b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload
    ).hexdigest()


def _config_value(root, git, prefix, name):
    return git(
        root,
        (
            *prefix, "--default=" + _ABSENT_CONFIG.decode("ascii"),
            "--get", name,
        ),
    ).strip()


def _lower_hex(value):
    return all(character in "0123456789abcdef" for character in value)
