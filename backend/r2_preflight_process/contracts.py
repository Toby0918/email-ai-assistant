"""Closed public command and result vocabulary for preflight."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


PREFLIGHT_ACKNOWLEDGEMENT = "ACKNOWLEDGE_R2_PREFLIGHT"
PREFLIGHT_VERBS = {
    "current-topology": "current_topology_preflight",
    "host-baseline": "host_baseline",
    "evidence-review": "evidence_review",
    "evidence-verification": "evidence_verification",
    "final-audit-readiness": "final_audit_readiness",
    "recovery-inspection": "recovery_inspection",
}


class PreflightProcessStatus(str, Enum):
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_ENVELOPE = "BLOCKED_ENVELOPE"
    BLOCKED_AUTHORIZATION = "BLOCKED_AUTHORIZATION"
    BLOCKED_REPLAY = "BLOCKED_REPLAY"
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


@dataclass(frozen=True, slots=True)
class PreflightProcessResult:
    status: PreflightProcessStatus
    accepted: int
    rejected: int
    host_operations: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.host_operations

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "host_operations": self.host_operations,
        }


def blocked(status: PreflightProcessStatus) -> PreflightProcessResult:
    accepted = int(status is PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND)
    return PreflightProcessResult(
        status=status,
        accepted=accepted,
        rejected=1 - accepted,
        host_operations=0,
    )
