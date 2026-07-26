"""Post-publication and rollback verification for the synthetic rehearsal."""

from __future__ import annotations

from pathlib import Path

from .baseline import (
    LinkedWorktreeBaseline,
    RepositoryBaseline,
    current_branch,
    current_common_identity,
    current_head,
    current_index_hash,
    current_status_hash,
    directory_identity,
    require_excluded_objects,
    require_source_hashes,
)
from .contract import (
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
)
from .errors import RehearsalError
from .evidence_bridge import (
    prepare_post_reparenting_review,
    require_verified_evidence,
)
from .git_runner import git_output
from .layout import require_managed_synthetic_layout
from .publication import PublishedRepository
from .synthetic_project import (
    SyntheticProject,
    require_synthetic_remote,
)
from .worktrees import PublishedWorktrees


def require_original_source(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
) -> None:
    """Prove an early rollback restored the original synthetic source."""

    require_synthetic_remote(project, repository=project.source)
    if (
        not project.source.is_dir()
        or project.legacy.exists()
        or directory_identity(project.source) != baseline.source_identity
        or current_common_identity(project, project.source)
        != baseline.common_identity
        or current_index_hash(project, project.source)
        != baseline.index_sha256
        or current_status_hash(project, project.source)
        != baseline.status_sha256
    ):
        raise RehearsalError()
    require_source_hashes(project.source, baseline)
    require_excluded_objects(project.source, baseline)
    require_verified_evidence(project.evidence_target)


def require_verified_rollback_path(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    repository: PublishedRepository,
) -> None:
    """Prove preserved legacy plus new main remain independently recoverable."""

    if (
        not repository.container.is_dir()
        or not repository.legacy.is_dir()
        or not repository.main.is_dir()
        or directory_identity(repository.legacy)
        != baseline.source_identity
        or current_common_identity(project, repository.main)
        != baseline.common_identity
        or current_index_hash(project, repository.main)
        != baseline.index_sha256
        or current_status_hash(project, repository.main)
        != baseline.status_sha256
    ):
        raise RehearsalError()
    require_source_hashes(repository.main, baseline)
    require_excluded_objects(repository.legacy, baseline)
    require_verified_evidence(project.evidence_target)


def require_reparented_state(
    *,
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    repository: PublishedRepository,
    worktrees: PublishedWorktrees,
    choices: tuple[ReviewedWorktreeChoice, ...],
) -> None:
    """Compare every Issue #36 postcondition with the captured baseline."""

    require_verified_rollback_path(project, baseline, repository)
    require_managed_synthetic_layout(
        container=repository.container,
        main=repository.main,
        legacy=repository.legacy,
    )
    post = prepare_post_reparenting_review(
        project=project,
        main=repository.main,
        worktrees=tuple(
            worktrees.path(item) for item in SyntheticWorktree
        ),
    )
    _require_review_matches(post, baseline)
    _require_main_review(post, baseline)
    _require_worktrees(project, baseline, worktrees, choices)
    _require_exact_worktree_roster(project, repository, worktrees)


def require_unpublished_rollback_state(
    *,
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    repository: PublishedRepository,
) -> None:
    """Verify a relocated main plus the original linked worktrees."""

    require_verified_rollback_path(project, baseline, repository)
    paths = tuple(item.path for item in baseline.linked_worktrees)
    post = prepare_post_reparenting_review(
        project=project,
        main=repository.main,
        worktrees=paths,
    )
    _require_review_matches(post, baseline)
    _require_main_review(post, baseline)
    for expected in baseline.linked_worktrees:
        status = git_output(
            project.scope,
            expected.path,
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        )
        if (
            current_branch(project, expected.path) != expected.branch_ref
            or current_head(project, expected.path) != expected.head_oid
            or current_common_identity(project, expected.path)
            != baseline.common_identity
            or directory_identity(expected.path)
            != expected.directory_identity
            or status != ""
        ):
            raise RehearsalError()


