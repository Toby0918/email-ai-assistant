"""Exact forward and reverse topology verification."""

from __future__ import annotations

from pathlib import Path

from .container_audit_bridge import (
    require_container_audit_policy_seams,
    require_reverse_failed_policy_seam,
)
from .errors import RepositoryTransactionError
from .failed_evidence import (
    verify_failed_evidence,
    verify_partial_failed_object,
)
from .git_inspection import (
    observe_git_topology,
)
from .git_recreation import _RecreatedWorktree
from .journal_types import ForwardBoundary
from .scope_models import (
    _SyntheticTransactionScope,
    _SyntheticWorktreePaths,
)
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)

_NON_MAIN_ZONES = (
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)


def verify_forward_topology(
    scope: _SyntheticTransactionScope,
    recreated: tuple[_RecreatedWorktree, ...],
) -> None:
    scenario = scope.review.scenario
    container = Path(scenario.source)
    main = container / "main"
    _require_exact_children(container, {"main", *_NON_MAIN_ZONES})
    if (
        directory_identity(main)
        != scope.review.repository_object_identity
        or directory_identity(main / ".git")
        != scope.review.common_object_identity
        or len(recreated) != 11
    ):
        _fail()
    _require_clean(main, scope)
    _verify_preserved_originals(scope)
    _verify_recreated(scope, recreated)
    require_container_audit_policy_seams(scope, recreated)
    expected = tuple(
        _target_as_original(item.paths)
        for item in scope.review.observations
    )
    observed, selections = observe_git_topology(
        scope.review.git_runner, main, expected
    )
    _require_reviewed_git_selections(
        scope, selections, allow_topology_change=True
    )
    for current, original in zip(observed, scope.review.observations):
        if (
            current.ref != original.ref
            or current.commit != original.commit
            or current.common != main / ".git"
        ):
            _fail()


def verify_forward_stage(
    scope: _SyntheticTransactionScope,
    stage: ForwardBoundary,
    recreated: tuple[_RecreatedWorktree, ...],
) -> None:
    if stage is ForwardBoundary.SOURCE_FROZEN:
        verify_original_repository(scope)
        return
    if stage is ForwardBoundary.WORKTREES_PRESERVED:
        _verify_relocated_original(scope, Path(scope.review.scenario.source))
        return
    scenario = scope.review.scenario
    if stage is ForwardBoundary.LEGACY_RENAMED:
        _require_absent(Path(scenario.source))
        _verify_relocated_original(scope, Path(scenario.legacy))
        return
    container = Path(scenario.source)
    expected = set()
    if stage is not ForwardBoundary.CONTAINER_PUBLISHED:
        expected.update(_NON_MAIN_ZONES)
    if stage not in {
        ForwardBoundary.CONTAINER_PUBLISHED,
        ForwardBoundary.NON_MAIN_ZONES_PUBLISHED,
    }:
        expected.add("main")
    _require_exact_children(container, expected)
    repository = (
        container / "main"
        if "main" in expected
        else Path(scenario.legacy)
    )
    _verify_relocated_original(scope, repository)
    if stage in {
        ForwardBoundary.WORKTREES_RECREATED,
        ForwardBoundary.REPOSITORY_FINAL_VERIFIED,
    }:
        verify_forward_topology(scope, recreated)


def verify_original_repository(scope: _SyntheticTransactionScope) -> None:
    source = Path(scope.review.scenario.source)
    if (
        directory_identity(source)
        != scope.review.repository_object_identity
        or directory_identity(source / ".git")
        != scope.review.common_object_identity
    ):
        _fail()
    _require_clean(source, scope)
    observed, selections = observe_git_topology(
        scope.review.git_runner, source,
        tuple(item.paths for item in scope.review.observations),
    )
    _require_reviewed_git_selections(
        scope, selections, allow_topology_change=False
    )
    for current, original in zip(observed, scope.review.observations):
        if not _same_original_worktree(current, original):
            _fail()


def verify_reverse_topology(
    scope: _SyntheticTransactionScope,
) -> None:
    verify_original_repository(scope)
    require_reverse_failed_policy_seam(scope)
    verify_failed_evidence(scope)


def verify_partial_reverse_topology(
    scope: _SyntheticTransactionScope,
    stage: ForwardBoundary,
) -> None:
    verify_original_repository(scope)
    scenario = scope.review.scenario
    failed = Path(scenario.failed_container)
    if stage in {
        ForwardBoundary.SOURCE_FROZEN,
        ForwardBoundary.WORKTREES_PRESERVED,
        ForwardBoundary.LEGACY_RENAMED,
    }:
        _require_absent(failed)
    elif stage is ForwardBoundary.CONTAINER_PUBLISHED:
        verify_partial_failed_object(
            scope, stage, main_extracted=True
        )
    elif stage in {
        ForwardBoundary.NON_MAIN_ZONES_PUBLISHED,
        ForwardBoundary.MAIN_PUBLISHED,
    }:
        verify_partial_failed_object(
            scope, stage, main_extracted=True
        )
    else:
        verify_failed_evidence(scope)
        return
    _verify_empty_recovery_roots(scenario)


def _verify_preserved_originals(scope) -> None:
    scenario = scope.review.scenario
    for item in scope.review.observations:
        physical = Path(scenario.worktree_preservation) / item.paths.role
        admin = Path(scenario.admin_preservation) / item.paths.role
        if (
            directory_identity(physical) != item.physical_identity
            or directory_identity(admin) != item.admin_identity
            or opaque_directory_fingerprint(admin) != item.admin_content
            or item.paths.original.exists()
        ):
            _fail()


def _verify_relocated_original(scope, repository: Path) -> None:
    if (
        directory_identity(repository)
        != scope.review.repository_object_identity
        or directory_identity(repository / ".git")
        != scope.review.common_object_identity
    ):
        _fail()
    _verify_preserved_originals(scope)


def _same_original_worktree(current, original) -> bool:
    return (
        current.ref == original.ref
        and current.commit == original.commit
        and current.physical_identity == original.physical_identity
        and current.admin_identity == original.admin_identity
        and current.admin_content == original.admin_content
    )


def _require_reviewed_git_selections(
    scope,
    observed: dict[str, str],
    *,
    allow_topology_change: bool,
) -> None:
    reviewed = scope.review.reviewed_git_selections
    if set(observed) != set(reviewed):
        _fail()
    compared = (
        set(reviewed) - {"worktree_topology"}
        if allow_topology_change
        else set(reviewed)
    )
    if any(observed[key] != reviewed[key] for key in compared):
        _fail()


def _verify_empty_recovery_roots(scenario) -> None:
    for path in (
        Path(scenario.admin_preservation),
        Path(scenario.worktree_preservation),
        Path(scenario.rollback_root),
        Path(scenario.external_target_parent),
    ):
        if any(path.iterdir()):
            _fail()


def _require_absent(path: Path) -> None:
    if path.exists() or path.is_symlink():
        _fail()


def _verify_recreated(scope, recreated) -> None:
    for current, reviewed in zip(recreated, scope.review.observations):
        if (
            current.reviewed is not reviewed
            or current.physical != reviewed.paths.target
            or current.admin_identity == reviewed.admin_identity
        ):
            _fail()


def _target_as_original(paths) -> _SyntheticWorktreePaths:
    return _SyntheticWorktreePaths(
        role=paths.role,
        placement=paths.placement,
        original=paths.target,
        target=paths.original,
        preservation=paths.preservation,
    )


def _require_clean(repository: Path, scope) -> None:
    status = scope.review.git_runner.status(repository)
    if status:
        _fail()


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
