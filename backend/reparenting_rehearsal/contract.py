"""Fixed request and result values for the synthetic rehearsal."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SyntheticWorktree(str, Enum):
    """The complete synthetic linked-worktree allowlist."""

    ALPHA = "alpha"
    BETA = "beta"


class WorktreeStrategy(str, Enum):
    """Reviewed recovery choices."""

    REPAIR = "repair"
    RECREATE = "recreate"


class PublicationBoundary(str, Enum):
    """Failure-injection points after durable synthetic publications."""

    EVIDENCE_PACKAGE = "evidence_package"
    LEGACY_RENAME = "legacy_rename"
    CONTAINER_PUBLICATION = "container_publication"
    MAIN_PUBLICATION = "main_publication"
    WORKTREE_PUBLICATION = "worktree_publication"
    CONTAINER_AUDIT = "container_audit"


class ReparentingStatus(str, Enum):
    """The complete public status allowlist."""

    COMPLETED = "reparenting_rehearsal_completed"
    ROLLBACK_VERIFIED = "reparenting_rehearsal_rollback_verified"
    FAILED = "reparenting_rehearsal_failed"


@dataclass(frozen=True, slots=True, repr=False)
class ReviewedWorktreeChoice:
    """One content-free choice for a fixed synthetic worktree."""

    worktree: SyntheticWorktree
    strategy: WorktreeStrategy


@dataclass(frozen=True, slots=True)
class ReparentingCounts:
    """Aggregate-only outcome counts."""

    completed: int
    rollback_verified: int
    failed: int


@dataclass(frozen=True, slots=True)
class ReparentingRehearsalResult:
    """A fixed public result with no path or Git detail."""

    status: ReparentingStatus
    counts: ReparentingCounts


COMPLETED_RESULT = ReparentingRehearsalResult(
    status=ReparentingStatus.COMPLETED,
    counts=ReparentingCounts(completed=1, rollback_verified=0, failed=0),
)
ROLLBACK_VERIFIED_RESULT = ReparentingRehearsalResult(
    status=ReparentingStatus.ROLLBACK_VERIFIED,
    counts=ReparentingCounts(completed=0, rollback_verified=1, failed=0),
)
FAILED_RESULT = ReparentingRehearsalResult(
    status=ReparentingStatus.FAILED,
    counts=ReparentingCounts(completed=0, rollback_verified=0, failed=1),
)
