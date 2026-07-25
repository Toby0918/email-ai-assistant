"""Canonical SHA-256 manifest and deterministic archive encoding."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from typing import Mapping

from .errors import MigrationEvidenceError
from .snapshot import SnapshotPayload


_MANIFEST_NAME = "manifest.json"
_COMMENT_PREFIX = b"sha256:"


def build_archive(
    *,
    review_fingerprint: str,
    payloads: Mapping[str, bytes],
    snapshot_records: tuple[SnapshotPayload, ...],
    refs: tuple[dict[str, str], ...],
    worktrees: tuple[dict[str, object], ...],
) -> bytes:
    """Build one deterministic ZIP whose comment binds its manifest."""

    _validate_payloads(payloads)
    files = [
        {
            "path": path,
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, payload in sorted(payloads.items())
    ]
    manifest = {
        "schema_version": "MigrationEvidencePackageV1",
        "review_fingerprint": review_fingerprint,
        "files": files,
        "snapshot_records": [_snapshot_mapping(item) for item in snapshot_records],
        "refs": list(refs),
        "worktrees": list(worktrees),
    }
    encoded_manifest = canonical_json(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, payload in sorted(payloads.items()):
            archive.writestr(_zip_info(path), payload)
        archive.writestr(_zip_info(_MANIFEST_NAME), encoded_manifest)
        archive.comment = _COMMENT_PREFIX + hashlib.sha256(encoded_manifest).hexdigest().encode("ascii")
    return output.getvalue()


def canonical_json(value: object) -> bytes:
    """Encode strict ordered JSON used for every package identity."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def strict_json(payload: bytes) -> dict[str, object]:
    """Decode UTF-8 JSON while rejecting duplicate keys and constants."""

    def object_pairs(pairs):
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            value[key] = item
        return value

    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=lambda _value: _invalid_json(),
        )
    except MigrationEvidenceError:
        raise
    except Exception:
        raise MigrationEvidenceError("migration_evidence_verify_failed") from None
    if type(decoded) is not dict:
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    return decoded


def manifest_comment(payload: bytes) -> bytes:
    """Return the exact archive comment for canonical manifest bytes."""

    return _COMMENT_PREFIX + hashlib.sha256(payload).hexdigest().encode("ascii")


def _snapshot_mapping(item: SnapshotPayload) -> dict[str, object]:
    return {
        "path": item.path,
        "status": item.status,
        "tracked": item.tracked,
        "index_archive_path": item.index_archive_path,
        "index_mode": item.index_mode,
        "index_size": item.index_size,
        "index_sha256": item.index_sha256,
        "worktree_archive_path": item.worktree_archive_path,
        "worktree_size": item.worktree_size,
        "worktree_sha256": item.worktree_sha256,
    }


def _zip_info(path: str) -> zipfile.ZipInfo:
    if not _valid_path(path, allow_manifest=True):
        raise MigrationEvidenceError("migration_evidence_create_failed")
    info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100600 << 16
    info.create_system = 3
    return info


def _invalid_json():
    raise MigrationEvidenceError("migration_evidence_verify_failed")


def _validate_payloads(payloads: Mapping[str, bytes]) -> None:
    if not 1 <= len(payloads) <= 599:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    paths = list(payloads)
    if len(paths) != len({path.casefold() for path in paths}):
        raise MigrationEvidenceError("migration_evidence_create_failed")
    total = 0
    for path, payload in payloads.items():
        if (
            not _valid_path(path)
            or type(payload) is not bytes
            or len(payload) > 192 * 1024 * 1024
        ):
            raise MigrationEvidenceError("migration_evidence_create_failed")
        total += len(payload)
    if total > 256 * 1024 * 1024:
        raise MigrationEvidenceError("migration_evidence_create_failed")


def _valid_path(value: object, *, allow_manifest: bool = False) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 512:
        return False
    if value == _MANIFEST_NAME:
        return allow_manifest
    parts = value.split("/")
    return (
        not value.startswith("/")
        and "\\" not in value
        and ":" not in value
        and all(
            part not in {"", ".", ".."}
            and len(part) <= 128
            and all(32 <= ord(character) != 127 for character in part)
            for part in parts
        )
    )
