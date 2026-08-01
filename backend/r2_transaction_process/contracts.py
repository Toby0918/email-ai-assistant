"""Closed transaction commands and aggregate outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


TRANSACTION_ACKNOWLEDGEMENT = "ACKNOWLEDGE_R2_TRANSACTION_ACTION"
TRANSACTION_VERBS = {
    "execute": "execute",
    "resume": "resume",
    "rollback": "rollback",
}


class TransactionProcessStatus(str, Enum):
    ACTION_COMPLETE = "TRANSACTION_ACTION_COMPLETE"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_ENVELOPE = "BLOCKED_ENVELOPE"
    BLOCKED_AUTHORIZATION = "BLOCKED_AUTHORIZATION"
    BLOCKED_REPLAY = "BLOCKED_REPLAY"
    BLOCKED_ACTION = "BLOCKED_ACTION"
    BLOCKED_NO_APPROVED_COMMAND = "BLOCKED_NO_APPROVED_COMMAND"


@dataclass(frozen=True, slots=True)
class TransactionProcessResult:
    status: TransactionProcessStatus
    accepted: int
    rejected: int
    mutations: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.mutations

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "mutations": self.mutations,
        }


def result(status: TransactionProcessStatus) -> TransactionProcessResult:
    accepted = int(
        status
        in {
            TransactionProcessStatus.ACTION_COMPLETE,
            TransactionProcessStatus.BLOCKED_NO_APPROVED_COMMAND,
        }
    )
    mutations = int(status is TransactionProcessStatus.ACTION_COMPLETE)
    return TransactionProcessResult(
        status=status,
        accepted=accepted,
        rejected=1 - accepted,
        mutations=mutations,
    )
