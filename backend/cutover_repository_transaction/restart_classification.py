"""Read-only classification of closed, safely observable crash gaps."""

from __future__ import annotations

from pathlib import Path

from .durable_store import _RepositoryJournalStore
from .git_inspection import directory_identity
from .scope_models import _SyntheticTransactionScope
from .transaction_types import RestartClassification


def classify_synthetic_restart(
    scope: object,
) -> RestartClassification:
    if type(scope) is not _SyntheticTransactionScope:
        return RestartClassification.INCIDENT_STOP
    try:
        records = _RepositoryJournalStore.open_verified(
            scope
        ).verified_records()
    except Exception:
        return RestartClassification.INCIDENT_STOP
    if not records:
        return RestartClassification.NO_INTERRUPTION
    last = records[-1]
    if (
        last.event == "committed"
        and last.boundary in {
            "repository_final_verified",
            "original_repository_verified",
        }
    ):
        return RestartClassification.NO_INTERRUPTION
    if last.event == "committed":
        return RestartClassification.SAFE_ABORT
    state = _classifiable_state(scope, last)
    if state == "before" and last.event == "intent":
        return RestartClassification.SAFE_ABORT
    if state == "after" and last.event in {"intent", "observed"}:
        return RestartClassification.SAFE_COMMIT_FACTS
    return RestartClassification.INCIDENT_STOP


def _classifiable_state(scope, record) -> str:
    scenario = scope.review.scenario
    if (
        record.direction == "forward"
        and record.boundary == "legacy_renamed"
    ):
        return _move_state(
            Path(scenario.source),
            Path(scenario.legacy),
            scope.review.repository_object_identity,
        )
    if (
        record.direction == "reverse"
    ):
        from .reverse_resume import reverse_gap_state

        return reverse_gap_state(scope, record)
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
