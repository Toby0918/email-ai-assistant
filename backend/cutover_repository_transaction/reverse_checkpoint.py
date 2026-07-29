"""Exact filesystem and topology checks for stable reverse checkpoints."""

from __future__ import annotations

from pathlib import Path

from .errors import RepositoryTransactionError
from .failed_evidence import (
    verify_failed_new_objects,
    verify_partial_failed_object,
)
from .journal_types import ForwardBoundary
from .reverse_plan import reverse_stage_plan
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)


def verify_resume_checkpoint(
    scope,
    stage: ForwardBoundary,
    progress: int,
) -> None:
    plan = reverse_stage_plan(stage)
    if progress == 0:
        from .verification import verify_forward_stage

        verify_forward_stage(scope, stage, ())
        return
    if progress < plan.preserve_last or progress > plan.final_index:
        _fail()
    if progress == plan.final_index:
        verify_reverse_final(scope, stage)
        return
    _verify_retained_failed_state(scope, plan, progress)
    _verify_repository_position(scope, plan, progress)
    _verify_original_worktrees(scope, plan, progress)


def reverse_main_source(scope, stage: ForwardBoundary) -> Path:
    scenario = scope.review.scenario
    if stage in {
        ForwardBoundary.MAIN_PUBLISHED,
        ForwardBoundary.WORKTREES_RECREATED,
        ForwardBoundary.REPOSITORY_FINAL_VERIFIED,
    }:
        return Path(scenario.failed_container) / "main"
    return Path(scenario.legacy)


def verify_reverse_final(scope, stage: ForwardBoundary) -> None:
    from .verification import (
        verify_partial_reverse_topology,
        verify_reverse_topology,
    )

    if stage in {
        ForwardBoundary.WORKTREES_RECREATED,
        ForwardBoundary.REPOSITORY_FINAL_VERIFIED,
    }:
        verify_reverse_topology(scope)
    else:
        verify_partial_reverse_topology(scope, stage)


def _verify_retained_failed_state(scope, plan, progress) -> None:
    main_extracted = (
        plan.main_index is not None and progress >= plan.main_index
    )
    if plan.preserve_kind == "full":
        verify_failed_new_objects(
            scope, main_extracted=main_extracted
        )
        from .container_audit_bridge import (
            require_reverse_failed_policy_seam,
        )

        require_reverse_failed_policy_seam(
            scope, main_extracted=main_extracted
        )
    elif plan.preserve_kind == "container":
        verify_partial_failed_object(
            scope,
            plan.stage,
            main_extracted=main_extracted,
        )


def _verify_repository_position(scope, plan, progress) -> None:
    repository = (
        reverse_main_source(scope, plan.stage)
        if plan.main_index is not None and progress < plan.main_index
        else Path(scope.review.scenario.source)
    )
    if (
        directory_identity(repository)
        != scope.review.repository_object_identity
        or directory_identity(repository / ".git")
        != scope.review.common_object_identity
    ):
        _fail()


def _verify_original_worktrees(scope, plan, progress) -> None:
    scenario = scope.review.scenario
    admin_restored = _restored_count(
        progress, plan.admin_first, plan.admin_last
    )
    physical_restored = _restored_count(
        progress, plan.physical_first, plan.physical_last
    )
    remaining_admin: set[str] = set()
    remaining_physical: set[str] = set()
    for index, item in enumerate(scope.review.observations):
        if index < admin_restored:
            admin = item.admin
        else:
            admin = Path(scenario.admin_preservation) / item.paths.role
            remaining_admin.add(item.paths.role)
        if index < physical_restored:
            physical = item.paths.original
        else:
            physical = (
                Path(scenario.worktree_preservation) / item.paths.role
            )
            remaining_physical.add(item.paths.role)
        _require_identity_and_content(
            admin, item.admin_identity, item.admin_content
        )
        if directory_identity(physical) != item.physical_identity:
            _fail()
    _require_exact_names(
        Path(scenario.admin_preservation), remaining_admin
    )
    _require_exact_names(
        Path(scenario.worktree_preservation), remaining_physical
    )


def _restored_count(
    progress: int,
    first: int | None,
    last: int | None,
) -> int:
    if first is None or last is None:
        return 11
    if progress < first:
        return 0
    return min(11, progress - first + 1)


def _require_identity_and_content(path, identity, content) -> None:
    if (
        directory_identity(path) != identity
        or opaque_directory_fingerprint(path) != content
    ):
        _fail()


def _require_exact_names(parent: Path, expected: set[str]) -> None:
    if (
        not parent.is_dir()
        or parent.is_symlink()
        or {item.name for item in parent.iterdir()} != expected
    ):
        _fail()


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_reverse_resume_invalid"
    ) from None
