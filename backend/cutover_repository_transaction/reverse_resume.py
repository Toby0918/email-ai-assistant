"""Stage-bound reconciliation and verification for interrupted reverse work."""

from __future__ import annotations

import hashlib
from contextlib import nullcontext
from pathlib import Path

from .errors import RepositoryTransactionError
from .journal_types import (
    ForwardBoundary,
    RepositoryMutationKind,
)
from .reverse_plan import ReverseStagePlan, reverse_stage_plan
from .reverse_checkpoint import (
    reverse_main_source,
    verify_resume_checkpoint,
    verify_reverse_final,
)
from .stable_observation import locked_filesystem_observation
from .windows_identity import directory_identity


def has_reverse_records(journal) -> bool:
    return any(
        record.direction == "reverse"
        for record in journal.verified_records()
    )


def reconcile_reverse_gap(journal, scope, stage: ForwardBoundary) -> None:
    records = journal.verified_records()
    last = records[-1]
    if last.direction != "reverse":
        _fail()
    if last.event in {"committed", "aborted"}:
        return
    state = reverse_gap_state(scope, last, stage)
    if state == "before" and last.event == "intent":
        journal.append_aborted(last)
        return
    if state != "after":
        _fail()
    with _stable_commit_context(scope, last, stage) as actual:
        if last.event == "intent":
            observed = journal.append_observed(last, actual)
            journal.append_committed(last, observed)
            return
        if (
            last.event == "observed"
            and len(records) >= 2
            and last.observed_effect_fingerprint == actual
        ):
            journal.append_committed(records[-2], last)
            return
    _fail()


def reverse_progress(journal, plan: ReverseStagePlan) -> int:
    committed = tuple(
        record
        for record in journal.verified_records()
        if record.direction == "reverse" and record.event == "committed"
    )
    if not committed:
        return 0
    indexes = tuple(record.mutation_index for record in committed)
    progress = indexes[-1]
    if (
        indexes != tuple(range(1, progress + 1))
        or progress > plan.final_index
    ):
        _fail()
    return progress


def reverse_gap_state(
    scope,
    record,
    stage: ForwardBoundary | None = None,
) -> str:
    if stage is None:
        from .durable_store import _RepositoryJournalStore
        from .forward_recovery import committed_forward_stage

        journal = _RepositoryJournalStore.open_verified(scope)
        stage = committed_forward_stage(journal, allow_reverse=True)
    plan = reverse_stage_plan(stage)
    index = record.mutation_index
    if index in {plan.preserve_last, plan.final_index}:
        if index == 0:
            return "unknown"
        try:
            if index == plan.final_index:
                verify_reverse_final(scope, stage)
            else:
                verify_resume_checkpoint(scope, stage, index)
        except Exception:
            return "unknown"
        return "after"
    if index == plan.main_index:
        return _move_state(
            reverse_main_source(scope, stage),
            Path(scope.review.scenario.source),
            scope.review.repository_object_identity,
        )
    if index == plan.admin_last:
        item = scope.review.observations[-1]
        return _move_state(
            Path(scope.review.scenario.admin_preservation)
            / item.paths.role,
            item.admin,
            item.admin_identity,
        )
    if index == plan.physical_last:
        item = scope.review.observations[-1]
        return _move_state(
            Path(scope.review.scenario.worktree_preservation)
            / item.paths.role,
            item.paths.original,
            item.physical_identity,
        )
    return "unknown"


def _move_state(source: Path, target: Path, expected: str) -> str:
    try:
        if source.is_dir() and not target.exists():
            return (
                "before"
                if directory_identity(source) == expected
                else "unknown"
            )
        if target.is_dir() and not source.exists():
            return (
                "after"
                if directory_identity(target) == expected
                else "unknown"
            )
    except Exception:
        return "unknown"
    return "unknown"


def _observation_fingerprint(scope, record, stage) -> str:
    if record.mutation_kind == RepositoryMutationKind.VERIFY.value:
        plan = reverse_stage_plan(stage)
        if record.mutation_index == plan.final_index:
            verify_reverse_final(scope, stage)
        else:
            verify_resume_checkpoint(
                scope, stage, record.mutation_index
            )
        return hashlib.sha256(
            b"verify-observed\0"
            + scope.review.operation_fingerprint.encode("ascii")
        ).hexdigest()
    target, kind = _move_target_and_kind(scope, record, stage)
    with locked_filesystem_observation(target, kind) as value:
        return value


def _stable_commit_context(scope, record, stage):
    if record.mutation_kind == RepositoryMutationKind.VERIFY.value:
        return nullcontext(
            _observation_fingerprint(scope, record, stage)
        )
    target, kind = _move_target_and_kind(scope, record, stage)
    return locked_filesystem_observation(target, kind)


def _move_target_and_kind(scope, record, stage):
    plan = reverse_stage_plan(stage)
    if record.mutation_index == plan.main_index:
        target = Path(scope.review.scenario.source)
    elif record.mutation_index == plan.admin_last:
        target = scope.review.observations[-1].admin
    elif record.mutation_index == plan.physical_last:
        target = scope.review.observations[-1].paths.original
    else:
        _fail()
    try:
        kind = RepositoryMutationKind(record.mutation_kind)
    except ValueError:
        _fail()
    if kind not in {
        RepositoryMutationKind.PHYSICAL_MOVE,
        RepositoryMutationKind.ADMIN_MOVE,
    }:
        _fail()
    return target, kind


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_reverse_resume_invalid"
    ) from None
