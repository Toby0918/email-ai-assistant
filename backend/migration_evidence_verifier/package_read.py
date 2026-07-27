"""Stable read-only package observations for the verifier worker."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .canonical import (
    VerifierProcessError,
    canonical_sha256,
    decode_canonical_object,
    is_sha256,
)


_MAX_PACKAGE_BYTES = 256 * 1024 * 1024
_MAX_MANIFEST_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class StablePackageRead:
    payload: bytes
    device: int
    inode: int
    mode_type: int
    links: int
    size: int
    modified_ns: int


def read_package_once(package: Path) -> StablePackageRead:
    _require_package_path(package)
    before = package.lstat()
    _require_regular_single_link(before)
    descriptor = None
    try:
        descriptor = os.open(package, _read_flags())
        opened_before = os.fstat(descriptor)
        _require_regular_single_link(opened_before)
        if _metadata(before) != _metadata(opened_before):
            raise VerifierProcessError
        payload = _read_bounded(descriptor, opened_before.st_size)
        opened_after = os.fstat(descriptor)
        if _metadata(opened_before) != _metadata(opened_after):
            raise VerifierProcessError
    except VerifierProcessError:
        raise
    except Exception:
        raise VerifierProcessError from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    after = package.lstat()
    _require_regular_single_link(after)
    if _metadata(before) != _metadata(after):
        raise VerifierProcessError
    return StablePackageRead(
        payload=payload,
        device=opened_after.st_dev,
        inode=opened_after.st_ino,
        mode_type=stat.S_IFMT(opened_after.st_mode),
        links=opened_after.st_nlink,
        size=opened_after.st_size,
        modified_ns=opened_after.st_mtime_ns,
    )


def require_same_package(
    before: StablePackageRead,
    after: StablePackageRead,
) -> None:
    if before != after:
        raise VerifierProcessError


def package_observation(
    package_read: StablePackageRead,
) -> dict[str, object]:
    package_sha256 = hashlib.sha256(
        package_read.payload
    ).hexdigest()
    manifest, manifest_bytes = _read_manifest(package_read.payload)
    review_fingerprint = manifest.get("review_fingerprint")
    if not is_sha256(review_fingerprint):
        raise VerifierProcessError
    files = _bounded_list_count(manifest.get("files"), 599)
    refs = _bounded_list_count(manifest.get("refs"), 128)
    worktrees = _bounded_list_count(manifest.get("worktrees"), 64)
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    identity = canonical_sha256(
        {
            "schema": "MigrationEvidencePackageIdentityV1",
            "device": package_read.device,
            "inode": package_read.inode,
            "mode_type": package_read.mode_type,
            "links": package_read.links,
            "size": package_read.size,
            "modified_ns": package_read.modified_ns,
            "package_sha256": package_sha256,
            "manifest_sha256": manifest_sha256,
        }
    )
    counts = canonical_sha256(
        {
            "schema": "MigrationEvidenceAggregateCountsV1",
            "files": files,
            "refs": refs,
            "worktrees": worktrees,
        }
    )
    return {
        "review_fingerprint": review_fingerprint,
        "package_sha256": package_sha256,
        "manifest_sha256": manifest_sha256,
        "package_identity_fingerprint": identity,
        "files": files,
        "refs": refs,
        "worktrees": worktrees,
        "counts_fingerprint": counts,
    }


def _read_manifest(
    payload: bytes,
) -> tuple[dict[str, object], bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            info = archive.getinfo("manifest.json")
            if not 1 <= info.file_size <= _MAX_MANIFEST_BYTES:
                raise VerifierProcessError
            manifest_bytes = archive.read(info)
    except VerifierProcessError:
        raise
    except Exception:
        raise VerifierProcessError from None
    return decode_canonical_object(manifest_bytes), manifest_bytes


def _bounded_list_count(value: object, maximum: int) -> int:
    if type(value) is not list or not 1 <= len(value) <= maximum:
        raise VerifierProcessError
    return len(value)


def _read_bounded(descriptor: int, expected_size: int) -> bytes:
    if not 1 <= expected_size <= _MAX_PACKAGE_BYTES:
        raise VerifierProcessError
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(
            descriptor,
            min(1024 * 1024, _MAX_PACKAGE_BYTES + 1 - total),
        )
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > _MAX_PACKAGE_BYTES:
            raise VerifierProcessError
    payload = b"".join(chunks)
    if len(payload) != expected_size:
        raise VerifierProcessError
    return payload


def _require_package_path(package: Path) -> None:
    if (
        not isinstance(package, Path)
        or not package.is_absolute()
        or not package.name.endswith(".migration-evidence.zip")
    ):
        raise VerifierProcessError


def _require_regular_single_link(value: os.stat_result) -> None:
    attributes = getattr(value, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        not stat.S_ISREG(value.st_mode)
        or value.st_nlink != 1
        or bool(attributes & reparse)
    ):
        raise VerifierProcessError


def _metadata(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
    )


def _read_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
