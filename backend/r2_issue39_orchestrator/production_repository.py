"""Reviewed tracked-byte manifest and resumable no-replace repository relocation."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from backend.cutover_managed_activation.windows_file_handles import WindowsReadHandleApi
from backend.cutover_repository_transaction.windows_identity import directory_identity

from .production_native import create_directory_no_replace, move_no_replace


_MAX_FILE_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 256 * 1024 * 1024
@dataclass(frozen=True, slots=True, repr=False)
class Issue39RepositoryEntryV1:
    relative: str
    git_oid: str = field(repr=False)
    size_bytes: int
    sha256: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class Issue39RepositoryManifestV1:
    entries: tuple[Issue39RepositoryEntryV1, ...] = field(repr=False)
    directories: tuple[str, ...]
    source_identity_fingerprint: str = field(repr=False)
    git_identity_fingerprint: str = field(repr=False)
    manifest_fingerprint: str = field(repr=False)

    def to_mapping(self):
        return {
            "entries": [
                {
                    "relative": item.relative, "git_oid": item.git_oid,
                    "size_bytes": item.size_bytes, "sha256": item.sha256,
                }
                for item in self.entries
            ],
            "directories": list(self.directories),
            "source_identity_fingerprint": self.source_identity_fingerprint,
            "git_identity_fingerprint": self.git_identity_fingerprint,
            "manifest_fingerprint": self.manifest_fingerprint,
        }


def review_repository_manifest(root):
    from .production_foundation import _git
    from .production_repository_review import (
        parse_index,
        require_clean_repository,
        require_safe_attributes,
        review_file,
    )

    if _git(root, ("rev-parse", "--show-object-format")).strip() != b"sha1":
        raise ValueError("R2_ISSUE39_REPOSITORY_OBJECT_FORMAT_INVALID")
    payload = _git(root, ("ls-files", "--stage", "-z"))
    indexed = parse_index(payload)
    attributes = require_safe_attributes(
        root, _git, tuple(relative for relative, _, _, _ in indexed)
    )
    clean = require_clean_repository(root, _git, indexed)
    entries, directories = _collect_entries(root, indexed, review_file)
    entries.sort(key=lambda item: item.relative)
    if not 1 <= len(entries) <= 10_000 or len(entries) != len({item.relative for item in entries}):
        raise ValueError("R2_ISSUE39_REPOSITORY_MANIFEST_INVALID")
    if _git(root, ("ls-files", "--stage", "-z")) != payload:
        raise ValueError("R2_ISSUE39_REPOSITORY_INDEX_DRIFT")
    if require_safe_attributes(
        root, _git, tuple(relative for relative, _, _, _ in indexed)
    ) != attributes:
        raise ValueError("R2_ISSUE39_REPOSITORY_ATTRIBUTES_INVALID")
    if require_clean_repository(root, _git, indexed) != clean:
        raise ValueError("R2_ISSUE39_REPOSITORY_NOT_CLEAN")
    body = {
        "entries": [{
            "relative": item.relative, "git_oid": item.git_oid,
            "size_bytes": item.size_bytes, "sha256": item.sha256,
        } for item in entries],
        "directories": sorted(directories, key=lambda item: (item.count("/"), item)),
        "source_identity_fingerprint": directory_identity(root),
        "git_identity_fingerprint": directory_identity(root / ".git"),
    }
    manifest = hashlib.sha256(
        b"r2-issue39-repository-manifest-v1\0" + _canonical(body)
    ).hexdigest()
    return Issue39RepositoryManifestV1(
        tuple(entries), tuple(body["directories"]),
        body["source_identity_fingerprint"], body["git_identity_fingerprint"],
        manifest,
    )


def _collect_entries(root, indexed, review_file):
    entries = []
    directories = set()
    total_bytes = 0
    for relative, _, oid, path in indexed:
        observed = review_file(
            root / Path(*path.parts), oid, limit=_MAX_FILE_BYTES
        )
        entries.append(Issue39RepositoryEntryV1(relative, oid, *observed))
        total_bytes += observed[0]
        if total_bytes > _MAX_TOTAL_BYTES:
            raise ValueError("R2_ISSUE39_REPOSITORY_MANIFEST_INVALID")
        for index in range(1, len(path.parts)):
            directories.add(PurePosixPath(*path.parts[:index]).as_posix())
    return entries, directories


def repository_manifest_from_mapping(value):
    if type(value) is not dict:
        raise ValueError
    entries = tuple(Issue39RepositoryEntryV1(**item) for item in value["entries"])
    body = {
        "entries": [
            {"relative": item.relative, "git_oid": item.git_oid,
             "size_bytes": item.size_bytes, "sha256": item.sha256}
            for item in entries
        ],
        "directories": value["directories"],
        "source_identity_fingerprint": value["source_identity_fingerprint"],
        "git_identity_fingerprint": value["git_identity_fingerprint"],
    }
    expected = hashlib.sha256(
        b"r2-issue39-repository-manifest-v1\0" + _canonical(body)
    ).hexdigest()
    if expected != value["manifest_fingerprint"]:
        raise ValueError
    return Issue39RepositoryManifestV1(
        entries, tuple(value["directories"]),
        value["source_identity_fingerprint"], value["git_identity_fingerprint"],
        expected,
    )


def relocate_repository(host, direction):
    source, target = (
        (host._layout.legacy, host._layout.main)
        if direction == "forward" else (host._layout.main, host._layout.legacy)
    )
    if direction == "forward":
        _ensure_directories(target, host._repository.directories)
        _move_entries(host._repository.entries, source, target)
        _move_git(host, source, target)
    else:
        _move_git(host, source, target)
        _move_entries(host._repository.entries, source, target)
    if not repository_exact(host, reverse=(direction == "rollback")):
        raise ValueError("R2_ISSUE39_REPOSITORY_RELOCATION_INVALID")


def repository_exact(host, *, reverse=False):
    source, target = _repository_positions(host, reverse)
    return all(
        _entry_exact(target / Path(*PurePosixPath(item.relative).parts), item)
        and not os.path.lexists(source / Path(*PurePosixPath(item.relative).parts))
        for item in host._repository.entries
    ) and (
        directory_identity(target / ".git")
        == host._repository.git_identity_fingerprint
        and not os.path.lexists(source / ".git")
    )


def _repository_positions(host, reverse):
    if not reverse:
        return host._layout.legacy, host._layout.main
    if os.path.lexists(host._layout.legacy):
        return host._layout.main, host._layout.legacy
    if os.path.lexists(host._layout.source) and os.path.lexists(host._layout.failed):
        return host._layout.failed / "main", host._layout.source
    return host._layout.main, host._layout.legacy


def repository_partial(host, action, direction):
    if action.action_name != "repository_relocation":
        return None
    legacy, main = host._layout.legacy, host._layout.main
    positions = []
    for item in host._repository.entries:
        relative = Path(*PurePosixPath(item.relative).parts)
        left = _entry_exact(legacy / relative, item)
        right = _entry_exact(main / relative, item)
        if left == right:
            raise ValueError("R2_ISSUE39_REPOSITORY_PARTIAL_INVALID")
        positions.append("L" if left else "M")
    git_left = _git_exact(host, legacy / ".git")
    git_right = _git_exact(host, main / ".git")
    if git_left == git_right:
        raise ValueError("R2_ISSUE39_REPOSITORY_PARTIAL_INVALID")
    if all(item == "L" for item in positions) and git_left:
        return None
    if all(item == "M" for item in positions) and git_right:
        return None
    return hashlib.sha256(
        b"r2-issue39-repository-partial-v1\0"
        + action.action_fingerprint.encode("ascii")
        + direction.encode("ascii") + "".join(positions).encode("ascii")
        + (b"L" if git_left else b"M")
    ).hexdigest()


def _ensure_directories(root, directories):
    for relative in directories:
        target = root / Path(*PurePosixPath(relative).parts)
        if os.path.lexists(target):
            _require_directory(target)
        else:
            create_directory_no_replace(target.parent, target)


def _move_entries(entries, source, target):
    for item in entries:
        relative = Path(*PurePosixPath(item.relative).parts)
        before, after = source / relative, target / relative
        if _entry_exact(after, item) and not os.path.lexists(before):
            continue
        if not _entry_exact(before, item) or os.path.lexists(after):
            raise ValueError("R2_ISSUE39_REPOSITORY_COLLISION")
        move_no_replace(before, after)
        if not _entry_exact(after, item):
            raise ValueError("R2_ISSUE39_REPOSITORY_BYTE_DRIFT")


def _move_git(host, source, target):
    before, after = source / ".git", target / ".git"
    if _git_exact(host, after) and not os.path.lexists(before):
        return
    if not _git_exact(host, before) or os.path.lexists(after):
        raise ValueError("R2_ISSUE39_REPOSITORY_GIT_COLLISION")
    move_no_replace(before, after)


def _entry_exact(path, entry):
    api = WindowsReadHandleApi()
    handle = None
    try:
        handle = api.open_existing(path, deny_write=True)
        observed = api.observe(handle)
        size, digest = api.hash_bounded(handle, limit=_MAX_FILE_BYTES)
        if size != entry.size_bytes or digest != entry.sha256:
            return False
        api.require_stable(handle, observed, path)
        return True
    except (OSError, ValueError):
        return False
    finally:
        if handle is not None:
            api.close(handle)


def _git_exact(host, path):
    try:
        return directory_identity(path) == host._repository.git_identity_fingerprint
    except Exception:
        return False


def _require_directory(path):
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode) or getattr(value, "st_file_attributes", 0) & 0x400:
        raise ValueError("R2_ISSUE39_REPOSITORY_DIRECTORY_INVALID")


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
