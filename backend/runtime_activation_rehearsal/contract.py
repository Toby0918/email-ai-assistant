"""Fixed, aggregate-only activation rehearsal results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ManagedActivationStatus(str, Enum):
    """The complete public status allowlist."""

    COMPLETED = "managed_activation_rehearsal_completed"
    FAILED = "managed_activation_rehearsal_failed"


@dataclass(frozen=True, slots=True)
class ManagedActivationCounts:
    """Aggregate-only outcome counts."""

    completed: int
    failed: int


@dataclass(frozen=True, slots=True)
class ManagedActivationResult:
    """A fixed public result without evidence or native detail."""

    status: ManagedActivationStatus
    counts: ManagedActivationCounts


COMPLETED_RESULT = ManagedActivationResult(
    status=ManagedActivationStatus.COMPLETED,
    counts=ManagedActivationCounts(completed=1, failed=0),
)
FAILED_RESULT = ManagedActivationResult(
    status=ManagedActivationStatus.FAILED,
    counts=ManagedActivationCounts(completed=0, failed=1),
)
