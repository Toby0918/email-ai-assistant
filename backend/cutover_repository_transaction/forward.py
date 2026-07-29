"""Fixed forward mixed-topology synthetic transaction."""

from __future__ import annotations

from pathlib import Path

from .durable_store import _RepositoryJournalStore
from .git_inspection import directory_identity
from .git_recreation import (
    add_reviewed_worktree,
    git_add_fingerprints,
    git_add_observation_fingerprint,
    observe_recreated_worktree,
)
from .journal_types import (
    ForwardBoundary,
    RepositoryMutationKind,
)
from .mutation_executor import _TransactionExecutor
from .scope_models import _SyntheticTransactionScope
from .transaction_types import (
    RepositoryTransactionReceiptV1,
    SyntheticFailureSelectorV1,
    SyntheticTransactionDirection,
)
from .verification import verify_forward_topology

_ZONES = (
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)


def _run_forward(
    *,
    scope: _SyntheticTransactionScope,
    selector: SyntheticFailureSelectorV1,
    observed_at_epoch: int,
) -> RepositoryTransactionReceiptV1:
    journal = _RepositoryJournalStore.begin(scope)
    executor = _TransactionExecutor(
        scope=scope,
        journal=journal,
        selector=selector,
        direction=SyntheticTransactionDirection.FORWARD,
        observed_at_epoch=observed_at_epoch,
    )
    scenario = scope.review.scenario
    executor.verify(
        boundary=ForwardBoundary.SOURCE_FROZEN,
        material=scope.review.operation_fingerprint,
        verification=lambda: _verify_initial(scope),
    )
    _preserve_original_worktrees(executor)
    executor.verify(
        boundary=ForwardBoundary.WORKTREES_PRESERVED,
        material=scope.roster.roster_fingerprint,
        verification=lambda: _verify_preserved(scope),
    )
    main = _publish_container(executor)
    recreated = _recreate_worktrees(executor, main)
    executor.verify(
        boundary=ForwardBoundary.REPOSITORY_FINAL_VERIFIED,
        material=scope.review.operation_fingerprint,
        verification=lambda: verify_forward_topology(scope, recreated),
    )
    records = journal.verified_records()
    return _forward_receipt(executor, len(records))


def _publish_container(executor) -> Path:
    scenario = executor.scope.review.scenario
    executor.move(
        boundary=ForwardBoundary.LEGACY_RENAMED,
        source=Path(scenario.source),
        target=Path(scenario.legacy),
    )
    executor.create_directory(
        boundary=ForwardBoundary.CONTAINER_PUBLISHED,
        target=Path(scenario.source),
    )
    for name in _ZONES:
        executor.create_directory(
            boundary=ForwardBoundary.NON_MAIN_ZONES_PUBLISHED,
            target=Path(scenario.source) / name,
        )
    main = Path(scenario.source) / "main"
    executor.move(
        boundary=ForwardBoundary.MAIN_PUBLISHED,
        source=Path(scenario.legacy),
        target=main,
    )
    return main


def _forward_receipt(executor, record_count):
    return RepositoryTransactionReceiptV1.create(
        direction=SyntheticTransactionDirection.FORWARD,
        boundary_count=8,
        mutation_count=executor.mutation_count,
        journal_record_count=record_count,
        failed_state_preserved=False,
    )


def _preserve_original_worktrees(executor) -> None:
    scope = executor.scope
    scenario = scope.review.scenario
    boundary = ForwardBoundary.WORKTREES_PRESERVED
    for item in scope.review.observations:
        executor.move(
            boundary=boundary,
            source=item.paths.original,
            target=Path(scenario.worktree_preservation) / item.paths.role,
        )
    for item in scope.review.observations:
        executor.move(
            boundary=boundary,
            source=item.admin,
            target=Path(scenario.admin_preservation) / item.paths.role,
            kind=RepositoryMutationKind.ADMIN_MOVE,
        )


def _recreate_worktrees(executor, main):
    values = []
    expected_admins: set[str] = set()
    scope = executor.scope
    boundary = ForwardBoundary.WORKTREES_RECREATED
    for reviewed in scope.review.observations:
        reservation = executor.create_directory(
            boundary=boundary,
            target=reviewed.paths.target,
            kind=RepositoryMutationKind.RESERVE_WORKTREE,
        )
        before, expected = git_add_fingerprints(reviewed)
        value = executor.fixed_effect(
            boundary=boundary,
            kind=RepositoryMutationKind.GIT_WORKTREE_ADD,
            before=before,
            expected=expected,
            effect=lambda reviewed=reviewed, identity=(
                reservation.target_identity_fingerprint
            ), admins=frozenset(expected_admins): add_reviewed_worktree(
                scope, reviewed, main, identity, admins
            ),
            observation=git_add_observation_fingerprint,
            stable_observation=lambda reviewed=reviewed: (
                git_add_observation_fingerprint(
                    observe_recreated_worktree(
                        scope, reviewed, main
                    )
                )
            ),
        )
        values.append(value)
        expected_admins.add(value.admin.name.casefold())
    return tuple(values)


def _verify_initial(scope) -> None:
    scenario = scope.review.scenario
    empty_roots = (
        Path(scenario.admin_preservation),
        Path(scenario.worktree_preservation),
        Path(scenario.rollback_root),
        Path(scenario.external_target_parent),
    )
    if (
        directory_identity(Path(scenario.source))
        != scope.review.repository_object_identity
        or Path(scenario.legacy).exists()
        or Path(scenario.failed_container).exists()
        or any(any(path.iterdir()) for path in empty_roots)
    ):
        raise ValueError("synthetic source changed")


def _verify_preserved(scope) -> None:
    scenario = scope.review.scenario
    for item in scope.review.observations:
        if (
            directory_identity(
                Path(scenario.worktree_preservation) / item.paths.role
            )
            != item.physical_identity
            or directory_identity(
                Path(scenario.admin_preservation) / item.paths.role
            )
            != item.admin_identity
        ):
            raise ValueError("synthetic preservation changed")
