"""Fixed Git worktree recreation and relationship verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import RepositoryTransactionError
from .git_inspection import exact_admin_children
from .scope_models import (
    _ObservedWorktree,
    _SyntheticTransactionScope,
)
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)


@dataclass(frozen=True, slots=True, repr=False)
class _RecreatedWorktree:
    reviewed: _ObservedWorktree = field(repr=False)
    physical: Path = field(repr=False)
    admin: Path = field(repr=False)
    physical_identity: str = field(repr=False)
    admin_identity: str = field(repr=False)
    admin_content: str = field(repr=False)


def add_reviewed_worktree(
    scope: _SyntheticTransactionScope,
    reviewed: _ObservedWorktree,
    main: Path,
    reserved_identity: str,
    expected_admins: frozenset[str],
) -> _RecreatedWorktree:
    target = reviewed.paths.target
    if (
        directory_identity(target) != reserved_identity
        or any(target.iterdir())
    ):
        _fail()
    namespace = main / ".git" / "worktrees"
    before = set(exact_admin_children(namespace))
    if before != set(expected_admins):
        _fail()
    scope.review.git_runner.add_worktree(
        main, target, reviewed.ref
    )
    after = set(exact_admin_children(namespace))
    added = after - before
    if len(added) != 1 or before - after:
        _fail()
    result = observe_recreated_worktree(scope, reviewed, main)
    if (
        result.admin.name.casefold() not in added
        or after != before | {result.admin.name.casefold()}
        or result.physical_identity != reserved_identity
        or result.admin_identity == reviewed.admin_identity
    ):
        _fail()
    return result


def observe_recreated_worktree(
    scope: _SyntheticTransactionScope,
    reviewed: _ObservedWorktree,
    main: Path,
) -> _RecreatedWorktree:
    target = reviewed.paths.target
    runner = scope.review.git_runner
    common = _resolved_path(runner.common_dir(target))
    admin = _resolved_path(runner.git_dir(target))
    expected_namespace = main / ".git" / "worktrees"
    if (
        directory_identity(common)
        != scope.review.common_object_identity
        or admin.parent != expected_namespace
        or not admin.name
    ):
        _fail()
    ref = _text(runner.symbolic_ref(target))
    commit = _text(runner.head(target))
    status = runner.status(target)
    if ref != reviewed.ref or commit != reviewed.commit or status:
        _fail()
    return _RecreatedWorktree(
        reviewed=reviewed,
        physical=target,
        admin=admin,
        physical_identity=directory_identity(target),
        admin_identity=directory_identity(admin),
        admin_content=opaque_directory_fingerprint(admin),
    )


def observe_all_recreated(
    scope: _SyntheticTransactionScope,
    main: Path,
) -> tuple[_RecreatedWorktree, ...]:
    values = tuple(
        observe_recreated_worktree(scope, item, main)
        for item in scope.review.observations
    )
    if (
        len({item.physical_identity for item in values}) != 11
        or len({item.admin_identity for item in values}) != 11
        or len({item.admin.name.casefold() for item in values}) != 11
    ):
        _fail()
    return values


def git_add_fingerprints(reviewed: _ObservedWorktree) -> tuple[str, str]:
    material = (
        reviewed.paths.role
        + reviewed.ref
        + reviewed.commit
        + reviewed.paths.target.name
    ).encode("utf-8")
    before = hashlib.sha256(b"issue56-git-add-before\0" + material).hexdigest()
    expected = hashlib.sha256(
        b"issue56-git-add-after\0" + material
    ).hexdigest()
    return before, expected


def git_add_observation_fingerprint(value: object) -> str:
    if type(value) is not _RecreatedWorktree:
        _fail()
    return git_add_observation_from_identities(
        value.reviewed,
        value.physical_identity,
        value.admin_identity,
        value.admin_content,
    )


def git_add_observation_from_identities(
    reviewed: _ObservedWorktree,
    physical_identity: str,
    admin_identity: str,
    admin_content: str,
) -> str:
    material = (
        reviewed.ref
        + reviewed.commit
        + physical_identity
        + admin_identity
        + admin_content
    ).encode("ascii")
    return hashlib.sha256(
        b"issue56-git-add-observed\0" + material
    ).hexdigest()


def _resolved_path(payload: bytes) -> Path:
    try:
        return Path(_text(payload)).resolve(strict=True)
    except (OSError, RuntimeError):
        _fail()


def _text(payload: bytes) -> str:
    try:
        return payload.decode("utf-8", "strict").strip()
    except UnicodeError:
        _fail()


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_git_recreation_invalid"
    ) from None
