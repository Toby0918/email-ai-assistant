"""Default-locked operator entry before separately approved Issue #39."""

from dataclasses import dataclass
from enum import Enum


class OperatorEntryStatus(str, Enum):
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


@dataclass(frozen=True, slots=True)
class OperatorEntryCounts:
    blocked: int
    executed: int


@dataclass(frozen=True, slots=True)
class OperatorEntryResult:
    status: OperatorEntryStatus
    counts: OperatorEntryCounts


_BLOCKED_RESULT = OperatorEntryResult(
    status=OperatorEntryStatus.BLOCKED_NO_APPROVED_COMMAND,
    counts=OperatorEntryCounts(blocked=1, executed=0),
)


def default_operator_entry() -> OperatorEntryResult:
    return _BLOCKED_RESULT
