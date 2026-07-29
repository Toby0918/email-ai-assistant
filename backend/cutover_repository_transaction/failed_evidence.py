"""Exact identity verification for retained failed worktree state."""

from __future__ import annotations

from pathlib import Path

from .durable_store import _RepositoryJournalStore
from .errors import RepositoryTransactionError
from .git_recreation import git_add_observation_from_identities
from .journal_types import ForwardBoundary, RepositoryMutationKind
from .journal_identity import journaled_container_identity
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)

_NON_MAIN_ZONES = {
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
}


def verify_failed_evidence(scope) -> None:
    verify_failed_new_objects(scope, main_extracted=True)
    scenario = scope.review.scenario
    if (
        any(Path(scenario.admin_preservation).iterdir())
        or any(Path(scenario.worktree_preservation).iterdir())
        or any(Path(scenario.external_target_parent).iterdir())
    ):
        _fail()


def verify_failed_new_objects(
    scope,
    *,
    main_extracted: bool,
) -> None:
    scenario = scope.review.scenario
    failed = Path(scenario.failed_container)
    if directory_identity(failed) != journaled_container_identity(scope):
        _fail()
    root_entries = set(_NON_MAIN_ZONES)
    if not main_extracted:
        root_entries.add("main")
    _require_exact_children(failed, root_entries)
    if (
        not main_extracted
        and directory_identity(failed / "main")
        != scope.review.repository_object_identity
    ):
        _fail()
    _require_exact_children(
        failed / "Worktrees",
        {
            item.paths.target.name
            for item in scope.review.observations[:8]
        },
    )
    for name in _NON_MAIN_ZONES - {"Worktrees"}:
        _require_exact_children(failed / name, set())
    rollback = Path(scenario.rollback_root)
    _require_exact_children(rollback, {"new-admin", "new-external"})
    _require_exact_children(
        rollback / "new-admin",
        {item.paths.role for item in scope.review.observations},
    )
    _require_exact_children(
        rollback / "new-external",
        {
            item.paths.role
            for item in scope.review.observations
            if item.paths.placement == "external"
        },
    )
    expected = _journal_fingerprints(scope)
    actual = tuple(
        _failed_worktree_fingerprint(scope, item)
        for item in scope.review.observations
    )
    if len(expected) != 11 or actual != expected:
        _fail()


def verify_partial_failed_object(
    scope,
    stage: ForwardBoundary,
    *,
    main_extracted: bool,
) -> None:
    if stage not in {
        ForwardBoundary.CONTAINER_PUBLISHED,
        ForwardBoundary.NON_MAIN_ZONES_PUBLISHED,
        ForwardBoundary.MAIN_PUBLISHED,
    }:
        _fail()
    scenario = scope.review.scenario
    failed = Path(scenario.failed_container)
    if directory_identity(failed) != journaled_container_identity(scope):
        _fail()
    expected: set[str] = set()
    if stage is not ForwardBoundary.CONTAINER_PUBLISHED:
        expected.update(_NON_MAIN_ZONES)
    if stage is ForwardBoundary.MAIN_PUBLISHED and not main_extracted:
        expected.add("main")
    _require_exact_children(failed, expected)
    for name in expected - {"main"}:
        _require_exact_children(failed / name, set())
    if (
        "main" in expected
        and directory_identity(failed / "main")
        != scope.review.repository_object_identity
    ):
        _fail()
    if (
        any(Path(scenario.rollback_root).iterdir())
        or any(Path(scenario.external_target_parent).iterdir())
    ):
        _fail()


def _journal_fingerprints(scope) -> tuple[str, ...]:
    return tuple(
        record.observed_effect_fingerprint
        for record in _RepositoryJournalStore.open_verified(
            scope
        ).verified_records()
        if (
            record.direction == "forward"
            and record.event == "committed"
            and record.mutation_kind
            == RepositoryMutationKind.GIT_WORKTREE_ADD.value
        )
    )


def _failed_worktree_fingerprint(scope, item) -> str:
    scenario = scope.review.scenario
    physical = (
        Path(scenario.failed_container)
        / "Worktrees"
        / item.paths.target.name
        if item.paths.placement == "embedded"
        else Path(scenario.rollback_root) / "new-external" / item.paths.role
    )
    admin = Path(scenario.rollback_root) / "new-admin" / item.paths.role
    return git_add_observation_from_identities(
        item,
        directory_identity(physical),
        directory_identity(admin),
        opaque_directory_fingerprint(admin),
    )


def _require_exact_children(parent: Path, expected: set[str]) -> None:
    if not parent.is_dir() or parent.is_symlink():
        _fail()
    children = tuple(parent.iterdir())
    if (
        {item.name for item in children} != expected
        or any(not item.is_dir() or item.is_symlink() for item in children)
    ):
        _fail()


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_topology_verification_failed"
    ) from None
