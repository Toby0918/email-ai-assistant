"""Build one reviewed Git and dirty-source migration evidence package."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from .contract import (
    MigrationEvidenceCounts,
    MigrationEvidenceResult,
    MigrationEvidenceReview,
    MigrationEvidenceStatus,
)
from .errors import MigrationEvidenceError
from .git_discovery import git_output
from .manifest import build_archive, canonical_json
from .publication import publish_new_package
from .review import prepare_migration_evidence_review
from .snapshot import capture_snapshot, read_checked_file


def create_migration_evidence_package(
    *,
    review: MigrationEvidenceReview,
    confirmed_review_fingerprint: str,
) -> MigrationEvidenceResult:
    """Create one complete package after exact separate-plan confirmation."""

    try:
        _validate_confirmation(review, confirmed_review_fingerprint)
        _require_review_stable(review)
        with tempfile.TemporaryDirectory(prefix="migration-evidence-") as temporary:
            temporary_root = Path(temporary).resolve()
            bundle = _create_and_verify_bundle(review, temporary_root)
            snapshot_records, snapshot_payloads = capture_snapshot(review)
            _require_review_stable(review)
            payloads = _package_payloads(review, bundle, snapshot_payloads, snapshot_records)
            archive = build_archive(
                review_fingerprint=review.review_fingerprint,
                payloads=payloads,
                snapshot_records=snapshot_records,
                refs=tuple({"name": item.name, "oid": item.oid} for item in review.reviewed_refs),
                worktrees=_worktree_mappings(review),
            )
        publish_new_package(review.target, archive)
        _require_published_package_valid(review.target)
        return _success_result(
            MigrationEvidenceStatus.CREATED,
            len(payloads),
            len(review.reviewed_refs),
            len(review.worktrees),
        )
    except BaseException:
        return _failure_result()


def _validate_confirmation(review, confirmed: str) -> None:
    if type(review) is not MigrationEvidenceReview:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    if type(confirmed) is not str or confirmed != review.review_fingerprint:
        raise MigrationEvidenceError("migration_evidence_create_failed")


def _require_published_package_valid(target: Path) -> None:
    from .verification import verify_migration_evidence_package

    result = verify_migration_evidence_package(package=target)
    if result.status is not MigrationEvidenceStatus.VERIFIED:
        raise MigrationEvidenceError("migration_evidence_create_failed")


def _require_review_stable(review: MigrationEvidenceReview) -> None:
    included = tuple(
        item.path
        for item in review.dirty_entries
        if item.disposition.value == "included"
    )
    current = prepare_migration_evidence_review(
        repository_root=review.repository_root,
        target=review.target,
        approved_dirty_paths=included,
        reviewed_refs=tuple(item.name for item in review.reviewed_refs),
        approved_worktrees=tuple(item.path for item in review.worktrees),
        host_baseline=review.host_baseline,
    )
    if current != review:
        raise MigrationEvidenceError("migration_evidence_create_failed")


def _create_and_verify_bundle(review, temporary_root: Path) -> bytes:
    bundle = temporary_root / "repository.bundle"
    refs = tuple(item.name for item in review.reviewed_refs)
    git_output(review.repository_root, ("bundle", "create", str(bundle), *refs))
    if not bundle.is_file() or bundle.stat().st_size > 192 * 1024 * 1024:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    verify_repository = temporary_root / "verify.git"
    git_output(temporary_root, ("init", "--bare", str(verify_repository)))
    git_output(verify_repository, ("bundle", "verify", str(bundle)))
    heads = git_output(verify_repository, ("bundle", "list-heads", str(bundle)))
    assert heads is not None
    if _parse_bundle_heads(heads) != tuple((item.oid, item.name) for item in review.reviewed_refs):
        raise MigrationEvidenceError("migration_evidence_create_failed")
    return bundle.read_bytes()


def _parse_bundle_heads(payload: bytes) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise MigrationEvidenceError("migration_evidence_create_failed") from None
    for line in lines:
        oid, separator, name = line.partition(" ")
        if not separator or len(oid) != 40 or not name.startswith("refs/heads/"):
            raise MigrationEvidenceError("migration_evidence_create_failed")
        values.append((oid, name))
    return tuple(sorted(values, key=lambda item: item[1]))


def _package_payloads(review, bundle, snapshots, records) -> dict[str, bytes]:
    return {
        "git/repository.bundle": bundle,
        "evidence/git.json": canonical_json(_git_evidence(review)),
        "evidence/host.json": canonical_json(_host_evidence(review)),
        "evidence/selection.json": canonical_json(
            _selection_evidence(review)
        ),
        "snapshot/index.json": canonical_json(
            _snapshot_index(review, records)
        ),
        **snapshots,
    }


def _git_evidence(review: MigrationEvidenceReview) -> dict[str, object]:
    return {
        "schema_version": 1,
        "branch_ref": review.git_baseline.branch_ref,
        "head_oid": review.git_baseline.head_oid,
        "upstream_ref": review.git_baseline.upstream_ref,
        "ahead": review.git_baseline.ahead,
        "behind": review.git_baseline.behind,
        "remotes": [
            {
                "name": item.name,
                "url_sha256": item.url_sha256,
                "fetch_sha256": item.fetch_sha256,
            }
            for item in review.git_baseline.remotes
        ],
        "refs": [{"name": item.name, "oid": item.oid} for item in review.reviewed_refs],
        "worktrees": list(_worktree_mappings(review)),
    }


def _host_evidence(review: MigrationEvidenceReview) -> dict[str, object]:
    return {
        "schema_version": review.host_baseline.schema_version,
        "acl_sha256": review.host_baseline.acl_sha256,
        "acl_entry_count": review.host_baseline.acl_entry_count,
        "volume_sha256": review.host_baseline.volume_sha256,
        "filesystem_name": review.host_baseline.filesystem_name,
        "drive_type": review.host_baseline.drive_type,
        "evidence_complete": review.host_baseline.evidence_complete,
        "content_observed": review.host_baseline.content_observed,
    }


def _snapshot_index(
    review: MigrationEvidenceReview,
    records,
) -> dict[str, object]:
    index_records = [_snapshot_mapping(item) for item in records]
    main_worktree = next(
        (item for item in review.worktrees if item.is_main),
        None,
    )
    if main_worktree is None:
        raise MigrationEvidenceError("migration_evidence_create_failed")
    return {
        "schema_version": "DirtySourceSnapshotV1",
        "source_worktree_path_sha256": main_worktree.path_sha256,
        "records": index_records,
    }


def _selection_evidence(
    review: MigrationEvidenceReview,
) -> dict[str, object]:
    return {
        "schema_version": "DirtySourceSelectionV1",
        "review_fingerprint": review.review_fingerprint,
        "repository_path_sha256": _path_hash(review.repository_root),
        "target_path_sha256": _path_hash(review.target),
        "entries": [
            {
                "path": item.path,
                "status": item.status,
                "tracked": item.tracked,
                "ignored": item.ignored,
                "disposition": item.disposition.value,
                "reason": item.reason.value,
            }
            for item in review.dirty_entries
        ],
    }


def _worktree_mapping(item) -> dict[str, object]:
    return {
        "path_sha256": item.path_sha256,
        "branch_ref": item.branch_ref,
        "head_oid": item.head_oid,
        "status_sha256": item.status_sha256,
        "status_count": item.status_count,
        "is_main": item.is_main,
    }


def _worktree_mappings(
    review: MigrationEvidenceReview,
) -> tuple[dict[str, object], ...]:
    values = (_worktree_mapping(item) for item in review.worktrees)
    return tuple(sorted(values, key=lambda item: item["path_sha256"]))


def _snapshot_mapping(item) -> dict[str, object]:
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


def _path_hash(path: Path) -> str:
    normalized = os.path.normcase(str(path))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _success_result(status, files, refs, worktrees) -> MigrationEvidenceResult:
    return MigrationEvidenceResult(
        status=status,
        counts=MigrationEvidenceCounts(
            packages=1,
            verified=1 if status is MigrationEvidenceStatus.VERIFIED else 0,
            rejected=0,
            files=files,
            refs=refs,
            worktrees=worktrees,
        ),
    )


def _failure_result() -> MigrationEvidenceResult:
    return MigrationEvidenceResult(
        status=MigrationEvidenceStatus.FAILED,
        counts=MigrationEvidenceCounts(
            packages=0,
            verified=0,
            rejected=1,
            files=0,
            refs=0,
            worktrees=0,
        ),
    )
