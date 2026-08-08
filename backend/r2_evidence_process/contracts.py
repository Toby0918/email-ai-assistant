"""Pure historical evidence result plus latent fixed command vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


EVIDENCE_ACKNOWLEDGEMENT = "ACKNOWLEDGE_R2_EVIDENCE_PUBLICATION"
EVIDENCE_VERBS = {"publish": "evidence_publication"}


class EvidenceProcessStatus(str, Enum):
    PUBLISHED = "EVIDENCE_PUBLISHED"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_EXECUTION_CONFIRMATION = "BLOCKED_EXECUTION_CONFIRMATION"
    BLOCKED_FINGERPRINT = "BLOCKED_FINGERPRINT"
    BLOCKED_REPLAY = "BLOCKED_REPLAY"
    BLOCKED_ACTION = "BLOCKED_ACTION"
    DORMANT_NO_ISSUE39_APPROVAL = "DORMANT_NO_ISSUE39_APPROVAL"


@dataclass(frozen=True, slots=True)
class EvidenceProcessResult:
    status: EvidenceProcessStatus
    accepted: int
    rejected: int
    published: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.published

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "published": self.published,
        }


def result(status: EvidenceProcessStatus) -> EvidenceProcessResult:
    if type(status) is not EvidenceProcessStatus:
        raise TypeError("R2_EVIDENCE_RESULT_INVALID")
    if status is EvidenceProcessStatus.DORMANT_NO_ISSUE39_APPROVAL:
        return EvidenceProcessResult(status, 0, 0, 0)
    accepted = int(status is EvidenceProcessStatus.PUBLISHED)
    return EvidenceProcessResult(status, accepted, 1 - accepted, accepted)
