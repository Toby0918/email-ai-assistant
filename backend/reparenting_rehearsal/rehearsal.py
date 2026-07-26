"""Public composition seam for a self-contained synthetic rehearsal."""

from __future__ import annotations

from pathlib import Path
import tempfile

from .audit_bridge import require_passed_container_audit
from .baseline import RepositoryBaseline, capture_repository_baseline
from .contract import (
    COMPLETED_RESULT,
    FAILED_RESULT,
    PublicationBoundary,
    ReparentingRehearsalResult,
    ROLLBACK_VERIFIED_RESULT,
    ReviewedWorktreeChoice,
    SyntheticWorktree,
    WorktreeStrategy,
)
from .evidence_bridge import (
    create_and_verify_synthetic_evidence,
    prepare_synthetic_evidence,
)
from .publication import (
    PublishedRepository,
    publish_container,
    publish_legacy_source,
    publish_main_repository,
    preserve_repository_for_rollback,
    restore_after_container_failure,
    restore_after_legacy_failure,
)
from .synthetic_project import (
    SyntheticProject,
    build_synthetic_project,
    require_synthetic_project,
)
from .verification import (
    require_original_source,
    require_relocated_reparented_state,
    require_reparented_state,
    require_unpublished_rollback_state,
)
from .worktrees import (
    PublishedWorktrees,
    publish_worktrees,
    relocate_published_worktrees,
    repair_worktree_metadata,
)


def _has_complete_choices(
    choices: object,
) -> bool:
    if type(choices) is not tuple:
        return False
    if not all(type(choice) is ReviewedWorktreeChoice for choice in choices):
        return False
    if not all(
        type(choice.worktree) is SyntheticWorktree
        and type(choice.strategy) is WorktreeStrategy
        for choice in choices
    ):
        return False
    worktrees = tuple(choice.worktree for choice in choices)
    return (
        len(worktrees) == len(SyntheticWorktree)
        and set(worktrees) == set(SyntheticWorktree)
    )


def rehearse_repository_reparenting(
    *,
    worktree_choices: tuple[ReviewedWorktreeChoice, ...],
    fail_at: PublicationBoundary | None,
) -> ReparentingRehearsalResult:
    """Run only the fixed synthetic scenario."""

    if not _has_complete_choices(worktree_choices):
        return FAILED_RESULT
    if fail_at is not None and type(fail_at) is not PublicationBoundary:
        return FAILED_RESULT
    try:
        with tempfile.TemporaryDirectory(
            prefix="issue36-synthetic-",
            delete=False,
        ) as temporary:
            return _run_rehearsal(
                Path(temporary),
                worktree_choices,
                fail_at,
            )
    except Exception:
        return FAILED_RESULT


def _run_rehearsal(
    scope: Path,
    choices: tuple[ReviewedWorktreeChoice, ...],
    fail_at: PublicationBoundary | None,
) -> ReparentingRehearsalResult:
    project = build_synthetic_project(scope)
    baseline = _prepare_baseline(project)
    early, repository = _publish_repository(
        project,
        baseline,
        fail_at,
    )
    if early is not None:
        return early
    if repository is None:
        return FAILED_RESULT
    return _publish_worktrees_and_audit(
        project,
        baseline,
        repository,
        choices,
        fail_at,
    )


def _prepare_baseline(
    project: SyntheticProject,
) -> RepositoryBaseline:
    require_synthetic_project(project)
    review = prepare_synthetic_evidence(project)
    require_synthetic_project(project)
    baseline = capture_repository_baseline(project, review)
    require_synthetic_project(project)
    create_and_verify_synthetic_evidence(review)
    require_synthetic_project(project)
    return baseline


def _publish_repository(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    fail_at: PublicationBoundary | None,
) -> tuple[
    ReparentingRehearsalResult | None,
    PublishedRepository | None,
]:
    if fail_at is PublicationBoundary.EVIDENCE_PACKAGE:
        require_original_source(project, baseline)
        return ROLLBACK_VERIFIED_RESULT, None

    publish_legacy_source(project)
    if fail_at is PublicationBoundary.LEGACY_RENAME:
        restore_after_legacy_failure(project)
        require_original_source(project, baseline)
        return ROLLBACK_VERIFIED_RESULT, None

    publish_container(project)
    if fail_at is PublicationBoundary.CONTAINER_PUBLICATION:
        restore_after_container_failure(project)
        require_original_source(project, baseline)
        return ROLLBACK_VERIFIED_RESULT, None

    repository = publish_main_repository(project, baseline)
    if fail_at is PublicationBoundary.MAIN_PUBLICATION:
        repository = preserve_repository_for_rollback(
            project,
            repository,
        )
        repair_worktree_metadata(
            project=project,
            main=repository.main,
            worktrees=tuple(
                item.path for item in baseline.linked_worktrees
            ),
        )
        require_unpublished_rollback_state(
            project=project,
            baseline=baseline,
            repository=repository,
        )
        return ROLLBACK_VERIFIED_RESULT, None
    return None, repository


def _publish_worktrees_and_audit(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    repository: PublishedRepository,
    choices: tuple[ReviewedWorktreeChoice, ...],
    fail_at: PublicationBoundary | None,
) -> ReparentingRehearsalResult:
    worktrees = publish_worktrees(
        project=project,
        repository=repository,
        baseline=baseline,
        choices=choices,
    )
    require_reparented_state(
        project=project,
        baseline=baseline,
        repository=repository,
        worktrees=worktrees,
        choices=choices,
    )
    if fail_at is PublicationBoundary.WORKTREE_PUBLICATION:
        _preserve_published_rollback(
            project,
            baseline,
            repository,
            worktrees,
            choices,
        )
        return ROLLBACK_VERIFIED_RESULT

    require_passed_container_audit(
        project=project,
        repository=repository,
        worktrees=worktrees,
    )
    if fail_at is PublicationBoundary.CONTAINER_AUDIT:
        _preserve_published_rollback(
            project,
            baseline,
            repository,
            worktrees,
            choices,
        )
        return ROLLBACK_VERIFIED_RESULT
    return COMPLETED_RESULT


def _preserve_published_rollback(
    project: SyntheticProject,
    baseline: RepositoryBaseline,
    repository: PublishedRepository,
    worktrees: PublishedWorktrees,
    choices: tuple[ReviewedWorktreeChoice, ...],
) -> None:
    relocated_repository = preserve_repository_for_rollback(
        project,
        repository,
    )
    relocated_worktrees = relocate_published_worktrees(
        worktrees,
        source_container=repository.container,
        rollback_container=relocated_repository.container,
    )
    repair_worktree_metadata(
        project=project,
        main=relocated_repository.main,
        worktrees=tuple(
            relocated_worktrees.path(item)
            for item in SyntheticWorktree
        ),
    )
    require_relocated_reparented_state(
        project=project,
        baseline=baseline,
        repository=relocated_repository,
        worktrees=relocated_worktrees,
        choices=choices,
    )
