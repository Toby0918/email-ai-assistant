"""Strict bounded schemas for Git and host evidence."""

from __future__ import annotations

import hashlib

from .manifest import canonical_json, strict_json
from .verification_snapshot import validate_selection_and_snapshot
from .verification_values import (
    bounded_count as _bounded_count,
    fail_verification as _fail,
    is_oid as _is_oid,
    is_ref as _is_ref,
    is_sha256 as _is_sha256,
)


_REQUIRED_PAYLOADS = {
    "evidence/git.json",
    "evidence/host.json",
    "evidence/selection.json",
    "git/repository.bundle",
    "snapshot/index.json",
}


def validate_package_semantics(
    manifest: dict[str, object],
    manifest_bytes: bytes,
    contents: dict[str, bytes],
) -> tuple[
    tuple[tuple[str, str], ...],
    tuple[dict[str, object], ...],
]:
    """Validate every bounded evidence contract and cross-reference."""

    if canonical_json(manifest) != manifest_bytes:
        _fail()
    if set(manifest) != {
        "schema_version",
        "review_fingerprint",
        "files",
        "snapshot_records",
        "refs",
        "worktrees",
    }:
        _fail()
    if manifest["schema_version"] != "MigrationEvidencePackageV1":
        _fail()
    review_fingerprint = manifest["review_fingerprint"]
    if not _is_sha256(review_fingerprint):
        _fail()
    if not _REQUIRED_PAYLOADS.issubset(contents):
        _fail()
    refs = _refs(manifest["refs"])
    worktrees = _worktrees(manifest["worktrees"], refs)
    git_evidence, host_evidence, selection, snapshot = _evidence_objects(contents)
    _validate_git(git_evidence, refs, worktrees)
    _validate_host(host_evidence)
    _validate_review_fingerprint(
        review_fingerprint,
        selection,
        git_evidence,
        host_evidence,
    )
    validate_selection_and_snapshot(
        review_fingerprint=review_fingerprint,
        selection=selection,
        snapshot=snapshot,
        manifest_records=manifest["snapshot_records"],
        worktrees=worktrees,
        contents=contents,
    )
    _require_known_payloads(contents)
    return refs, worktrees


