"""Strict selection and dirty-layer verification."""

from __future__ import annotations

import hashlib

from .contract import DirtyDisposition, DirtyReason
from .errors import MigrationEvidenceError
from .policy import (
    inclusion_reason,
    require_approved_source,
    validate_relative_path,
)


_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_SNAPSHOT_FIELDS = {
    "path",
    "status",
    "tracked",
    "index_archive_path",
    "index_mode",
    "index_size",
    "index_sha256",
    "worktree_archive_path",
    "worktree_size",
    "worktree_sha256",
}


def validate_selection_and_snapshot(
    *,
    review_fingerprint: str,
    selection: dict[str, object],
    snapshot: dict[str, object],
    manifest_records: object,
    worktrees: tuple[dict[str, object], ...],
    contents: dict[str, bytes],
) -> None:
    """Cross-check review entries, snapshot records, and layer payloads."""

    entries = _selection_entries(selection, review_fingerprint)
    records = _snapshot_records(snapshot, manifest_records, worktrees)
    included = {
        item["path"]: item
        for item in entries
        if item["disposition"] == DirtyDisposition.INCLUDED.value
    }
    if set(included) != {item["path"] for item in records}:
        _fail()
    for record in records:
        selected = included[record["path"]]
        if (
            selected["status"] != record["status"]
            or selected["tracked"] is not record["tracked"]
        ):
            _fail()
        _validate_layers(record, contents)
    referenced = {
        layer
        for record in records
        for layer in (
            record["index_archive_path"],
            record["worktree_archive_path"],
        )
        if layer is not None
    }
    actual = {
        path
        for path in contents
        if path.startswith("snapshot/")
        and path != "snapshot/index.json"
    }
    if actual != referenced:
        _fail()


def _selection_entries(
    selection: dict[str, object],
    review_fingerprint: str,
) -> tuple[dict[str, object], ...]:
    required = {
        "schema_version",
        "review_fingerprint",
        "repository_path_sha256",
        "target_path_sha256",
        "entries",
    }
    if set(selection) != required:
        _fail()
    if (
        selection["schema_version"] != "DirtySourceSelectionV1"
        or selection["review_fingerprint"] != review_fingerprint
        or not _is_sha256(selection["repository_path_sha256"])
        or not _is_sha256(selection["target_path_sha256"])
    ):
        _fail()
    values = selection["entries"]
    if type(values) is not list or len(values) > 2048:
        _fail()
    entries = [_selection_entry(value) for value in values]
    if entries != sorted(entries, key=lambda item: item["path"]):
        _fail()
    if len({item["path"] for item in entries}) != len(entries):
        _fail()
    return tuple(entries)


def _selection_entry(value: object) -> dict[str, object]:
    if type(value) is not dict or set(value) != {
        "path",
        "status",
        "tracked",
        "ignored",
        "disposition",
        "reason",
    }:
        _fail()
    path = validate_relative_path(value["path"])
    status = value["status"]
    if path != value["path"] or not _valid_status(status, allow_ignored=True):
        _fail()
    if type(value["tracked"]) is not bool or type(value["ignored"]) is not bool:
        _fail()
    if value["tracked"] is not (status not in {"!!", "??"}):
        _fail()
    if value["ignored"] is not (status == "!!"):
        _fail()
    if value["disposition"] not in {item.value for item in DirtyDisposition}:
        _fail()
    if value["reason"] not in {item.value for item in DirtyReason}:
        _fail()
    if value["disposition"] == DirtyDisposition.INCLUDED.value:
        if (
            value["reason"] != DirtyReason.APPROVED_SOURCE.value
            or value["ignored"] is not False
        ):
            _fail()
        try:
            require_approved_source(path)
        except MigrationEvidenceError:
            _fail()
    elif value["reason"] != inclusion_reason(
        path,
        ignored=value["ignored"],
    ).value:
        _fail()
    return value


def _snapshot_records(
    snapshot: dict[str, object],
    manifest_records: object,
    worktrees: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    if set(snapshot) != {
        "schema_version",
        "source_worktree_path_sha256",
        "records",
    }:
        _fail()
    main = [item for item in worktrees if item["is_main"] is True]
    if (
        snapshot["schema_version"] != "DirtySourceSnapshotV1"
        or len(main) != 1
        or snapshot["source_worktree_path_sha256"] != main[0]["path_sha256"]
    ):
        _fail()
    values = snapshot["records"]
    if type(values) is not list or values != manifest_records or len(values) > 256:
        _fail()
    records: list[dict[str, object]] = []
    for value in values:
        if type(value) is not dict or set(value) != _SNAPSHOT_FIELDS:
            _fail()
        if validate_relative_path(value["path"]) != value["path"]:
            _fail()
        if not _valid_status(value["status"], allow_ignored=False):
            _fail()
        if type(value["tracked"]) is not bool:
            _fail()
        records.append(value)
    if records != sorted(records, key=lambda item: item["path"]):
        _fail()
    if len({item["path"] for item in records}) != len(records):
        _fail()
    return tuple(records)


def _validate_layers(
    record: dict[str, object],
    contents: dict[str, bytes],
) -> None:
    tracked = record["tracked"]
    status = record["status"]
    index_present = tracked is True and status[0] != "D"
    worktree_present = status == "??" or "D" not in status
    _validate_layer(
        record,
        contents,
        layer="index",
        present=index_present,
        mode_required=index_present,
    )
    _validate_layer(
        record,
        contents,
        layer="worktree",
        present=worktree_present,
        mode_required=False,
    )


def _validate_layer(
    record: dict[str, object],
    contents: dict[str, bytes],
    *,
    layer: str,
    present: bool,
    mode_required: bool,
) -> None:
    archive_path = record[f"{layer}_archive_path"]
    mode = record.get(f"{layer}_mode")
    size = record[f"{layer}_size"]
    digest = record[f"{layer}_sha256"]
    if not present:
        if (
            archive_path is not None
            or mode is not None
            or size != 0
            or digest != _EMPTY_SHA256
        ):
            _fail()
        return
    expected = f"snapshot/{layer}/{record['path']}"
    if archive_path != expected:
        _fail()
    if mode_required and mode not in {"100644", "100755"}:
        _fail()
    if type(size) is not int or type(size) is bool or not 0 <= size <= 16 * 1024 * 1024:
        _fail()
    if not _is_sha256(digest):
        _fail()
    payload = contents.get(expected)
    if payload is None or len(payload) != size:
        _fail()
    if hashlib.sha256(payload).hexdigest() != digest:
        _fail()


def _valid_status(value: object, *, allow_ignored: bool) -> bool:
    if value == "??" or (allow_ignored and value == "!!"):
        return True
    return (
        type(value) is str
        and len(value) == 2
        and value not in {"  ", "DD"}
        and all(character in " MAD" for character in value)
    )


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _fail() -> None:
    raise MigrationEvidenceError("migration_evidence_verify_failed")
