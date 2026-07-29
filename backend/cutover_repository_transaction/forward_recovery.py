"""Exact forward-stage recovery used only by the reverse entry."""

from __future__ import annotations

from pathlib import Path

from .journal_types import ForwardBoundary, RepositoryMutationKind
from .restart_classification import classify_synthetic_restart
from .stable_observation import locked_filesystem_observation
from .transaction_types import RestartClassification

_FORWARD_STAGE_MUTATIONS = {
    ForwardBoundary.SOURCE_FROZEN: 1,
    ForwardBoundary.WORKTREES_PRESERVED: 24,
    ForwardBoundary.LEGACY_RENAMED: 25,
    ForwardBoundary.CONTAINER_PUBLISHED: 26,
    ForwardBoundary.NON_MAIN_ZONES_PUBLISHED: 34,
    ForwardBoundary.MAIN_PUBLISHED: 35,
    ForwardBoundary.WORKTREES_RECREATED: 57,
    ForwardBoundary.REPOSITORY_FINAL_VERIFIED: 58,
}
_FORWARD_STAGES = tuple(_FORWARD_STAGE_MUTATIONS)


def committed_forward_stage(
    journal, *, allow_reverse: bool = False
) -> ForwardBoundary:
    records = journal.verified_records()
    if (
        not allow_reverse
        and any(record.direction != "forward" for record in records)
    ):
        raise ValueError("synthetic forward journal incomplete")
    committed = tuple(
        record
        for record in records
        if record.direction == "forward" and record.event == "committed"
    )
    if not committed:
        raise ValueError("synthetic forward journal incomplete")
    last = committed[-1]
    try:
        stage = ForwardBoundary(last.boundary)
    except ValueError:
        raise ValueError("synthetic forward journal incomplete") from None
    if last.mutation_index != _FORWARD_STAGE_MUTATIONS[stage]:
        raise ValueError("synthetic forward journal incomplete")
    return stage


def reconcile_forward_gap(journal, scope) -> None:
    records = journal.verified_records()
    last = records[-1] if records else None
    if last is None or last.event in {"committed", "aborted"}:
        return
    classification = classify_synthetic_restart(scope)
    if (
        last.direction != "forward"
        or classification
        in {
            RestartClassification.INCIDENT_STOP,
            RestartClassification.NO_INTERRUPTION,
        }
    ):
        raise ValueError("synthetic forward journal incomplete")
    if classification is RestartClassification.SAFE_ABORT:
        journal.append_aborted(last)
        return
    if (
        last.boundary != ForwardBoundary.LEGACY_RENAMED.value
        or last.mutation_kind
        != RepositoryMutationKind.PHYSICAL_MOVE.value
    ):
        raise ValueError("synthetic forward journal incomplete")
    target = Path(scope.review.scenario.legacy)
    with locked_filesystem_observation(
        target, RepositoryMutationKind.PHYSICAL_MOVE
    ) as actual:
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
    raise ValueError("synthetic forward journal incomplete")


def at_least(
    stage: ForwardBoundary, expected: ForwardBoundary
) -> bool:
    return _FORWARD_STAGES.index(stage) >= _FORWARD_STAGES.index(expected)
