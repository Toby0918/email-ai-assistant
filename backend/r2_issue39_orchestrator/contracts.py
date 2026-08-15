"""Closed content-free Issue #39 orchestration values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Issue39OrchestratorStatusV1(str, Enum):
    BLOCKED_CLOSURE = "BLOCKED_CLOSURE"
    BLOCKED_ISSUE38 = "BLOCKED_ISSUE38"
    BLOCKED_INCIDENT_STAGE = "BLOCKED_INCIDENT_STAGE"
    PREFLIGHT_COMPLETE = "PREFLIGHT_COMPLETE"
    EVIDENCE_COMPLETE = "EVIDENCE_COMPLETE"
    CUTOVER_SUCCEEDED = "PROJECT_CONTAINER_CUTOVER_SUCCEEDED"
    SAFE_ABORT = "SAFE_ABORT"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    LEGACY_RECOVERED = "LEGACY_FLAT_LAYOUT_RESTORED"
    INCIDENT_STOP = "INCIDENT_STOP"


class Issue39TransactionStatusV1(str, Enum):
    SUCCEEDED = "CUTOVER_SUCCEEDED"
    SAFE_ABORT = "SAFE_ABORT"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    LEGACY_RECOVERED = "LEGACY_RECOVERED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True)
class Issue39TransactionOutcomeV1:
    status: Issue39TransactionStatusV1
    host_actions: int

    def __post_init__(self) -> None:
        if type(self.host_actions) is not int or not 0 <= self.host_actions <= 64:
            raise TypeError("R2_ISSUE39_TRANSACTION_OUTCOME_INVALID")


@dataclass(frozen=True, slots=True)
class Issue39ReadinessV1:
    closure_eligible: bool
    issue38_closed: bool
    incident_stage_absent: bool

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (
                self.closure_eligible,
                self.issue38_closed,
                self.incident_stage_absent,
            )
        ):
            raise TypeError("R2_ISSUE39_READINESS_INVALID")


@dataclass(frozen=True, slots=True)
class Issue39OrchestratorResultV1:
    status: Issue39OrchestratorStatusV1
    accepted: int
    rejected: int
    host_actions: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.host_actions

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "host_actions": self.host_actions,
        }
