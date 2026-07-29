"""Fixed reverse transaction preserving failed new state."""

from __future__ import annotations

from pathlib import Path

from .durable_store import _RepositoryJournalStore
from .forward_recovery import (
    at_least as _at_least,
    committed_forward_stage as _committed_forward_stage,
    reconcile_forward_gap as _reconcile_forward_gap,
)
from .git_recreation import observe_all_recreated
from .failed_evidence import (
    verify_failed_new_objects,
    verify_partial_failed_object,
)
from .journal_types import (
    ForwardBoundary,
    RepositoryMutationKind,
    ReverseBoundary,
)
from .mutation_executor import _TransactionExecutor
from .reverse_resume import (
    has_reverse_records,
    reconcile_reverse_gap,
    reverse_progress,
    verify_resume_checkpoint,
)
from .reverse_plan import reverse_stage_plan
from .scope_models import _SyntheticTransactionScope
from .transaction_types import (
    RepositoryTransactionReceiptV1,
    SyntheticFailureSelectorV1,
    SyntheticTransactionDirection,
)
from .verification import (
    verify_forward_stage,
    verify_partial_reverse_topology,
    verify_reverse_topology,
)
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)

def _run_reverse(
    *,
    scope: _SyntheticTransactionScope,
    selector: SyntheticFailureSelectorV1,
    observed_at_epoch: int,
) -> RepositoryTransactionReceiptV1:
    journal = _RepositoryJournalStore.open_verified(scope)
    if has_reverse_records(journal):
        return _resume_interrupted_reverse(
            scope=scope,
            journal=journal,
            selector=selector,
            observed_at_epoch=observed_at_epoch,
        )
    _reconcile_forward_gap(journal, scope)
    stage = _committed_forward_stage(journal)
    recreated = _observe_forward_stage(scope, stage)
    verify_forward_stage(scope, stage, recreated)
    executor = _TransactionExecutor(
        scope=scope,
        journal=journal,
        selector=selector,
        direction=SyntheticTransactionDirection.REVERSE,
        observed_at_epoch=observed_at_epoch,
    )
    failed_preserved = _preserve_stage(executor, stage, recreated)
    _extract_original(executor, stage)
    if _at_least(stage, ForwardBoundary.WORKTREES_PRESERVED):
        _restore_admin(executor)
        _restore_physical(executor)
    executor.verify(
        boundary=ReverseBoundary.ORIGINAL_REPOSITORY_VERIFIED,
        material=scope.review.operation_fingerprint,
        verification=lambda: _verify_reverse(scope, stage),
    )
    records = journal.verified_records()
    return RepositoryTransactionReceiptV1.create(
        direction=SyntheticTransactionDirection.REVERSE,
        boundary_count=_reverse_boundary_count(stage),
        mutation_count=executor.mutation_count,
        journal_record_count=len(records),
        failed_state_preserved=failed_preserved,
    )


def _resume_interrupted_reverse(
    *,
    scope,
    journal,
    selector,
    observed_at_epoch,
):
    stage = _committed_forward_stage(journal, allow_reverse=True)
    plan = reverse_stage_plan(stage)
    reconcile_reverse_gap(journal, scope, stage)
    progress = reverse_progress(journal, plan)
    verify_resume_checkpoint(scope, stage, progress)
    if progress < plan.preserve_last:
        raise ValueError("synthetic reverse resume invalid")
    executor = _TransactionExecutor(
        scope=scope, journal=journal, selector=selector,
        direction=SyntheticTransactionDirection.REVERSE,
        observed_at_epoch=observed_at_epoch,
        mutation_count=progress,
    )
    _resume_remaining(executor, stage, plan, progress)
    records = journal.verified_records()
    return RepositoryTransactionReceiptV1.create(
        direction=SyntheticTransactionDirection.REVERSE,
        boundary_count=plan.boundary_count,
        mutation_count=executor.mutation_count,
        journal_record_count=len(records),
        failed_state_preserved=plan.failed_state_preserved,
    )


def _resume_remaining(executor, stage, plan, progress) -> None:
    if plan.main_index is not None and progress < plan.main_index:
        _extract_original(executor, stage)
    if plan.admin_last is not None and progress < plan.admin_last:
        _restore_admin(
            executor,
            start=_completed_in_range(
                progress, plan.admin_first, plan.admin_last
            ),
        )
    if (
        plan.physical_last is not None
        and progress < plan.physical_last
    ):
        _restore_physical(
            executor,
            start=_completed_in_range(
                progress, plan.physical_first, plan.physical_last
            ),
        )
    if progress < plan.final_index:
        executor.verify(
            boundary=ReverseBoundary.ORIGINAL_REPOSITORY_VERIFIED,
            material=executor.scope.review.operation_fingerprint,
            verification=lambda: _verify_reverse(executor.scope, stage),
        )
    else:
        _verify_reverse(executor.scope, stage)


