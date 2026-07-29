"""Private path-bearing models for the synthetic transaction scope."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)

from .contracts import SyntheticRepositoryRosterV1
from .git_runner import _BoundSyntheticGitRunner


@dataclass(frozen=True, slots=True, repr=False)
class _SyntheticWorktreePaths:
    role: str
    placement: str
    original: Path = field(repr=False)
    target: Path = field(repr=False)
    preservation: Path = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _ObservedWorktree:
    paths: _SyntheticWorktreePaths = field(repr=False)
    ref: str = field(repr=False)
    commit: str = field(repr=False)
    common: Path = field(repr=False)
    admin: Path = field(repr=False)
    physical_identity: str = field(repr=False)
    admin_identity: str = field(repr=False)
    admin_content: str = field(repr=False)
    status_fingerprint: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _SyntheticRepositoryReview:
    scenario: object = field(repr=False)
    roster: SyntheticRepositoryRosterV1 = field(repr=False)
    observations: tuple[_ObservedWorktree, ...] = field(repr=False)
    role_selections: dict[str, str] = field(repr=False)
    evidence_roles: dict[str, str] = field(repr=False)
    reviewed_git_selections: dict[str, str] = field(repr=False)
    rollback_roles: dict[str, str] = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    root_identity: str = field(repr=False)
    marker_identity: str = field(repr=False)
    git_runner: _BoundSyntheticGitRunner = field(repr=False)
    repository_object_identity: str = field(repr=False)
    common_object_identity: str = field(repr=False)
    volume_identity: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _SyntheticTransactionScope:
    review: _SyntheticRepositoryReview = field(repr=False)
    profile: CutoverProfileV1 = field(repr=False)
    authorization: TestSandboxAuthorizationV1 = field(repr=False)
    roster: SyntheticRepositoryRosterV1 = field(repr=False)