def require_relocated_reparented_state(
    *,
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    repository: PublishedRepository,
    worktrees: PublishedWorktrees,
    choices: tuple[ReviewedWorktreeChoice, ...],
) -> None:
    """Verify a complete topology at the unique rollback path."""

    require_verified_rollback_path(project, baseline, repository)
    post = prepare_post_reparenting_review(
        project=project,
        main=repository.main,
        worktrees=tuple(
            worktrees.path(item) for item in SyntheticWorktree
        ),
    )
    _require_review_matches(post, baseline)
    _require_main_review(post, baseline)
    _require_worktrees(project, baseline, worktrees, choices)
    _require_exact_worktree_roster(project, repository, worktrees)


def _require_review_matches(
    post: object,
    baseline: RepositoryBaseline,
) -> None:
    if (
        post.git_baseline != baseline.review.git_baseline
        or post.reviewed_refs != baseline.review.reviewed_refs
        or _included_dirty(post) != _included_dirty(baseline.review)
    ):
        raise RehearsalError()


def _included_dirty(review: object) -> tuple[tuple[object, ...], ...]:
    values = getattr(review, "dirty_entries", ())
    return tuple(
        (
            item.path,
            item.status,
            item.tracked,
            item.ignored,
            item.disposition,
            item.reason,
        )
        for item in values
        if item.disposition.value == "included"
    )


def _require_main_review(
    post: object,
    baseline: RepositoryBaseline,
) -> None:
    worktrees = getattr(post, "worktrees", ())
    main = tuple(item for item in worktrees if item.is_main)
    baseline_main = tuple(
        item for item in baseline.review.worktrees if item.is_main
    )
    if (
        len(main) != 1
        or len(baseline_main) != 1
        or main[0].branch_ref != baseline_main[0].branch_ref
        or main[0].head_oid != baseline_main[0].head_oid
    ):
        raise RehearsalError()


def _require_worktrees(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    published: PublishedWorktrees,
    choices: tuple[ReviewedWorktreeChoice, ...],
) -> None:
    choice_map = {choice.worktree: choice.strategy for choice in choices}
    common = baseline.common_identity
    for item in SyntheticWorktree:
        expected = baseline.linked(item)
        path = published.path(item)
        status = git_output(
            project.scope,
            path,
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
        )
        if (
            current_branch(project, path) != expected.branch_ref
            or current_head(project, path) != expected.head_oid
            or current_common_identity(project, path) != common
            or status != ""
        ):
            raise RehearsalError()
        _require_strategy_preservation(
            expected,
            path,
            choice_map.get(item),
            published,
        )


def _require_strategy_preservation(
    expected: LinkedWorktreeBaseline,
    active_path: Path,
    strategy: WorktreeStrategy | None,
    published: PublishedWorktrees,
) -> None:
    original_path = expected.path
    original_identity = expected.directory_identity
    if strategy is WorktreeStrategy.REPAIR:
        if (
            directory_identity(active_path) != original_identity
            or original_path.exists()
        ):
            raise RehearsalError()
    elif strategy is WorktreeStrategy.RECREATE:
        if (
            not original_path.is_dir()
            or directory_identity(original_path) != original_identity
            or original_path not in published.preserved_originals
            or not all(path.is_dir() for path in published.preserved_admin)
        ):
            raise RehearsalError()
    else:
        raise RehearsalError()


def _require_exact_worktree_roster(
    project: SyntheticProject,
    repository: PublishedRepository,
    worktrees: PublishedWorktrees,
) -> None:
    output = git_output(
        project.scope,
        repository.main,
        ("worktree", "list", "--porcelain", "-z"),
    )
    expected = {
        repository.main,
        *(worktrees.path(item) for item in SyntheticWorktree),
    }
    actual = {
        Path(value[len("worktree "):]).resolve(strict=True)
        for value in output.split("\x00")
        if value.startswith("worktree ")
    }
    if actual != expected:
        raise RehearsalError()