def _observe_forward_stage(scope, stage):
    if _at_least(stage, ForwardBoundary.WORKTREES_RECREATED):
        main = Path(scope.review.scenario.source) / "main"
        return observe_all_recreated(scope, main)
    return ()


def _preserve_stage(executor, stage, recreated) -> bool:
    if not _at_least(stage, ForwardBoundary.CONTAINER_PUBLISHED):
        return False
    if _at_least(stage, ForwardBoundary.WORKTREES_RECREATED):
        _preserve_new_state(executor, recreated)
        verification = lambda: _verify_new_preserved(
            executor.scope, recreated
        )
    else:
        scenario = executor.scope.review.scenario
        executor.move(
            boundary=ReverseBoundary.NEW_STATE_PRESERVED,
            source=Path(scenario.source),
            target=Path(scenario.failed_container),
        )
        verification = lambda: verify_partial_failed_object(
            executor.scope, stage, main_extracted=False
        )
    executor.verify(
        boundary=ReverseBoundary.NEW_STATE_PRESERVED,
        material=executor.scope.review.operation_fingerprint,
        verification=verification,
    )
    return True


def _extract_original(executor, stage) -> None:
    if stage in {
        ForwardBoundary.SOURCE_FROZEN,
        ForwardBoundary.WORKTREES_PRESERVED,
    }:
        return
    scenario = executor.scope.review.scenario
    if _at_least(stage, ForwardBoundary.MAIN_PUBLISHED):
        source = Path(scenario.failed_container) / "main"
    else:
        source = Path(scenario.legacy)
    executor.move(
        boundary=ReverseBoundary.MAIN_EXTRACTED,
        source=source,
        target=Path(scenario.source),
    )


def _preserve_new_state(executor, recreated) -> None:
    scope = executor.scope
    scenario = scope.review.scenario
    boundary = ReverseBoundary.NEW_STATE_PRESERVED
    admin_root = Path(scenario.rollback_root) / "new-admin"
    external_root = Path(scenario.rollback_root) / "new-external"
    executor.create_directory(boundary=boundary, target=admin_root)
    executor.create_directory(boundary=boundary, target=external_root)
    executor.move(
        boundary=boundary,
        source=Path(scenario.source),
        target=Path(scenario.failed_container),
    )
    failed_main = Path(scenario.failed_container) / "main"
    for item in recreated:
        source = failed_main / ".git" / "worktrees" / item.admin.name
        if (
            directory_identity(source) != item.admin_identity
            or opaque_directory_fingerprint(source) != item.admin_content
        ):
            raise ValueError("synthetic new admin changed")
        executor.move(
            boundary=boundary,
            source=source,
            target=admin_root / item.reviewed.paths.role,
            kind=RepositoryMutationKind.ADMIN_MOVE,
        )
    for item in recreated[8:]:
        executor.move(
            boundary=boundary,
            source=item.physical,
            target=external_root / item.reviewed.paths.role,
        )


def _restore_admin(executor, *, start: int = 0) -> None:
    scope = executor.scope
    scenario = scope.review.scenario
    for item in scope.review.observations[start:]:
        executor.move(
            boundary=ReverseBoundary.ADMIN_RECORDS_RESTORED,
            source=Path(scenario.admin_preservation) / item.paths.role,
            target=item.admin,
            kind=RepositoryMutationKind.ADMIN_MOVE,
        )


def _restore_physical(executor, *, start: int = 0) -> None:
    scope = executor.scope
    scenario = scope.review.scenario
    for item in scope.review.observations[start:]:
        executor.move(
            boundary=ReverseBoundary.PHYSICAL_WORKTREES_RESTORED,
            source=Path(scenario.worktree_preservation) / item.paths.role,
            target=item.paths.original,
        )


def _verify_new_preserved(scope, recreated) -> None:
    if len(recreated) != 11:
        raise ValueError("synthetic failed evidence changed")
    verify_failed_new_objects(scope, main_extracted=False)
    from .container_audit_bridge import require_reverse_failed_policy_seam

    require_reverse_failed_policy_seam(scope, main_extracted=False)


def _verify_reverse(scope, stage) -> None:
    if _at_least(stage, ForwardBoundary.WORKTREES_RECREATED):
        verify_reverse_topology(scope)
    else:
        verify_partial_reverse_topology(scope, stage)


def _reverse_boundary_count(stage: ForwardBoundary) -> int:
    return reverse_stage_plan(stage).boundary_count


def _completed_in_range(
    progress: int,
    first: int | None,
    last: int | None,
) -> int:
    if first is None or last is None or progress < first:
        return 0
    return min(11, progress - first + 1)
