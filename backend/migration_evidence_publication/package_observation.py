"""Content-free observation of one newly published evidence package."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


_ERROR = "MIGRATION_EVIDENCE_PACKAGE_OBSERVATION_REJECTED"
_MAX_PACKAGE_BYTES = 256 * 1024 * 1024
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class PackageAggregateCountsV1:
    files: int
    refs: int
    worktrees: int


@dataclass(frozen=True, slots=True)
class CreatedPackageObservationV1:
    review_fingerprint: str = field(repr=False)
    package_sha256: str = field(repr=False)
    manifest_sha256: str = field(repr=False)
    package_identity_fingerprint: str = field(repr=False)
    counts: PackageAggregateCountsV1
    counts_fingerprint: str = field(repr=False)


def observe_created_package(
    *,
    package: Path,
) -> CreatedPackageObservationV1:
    """Reread one created target without invoking independent verification."""

    try:
        payload, identity = _read_stable_package(package)
        manifest_bytes, manifest = _read_manifest(payload)
        review, counts = _manifest_observation(manifest)
        package_hash = hashlib.sha256(payload).hexdigest()
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        return CreatedPackageObservationV1(
            review_fingerprint=review,
            package_sha256=package_hash,
            manifest_sha256=manifest_hash,
            package_identity_fingerprint=_identity_fingerprint(
                identity,
                package_hash,
                manifest_hash,
            ),
            counts=counts,
            counts_fingerprint=_counts_fingerprint(counts),
        )
    except Exception:
        raise ValueError(_ERROR) from None


def _read_stable_package(
    package: object,
) -> tuple[bytes, tuple[int, int, int, int, int, int]]:
    if (
        not isinstance(package, Path)
        or not package.is_absolute()
        or not package.name.endswith(".migration-evidence.zip")
    ):
        raise ValueError(_ERROR)
    _require_directory(package.parent)
    before = _file_identity(package)
    descriptor = -1
    try:
        descriptor = os.open(
            package,
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = _identity_from_stat(os.fstat(descriptor), regular=True)
        if opened != before or opened[3] > _MAX_PACKAGE_BYTES:
            raise ValueError(_ERROR)
        payload = _read_limit(descriptor, _MAX_PACKAGE_BYTES + 1)
        if len(payload) > _MAX_PACKAGE_BYTES:
            raise ValueError(_ERROR)
        if (
            _identity_from_stat(os.fstat(descriptor), regular=True)
            != opened
            or _file_identity(package) != opened
        ):
            raise ValueError(_ERROR)
        return payload, opened
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _read_manifest(
    payload: bytes,
) -> tuple[bytes, dict[str, object]]:
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        names = archive.namelist()
        if (
            names.count("manifest.json") != 1
            or len(names) != len(set(names))
        ):
            raise ValueError(_ERROR)
        info = archive.getinfo("manifest.json")
        if not 1 <= info.file_size <= _MAX_MANIFEST_BYTES:
            raise ValueError(_ERROR)
        manifest_bytes = archive.read(info)
    return manifest_bytes, _strict_json(manifest_bytes)


def _manifest_observation(
    manifest: dict[str, object],
) -> tuple[str, PackageAggregateCountsV1]:
    review = manifest.get("review_fingerprint")
    files = manifest.get("files")
    refs = manifest.get("refs")
    worktrees = manifest.get("worktrees")
    if (
        not _is_fingerprint(review)
        or type(files) is not list
        or type(refs) is not list
        or type(worktrees) is not list
        or not 1 <= len(files) <= 599
        or not 1 <= len(refs) <= 128
        or not 1 <= len(worktrees) <= 64
    ):
        raise ValueError(_ERROR)
    return review, PackageAggregateCountsV1(
        files=len(files),
        refs=len(refs),
        worktrees=len(worktrees),
    )


def _identity_fingerprint(
    identity: tuple[int, int, int, int, int, int],
    package_sha256: str,
    manifest_sha256: str,
) -> str:
    device, inode, mode, size, modified_ns, links = identity
    return _fingerprint(
        {
            "schema": "MigrationEvidencePackageIdentityV1",
            "device": device,
            "inode": inode,
            "mode_type": stat.S_IFMT(mode),
            "size": size,
            "modified_ns": modified_ns,
            "links": links,
            "package_sha256": package_sha256,
            "manifest_sha256": manifest_sha256,
        }
    )


def _counts_fingerprint(counts: PackageAggregateCountsV1) -> str:
    return _fingerprint(
        {
            "schema": "MigrationEvidenceAggregateCountsV1",
            "files": counts.files,
            "refs": counts.refs,
            "worktrees": counts.worktrees,
        }
    )


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _strict_json(payload: bytes) -> dict[str, object]:
    def object_pairs(pairs):
        value: dict[str, object] = {}
        for key, item in pairs:
            if type(key) is not str or key in value:
                raise ValueError(_ERROR)
            value[key] = item
        return value

    decoded = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=object_pairs,
        parse_constant=lambda _value: _fail(),
    )
    if type(decoded) is not dict:
        raise ValueError(_ERROR)
    return decoded


def _require_directory(path: Path) -> None:
    metadata = os.lstat(path)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & reparse
    ):
        raise ValueError(_ERROR)


def _file_identity(
    path: Path,
) -> tuple[int, int, int, int, int, int]:
    return _identity_from_stat(os.lstat(path), regular=True)


def _identity_from_stat(
    metadata: object,
    *,
    regular: bool,
) -> tuple[int, int, int, int, int, int]:
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        regular
        and (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & reparse
            or metadata.st_nlink != 1
        )
    ):
        raise ValueError(_ERROR)
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_nlink,
    )


def _read_limit(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    remaining = limit
    while remaining:
        chunk = os.read(descriptor, min(64 * 1024, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and set(value) <= _HEX
    )


def _fail() -> None:
    raise ValueError(_ERROR)
