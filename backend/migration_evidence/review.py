"""Operator-review preparation for a migration evidence package."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .contract import (
    DirtyDisposition,
    DirtyEntryReview,
    DirtyReason,
    HostBaseline,
    MigrationEvidenceReview,
)
from .errors import MigrationEvidenceError
from .git_discovery import (
    git_baseline,
    repository_root,
    require_plain_index,
    reviewed_refs,
    reviewed_worktrees,
    status_records,
)
from .policy import inclusion_reason, require_approved_source, validate_relative_path
from .path_checks import require_non_reparse_parent


_HEX = frozenset("0123456789abcdef")


def prepare_migration_evidence_review(
    *,
    repository_root: Path,
    target: Path,
    approved_dirty_paths: tuple[str, ...],
    reviewed_refs: tuple[str, ...],
    approved_worktrees: tuple[Path, ...],
    host_baseline: HostBaseline,
) -> MigrationEvidenceReview:
    """Discover exact live scope for a separate operator confirmation."""

    try:
        return _prepare_review(
            repository_root,
            target,
            approved_dirty_paths,
            reviewed_refs,
            approved_worktrees,
            host_baseline,
        )
    except MigrationEvidenceError:
        raise
    except Exception:
        raise MigrationEvidenceError() from None


def _prepare_review(
    source: Path,
    target: Path,
    approved_paths: tuple[str, ...],
    ref_names: tuple[str, ...],
    worktree_paths: tuple[Path, ...],
    host: HostBaseline,
) -> MigrationEvidenceReview:
    normalized_target = _validate_target(target)
    _validate_host_baseline(host)
    approved = _validate_approved_paths(approved_paths)
    root = globals()["repository_root"](source)
    _require_external_target(normalized_target, (root,))
    require_plain_index(root)
    dirty_entries = _review_dirty_entries(status_records(root), approved)
    refs = globals()["reviewed_refs"](root, ref_names)
    worktrees = globals()["reviewed_worktrees"](root, worktree_paths, refs)
    _require_external_target(
        normalized_target,
        tuple(item.path for item in worktrees),
    )
    baseline = git_baseline(root)
    core = _review_mapping(
        root, normalized_target, dirty_entries, refs, worktrees, baseline, host
    )
    return MigrationEvidenceReview(
        schema_version=1,
        repository_root=root,
        target=normalized_target,
        dirty_entries=dirty_entries,
        reviewed_refs=refs,
        worktrees=worktrees,
        git_baseline=baseline,
        host_baseline=host,
        review_fingerprint=hashlib.sha256(_canonical_json(core)).hexdigest(),
    )


def _validate_target(target: Path) -> Path:
    if not isinstance(target, Path) or not target.is_absolute():
        raise MigrationEvidenceError()
    if target.name.endswith(".migration-evidence.zip") is False:
        raise MigrationEvidenceError()
    return require_non_reparse_parent(target)


def _validate_host_baseline(value: HostBaseline) -> None:
    if type(value) is not HostBaseline or value.schema_version != 1:
        raise MigrationEvidenceError()
    if not _is_sha256(value.acl_sha256) or not _is_sha256(value.volume_sha256):
        raise MigrationEvidenceError()
    if type(value.acl_entry_count) is not int or not 0 <= value.acl_entry_count <= 4096:
        raise MigrationEvidenceError()
    if value.filesystem_name != "NTFS" or value.drive_type != "fixed":
        raise MigrationEvidenceError()
    if value.evidence_complete is not True or value.content_observed is not False:
        raise MigrationEvidenceError()


def _require_external_target(
    target: Path,
    worktrees: tuple[Path, ...],
) -> None:
    if any(
        target == worktree or worktree in target.parents
        for worktree in worktrees
    ):
        raise MigrationEvidenceError()


def _validate_approved_paths(values: tuple[str, ...]) -> frozenset[str]:
    if type(values) is not tuple or len(values) > 256 or len(set(values)) != len(values):
        raise MigrationEvidenceError()
    approved = frozenset(require_approved_source(value) for value in values)
    if len(approved) != len(values):
        raise MigrationEvidenceError()
    return approved


def _review_dirty_entries(
    records: tuple[tuple[str, str], ...],
    approved: frozenset[str],
) -> tuple[DirtyEntryReview, ...]:
    entries: list[DirtyEntryReview] = []
    discovered_approved: set[str] = set()
    for status, path in records:
        _require_supported_status(status)
        validate_relative_path(path)
        ignored = status == "!!"
        tracked = status not in {"!!", "??"}
        if path in approved:
            if ignored:
                raise MigrationEvidenceError()
            disposition = DirtyDisposition.INCLUDED
            reason = DirtyReason.APPROVED_SOURCE
            discovered_approved.add(path)
        else:
            disposition = DirtyDisposition.EXCLUDED
            reason = inclusion_reason(path, ignored=ignored)
        entries.append(
            DirtyEntryReview(
                path=path,
                status=status,
                tracked=tracked,
                ignored=ignored,
                disposition=disposition,
                reason=reason,
            )
        )
    if discovered_approved != set(approved):
        raise MigrationEvidenceError()
    return tuple(entries)


def _require_supported_status(status: str) -> None:
    if status in {"??", "!!"}:
        return
    unmerged = {"AA", "AU", "DD", "DU", "UA", "UD", "UU"}
    if (
        type(status) is not str
        or len(status) != 2
        or status in unmerged
        or status == "  "
        or any(character not in " MAD" for character in status)
    ):
        raise MigrationEvidenceError()


def _review_mapping(root, target, entries, refs, worktrees, baseline, host) -> dict[str, object]:
    return {
        "schema_version": 1,
        "repository_path_sha256": _path_sha256(root),
        "target_path_sha256": _path_sha256(target),
        "dirty_entries": [
            {
                "path": item.path,
                "status": item.status,
                "tracked": item.tracked,
                "ignored": item.ignored,
                "disposition": item.disposition.value,
                "reason": item.reason.value,
            }
            for item in entries
        ],
        "reviewed_refs": [{"name": item.name, "oid": item.oid} for item in refs],
        "worktrees": [
            {
                "path_sha256": item.path_sha256,
                "branch_ref": item.branch_ref,
                "head_oid": item.head_oid,
                "status_sha256": item.status_sha256,
                "status_count": item.status_count,
                "is_main": item.is_main,
            }
            for item in sorted(
                worktrees,
                key=lambda value: value.path_sha256,
            )
        ],
        "git_baseline": _git_mapping(baseline),
        "host_baseline": _host_mapping(host),
    }


def _git_mapping(value) -> dict[str, object]:
    return {
        "branch_ref": value.branch_ref,
        "head_oid": value.head_oid,
        "upstream_ref": value.upstream_ref,
        "ahead": value.ahead,
        "behind": value.behind,
        "remotes": [
            {
                "name": remote.name,
                "url_sha256": remote.url_sha256,
                "fetch_sha256": remote.fetch_sha256,
            }
            for remote in value.remotes
        ],
    }


def _host_mapping(value: HostBaseline) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "acl_sha256": value.acl_sha256,
        "acl_entry_count": value.acl_entry_count,
        "volume_sha256": value.volume_sha256,
        "filesystem_name": value.filesystem_name,
        "drive_type": value.drive_type,
        "evidence_complete": value.evidence_complete,
        "content_observed": value.content_observed,
    }


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _is_sha256(value: object) -> bool:
    return type(value) is str and len(value) == 64 and set(value) <= _HEX


def _path_sha256(path: Path) -> str:
    normalized = os.path.normcase(str(path))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
