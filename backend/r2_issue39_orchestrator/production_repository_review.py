"""Filter-free index, attribute, and raw-byte review for repository relocation."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from backend.cutover_managed_activation.windows_file_handles import (
    WindowsReadHandleApi,
)


_REVIEWED_ATTRIBUTES = ("filter", "working-tree-encoding", "text", "eol")
_ATTRIBUTE_BATCH_SIZE = 32


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


def require_safe_attributes(root, git, relatives):
    evidence = []
    for start in range(0, len(relatives), _ATTRIBUTE_BATCH_SIZE):
        batch = relatives[start:start + _ATTRIBUTE_BATCH_SIZE]
        payload = git(
            root,
            ("check-attr", "-z", *_REVIEWED_ATTRIBUTES, "--", *batch),
        )
        fields = payload.split(b"\0")
        if not fields or fields[-1] != b"":
            raise ValueError("R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID")
        fields.pop()
        if len(fields) != len(batch) * len(_REVIEWED_ATTRIBUTES) * 3:
            raise ValueError("R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID")
        position = 0
        for relative in batch:
            for attribute in _REVIEWED_ATTRIBUTES:
                expected = (
                    relative.encode("utf-8"), attribute.encode("ascii"),
                    b"unspecified",
                )
                if tuple(fields[position:position + 3]) != expected:
                    raise ValueError(
                        "R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID"
                    )
                position += 3
        evidence.append(payload)
    return tuple(evidence)


def review_file(path, oid, *, limit):
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
            b"\r\n" not in payload or b"\0" in payload
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


def _lower_hex(value):
    return all(character in "0123456789abcdef" for character in value)