def _evidence_objects(
    contents: dict[str, bytes],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    return (
        _strict_object(contents["evidence/git.json"]),
        _strict_object(contents["evidence/host.json"]),
        _strict_object(contents["evidence/selection.json"]),
        _strict_object(contents["snapshot/index.json"]),
    )


def _require_known_payloads(contents: dict[str, bytes]) -> None:
    allowed = _REQUIRED_PAYLOADS | {
        path
        for path in contents
        if path.startswith("snapshot/index/")
        or path.startswith("snapshot/worktree/")
    }
    if set(contents) != allowed:
        _fail()


def _strict_object(payload: bytes) -> dict[str, object]:
    value = strict_json(payload)
    if canonical_json(value) != payload:
        _fail()
    return value


def _refs(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not list or not 1 <= len(value) <= 128:
        _fail()
    refs: list[tuple[str, str]] = []
    for item in value:
        if type(item) is not dict or set(item) != {"name", "oid"}:
            _fail()
        name, oid = item["name"], item["oid"]
        if not _is_ref(name) or not _is_oid(oid):
            _fail()
        refs.append((oid, name))
    if refs != sorted(refs, key=lambda item: item[1]):
        _fail()
    if len({name for _, name in refs}) != len(refs):
        _fail()
    return tuple(refs)


def _worktrees(
    value: object,
    refs: tuple[tuple[str, str], ...],
) -> tuple[dict[str, object], ...]:
    if type(value) is not list or not 1 <= len(value) <= 64:
        _fail()
    required = {
        "path_sha256",
        "branch_ref",
        "head_oid",
        "status_sha256",
        "status_count",
        "is_main",
    }
    ref_map = {name: oid for oid, name in refs}
    records: list[dict[str, object]] = []
    for item in value:
        if type(item) is not dict or set(item) != required:
            _fail()
        if (
            not _is_sha256(item["path_sha256"])
            or not _is_ref(item["branch_ref"])
            or not _is_oid(item["head_oid"])
            or not _is_sha256(item["status_sha256"])
            or type(item["status_count"]) is not int
            or type(item["status_count"]) is bool
            or not 0 <= item["status_count"] <= 2048
            or type(item["is_main"]) is not bool
        ):
            _fail()
        if ref_map.get(item["branch_ref"]) != item["head_oid"]:
            _fail()
        records.append(item)
    keys = [
        (item["path_sha256"], item["branch_ref"])
        for item in records
    ]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        _fail()
    if sum(item["is_main"] is True for item in records) != 1:
        _fail()
    return tuple(records)


def _validate_git(
    value: dict[str, object],
    refs: tuple[tuple[str, str], ...],
    worktrees: tuple[dict[str, object], ...],
) -> None:
    if set(value) != {
        "schema_version",
        "branch_ref",
        "head_oid",
        "upstream_ref",
        "ahead",
        "behind",
        "remotes",
        "refs",
        "worktrees",
    }:
        _fail()
    if (
        value["schema_version"] != 1
        or not _is_ref(value["branch_ref"])
        or not _is_oid(value["head_oid"])
        or type(value["upstream_ref"]) is not str
        or len(value["upstream_ref"]) > 256
        or not _bounded_count(value["ahead"], 1_000_000)
        or not _bounded_count(value["behind"], 1_000_000)
    ):
        _fail()
    ref_list = [
        {"name": name, "oid": oid}
        for oid, name in refs
    ]
    if value["refs"] != ref_list or value["worktrees"] != list(worktrees):
        _fail()
    ref_map = {name: oid for oid, name in refs}
    if ref_map.get(value["branch_ref"]) != value["head_oid"]:
        _fail()
    _validate_remotes(value["remotes"])


def _validate_remotes(value: object) -> None:
    if type(value) is not list or len(value) > 16:
        _fail()
    names: list[str] = []
    for item in value:
        if type(item) is not dict or set(item) != {
            "name",
            "url_sha256",
            "fetch_sha256",
        }:
            _fail()
        name = item["name"]
        if (
            type(name) is not str
            or not name
            or len(name) > 64
            or not name.replace("-", "").replace("_", "").isalnum()
            or not _is_sha256(item["url_sha256"])
            or not _is_sha256(item["fetch_sha256"])
        ):
            _fail()
        names.append(name)
    if names != sorted(names) or len(set(names)) != len(names):
        _fail()


def _validate_host(value: dict[str, object]) -> None:
    if set(value) != {
        "schema_version",
        "acl_sha256",
        "acl_entry_count",
        "volume_sha256",
        "filesystem_name",
        "drive_type",
        "evidence_complete",
        "content_observed",
    }:
        _fail()
    if (
        value["schema_version"] != 1
        or not _is_sha256(value["acl_sha256"])
        or not _bounded_count(value["acl_entry_count"], 4096)
        or not _is_sha256(value["volume_sha256"])
        or value["filesystem_name"] != "NTFS"
        or value["drive_type"] != "fixed"
        or value["evidence_complete"] is not True
        or value["content_observed"] is not False
    ):
        _fail()


def _validate_review_fingerprint(
    expected: str,
    selection: dict[str, object],
    git: dict[str, object],
    host: dict[str, object],
) -> None:
    baseline = {
        key: git[key]
        for key in (
            "branch_ref",
            "head_oid",
            "upstream_ref",
            "ahead",
            "behind",
            "remotes",
        )
    }
    core = {
        "schema_version": 1,
        "repository_path_sha256": selection["repository_path_sha256"],
        "target_path_sha256": selection["target_path_sha256"],
        "dirty_entries": selection["entries"],
        "reviewed_refs": git["refs"],
        "worktrees": git["worktrees"],
        "git_baseline": baseline,
        "host_baseline": host,
    }
    actual = hashlib.sha256(canonical_json(core)).hexdigest()
    if actual != expected:
        _fail()
