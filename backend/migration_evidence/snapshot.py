"""Descriptor-bound dirty worktree snapshot capture."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .checked_io import read_checked_file
from .contract import (
    DirtyDisposition,
    DirtyEntryReview,
    MigrationEvidenceReview,
)
from .errors import MigrationEvidenceError
from .git_discovery import git_output


_MAX_FILE_BYTES = 16 * 1024 * 1024
_MAX_TOTAL_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class SnapshotPayload:
    path: str
    status: str
    tracked: bool
    index_archive_path: str | None
    index_mode: str | None
    index_size: int
    index_sha256: str
    worktree_archive_path: str | None
    worktree_size: int
    worktree_sha256: str


def capture_snapshot(
    review: MigrationEvidenceReview,
) -> tuple[tuple[SnapshotPayload, ...], dict[str, bytes]]:
    """Read only exact approved worktree files after policy review."""

    records: list[SnapshotPayload] = []
    payloads: dict[str, bytes] = {}
    total = 0
    for entry in review.dirty_entries:
        if entry.disposition is not DirtyDisposition.INCLUDED:
            continue
        record, entry_payloads, entry_size = _capture_entry(review, entry)
        total += entry_size
        if total > _MAX_TOTAL_BYTES:
            raise MigrationEvidenceError("migration_evidence_create_failed")
        payloads.update(entry_payloads)
        records.append(record)
    _require_snapshot_stable(review, tuple(records), payloads)
    return tuple(records), payloads


def _capture_entry(
    review: MigrationEvidenceReview,
    entry: DirtyEntryReview,
) -> tuple[SnapshotPayload, dict[str, bytes], int]:
    _validate_status(entry.status)
    index_mode, index_payload = _read_index_payload(
        review.repository_root,
        entry.path,
        entry.tracked,
    )
    worktree_payload = _read_worktree_payload(
        review.repository_root,
        entry.path,
        entry.status,
    )
    index_path = _archive_path("index", entry.path, index_payload)
    worktree_path = _archive_path(
        "worktree",
        entry.path,
        worktree_payload,
    )
    payloads = {
        path: payload
        for path, payload in (
            (index_path, index_payload),
            (worktree_path, worktree_payload),
        )
        if path is not None and payload is not None
    }
    record = SnapshotPayload(
        path=entry.path,
        status=entry.status,
        tracked=entry.tracked,
        index_archive_path=index_path,
        index_mode=index_mode,
        index_size=_payload_size(index_payload),
        index_sha256=_payload_hash(index_payload),
        worktree_archive_path=worktree_path,
        worktree_size=_payload_size(worktree_payload),
        worktree_sha256=_payload_hash(worktree_payload),
    )
    size = _payload_size(index_payload) + _payload_size(worktree_payload)
    return record, payloads, size


def _validate_status(status: str) -> None:
    if status == "??":
        return
    if len(status) != 2 or status == "!!":
        raise MigrationEvidenceError("migration_evidence_create_failed")
    if any(code not in " MAD" for code in status):
        raise MigrationEvidenceError("migration_evidence_create_failed")
    if status == "  " or status == "DD":
        raise MigrationEvidenceError("migration_evidence_create_failed")


def _read_index_payload(
    root: Path,
    path: str,
    tracked: bool,
) -> tuple[str | None, bytes | None]:
    if not tracked:
        return None, None
    output = git_output(
        root,
        ("ls-files", "--stage", "-z", "--", path),
    )
    assert output is not None
    if output == b"":
        _require_regular_head_entry(root, path)
        return None, None
    mode, oid = _parse_index_entry(output, path)
    payload = git_output(
        root,
        ("cat-file", "blob", oid),
        maximum=_MAX_FILE_BYTES + 1,
    )
    assert payload is not None
    if len(payload) > _MAX_FILE_BYTES or _git_blob_oid(payload) != oid:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    return mode, payload


def _require_regular_head_entry(root: Path, path: str) -> None:
    output = git_output(
        root,
        ("ls-tree", "-z", "HEAD", "--", path),
    )
    assert output is not None
    if not output.endswith(b"\0") or output.count(b"\0") != 1:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    metadata, separator, raw_path = output[:-1].partition(b"\t")
    fields = metadata.split(b" ")
    try:
        mode = fields[0].decode("ascii")
        kind = fields[1].decode("ascii")
        oid = fields[2].decode("ascii")
        actual_path = raw_path.decode("utf-8")
    except (IndexError, UnicodeDecodeError):
        raise MigrationEvidenceError("migration_evidence_create_failed") from None
    if (
        not separator
        or len(fields) != 3
        or mode not in {"100644", "100755"}
        or kind != "blob"
        or len(oid) != 40
        or any(character not in "0123456789abcdef" for character in oid)
        or actual_path != path
    ):
        raise MigrationEvidenceError("migration_evidence_create_failed")


def _parse_index_entry(payload: bytes, expected_path: str) -> tuple[str, str]:
    if not payload.endswith(b"\0") or payload.count(b"\0") != 1:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    metadata, separator, raw_path = payload[:-1].partition(b"\t")
    fields = metadata.split(b" ")
    try:
        path = raw_path.decode("utf-8")
        mode = fields[0].decode("ascii")
        oid = fields[1].decode("ascii")
        stage = fields[2].decode("ascii")
    except (IndexError, UnicodeDecodeError):
        raise MigrationEvidenceError("migration_evidence_create_failed") from None
    if not separator or len(fields) != 3 or path != expected_path:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    if mode not in {"100644", "100755"} or stage != "0":
        raise MigrationEvidenceError("migration_evidence_create_failed")
    if len(oid) != 40 or any(character not in "0123456789abcdef" for character in oid):
        raise MigrationEvidenceError("migration_evidence_create_failed")
    return mode, oid


def _read_worktree_payload(
    root: Path,
    path: str,
    status: str,
) -> bytes | None:
    if status != "??" and "D" in status:
        return None
    return read_checked_file(root, path)


def _archive_path(
    layer: str,
    path: str,
    payload: bytes | None,
) -> str | None:
    if payload is None:
        return None
    return f"snapshot/{layer}/{path}"


def _require_snapshot_stable(
    review: MigrationEvidenceReview,
    records: tuple[SnapshotPayload, ...],
    payloads: dict[str, bytes],
) -> None:
    for record in records:
        mode, index_payload = _read_index_payload(
            review.repository_root,
            record.path,
            record.tracked,
        )
        worktree_payload = _read_worktree_payload(
            review.repository_root,
            record.path,
            record.status,
        )
        if mode != record.index_mode:
            raise MigrationEvidenceError("migration_evidence_create_failed")
        if index_payload != _stored_payload(
            payloads,
            record.index_archive_path,
        ):
            raise MigrationEvidenceError("migration_evidence_create_failed")
        if worktree_payload != _stored_payload(
            payloads,
            record.worktree_archive_path,
        ):
            raise MigrationEvidenceError("migration_evidence_create_failed")


def _stored_payload(
    payloads: dict[str, bytes],
    archive_path: str | None,
) -> bytes | None:
    if archive_path is None:
        return None
    try:
        return payloads[archive_path]
    except KeyError:
        raise MigrationEvidenceError("migration_evidence_create_failed") from None


def _payload_size(payload: bytes | None) -> int:
    return 0 if payload is None else len(payload)


def _payload_hash(payload: bytes | None) -> str:
    return _empty_hash() if payload is None else hashlib.sha256(payload).hexdigest()


def _git_blob_oid(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _empty_hash() -> str:
    return hashlib.sha256(b"").hexdigest()
