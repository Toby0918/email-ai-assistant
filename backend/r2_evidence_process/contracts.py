"""Closed evidence command and public aggregate results."""

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
    BLOCKED_ENVELOPE = "BLOCKED_ENVELOPE"
    BLOCKED_AUTHORIZATION = "BLOCKED_AUTHORIZATION"
    BLOCKED_REPLAY = "BLOCKED_REPLAY"
    BLOCKED_PUBLICATION = "BLOCKED_PUBLICATION"
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


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
    accepted = int(
        status
        in {
            EvidenceProcessStatus.PUBLISHED,
            EvidenceProcessStatus.BLOCKED_NO_APPROVED_COMMAND,
        }
    )
    published = int(status is EvidenceProcessStatus.PUBLISHED)
    return EvidenceProcessResult(
        status=status,
        accepted=accepted,
        rejected=1 - accepted,
        published=published,
    )
