"""The only Issue #36 bridge to the Issue #35 evidence contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

from backend.migration_evidence import (
    HostBaseline,
    MigrationEvidenceReview,
    MigrationEvidenceStatus,
    RemoteBaseline,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
    verify_migration_evidence_package,
)

from .errors import RehearsalError
from .git_runner import git_output
from .synthetic_project import REVIEWED_DIRTY, SyntheticProject


def prepare_synthetic_evidence(
    project: SyntheticProject,
) -> MigrationEvidenceReview:
    """Capture the exact fixed synthetic source selection."""

    refs = _local_branch_refs(project.scope, project.source)
    review = prepare_migration_evidence_review(
        repository_root=project.source,
        target=project.evidence_target,
        approved_dirty_paths=REVIEWED_DIRTY,
        reviewed_refs=refs,
        approved_worktrees=(
            project.source,
            *(path for _, path in project.old_worktrees),
        ),
        host_baseline=_synthetic_host_baseline(),
    )
    if tuple(item.name for item in review.reviewed_refs) != refs:
        raise RehearsalError()
    if review.git_baseline.remotes != (
        RemoteBaseline(
            name="origin",
            url_sha256=hashlib.sha256(
                str(project.remote).encode("utf-8")
            ).hexdigest(),
            fetch_sha256=hashlib.sha256(
                b"+refs/heads/*:refs/remotes/origin/*"
            ).hexdigest(),
        ),
    ):
        raise RehearsalError()
    return review


def create_and_verify_synthetic_evidence(
    review: MigrationEvidenceReview,
) -> None:
    """Create and independently verify exactly one synthetic package."""

    created = create_migration_evidence_package(
        review=review,
        confirmed_review_fingerprint=review.review_fingerprint,
    )
    if created.status is not MigrationEvidenceStatus.CREATED:
        raise RehearsalError()
    require_verified_evidence(review.target)


def require_verified_evidence(package: Path) -> None:
    verified = verify_migration_evidence_package(package=package)
    if verified.status is not MigrationEvidenceStatus.VERIFIED:
        raise RehearsalError()


def prepare_post_reparenting_review(
    *,
    project: SyntheticProject,
    main: Path,
    worktrees: tuple[Path, ...],
) -> MigrationEvidenceReview:
    """Recapture comparable Git state without creating another package."""

    target = project.evidence_target.parent / (
        "postcheck.migration-evidence.zip"
    )
    return prepare_migration_evidence_review(
        repository_root=main,
        target=target,
        approved_dirty_paths=REVIEWED_DIRTY,
        reviewed_refs=_local_branch_refs(project.scope, main),
        approved_worktrees=(main, *worktrees),
        host_baseline=_synthetic_host_baseline(),
    )


def _local_branch_refs(scope: Path, repository: Path) -> tuple[str, ...]:
    output = git_output(
        scope,
        repository,
        ("for-each-ref", "--format=%(refname)", "refs/heads"),
    )
    refs = tuple(sorted(line for line in output.splitlines() if line))
    expected = (
        "refs/heads/master",
        "refs/heads/synthetic-alpha",
        "refs/heads/synthetic-beta",
    )
    if refs != expected:
        raise RehearsalError()
    return refs


def _synthetic_host_baseline() -> HostBaseline:
    return HostBaseline(
        schema_version=1,
        acl_sha256=hashlib.sha256(
            b"issue36-synthetic-acl"
        ).hexdigest(),
        acl_entry_count=1,
        volume_sha256=hashlib.sha256(
            b"issue36-synthetic-volume"
        ).hexdigest(),
        filesystem_name="NTFS",
        drive_type="fixed",
        evidence_complete=True,
        content_observed=False,
    )
