"""Closed public status, phase, counts, and result values."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._canonical import is_fingerprint
from .errors import JournalContractError


class JournalOperationStatus(str, Enum):
    SAFE_ABORT = "SAFE_ABORT"
    RESUME_ALLOWED = "RESUME_ALLOWED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    INCIDENT_STOP = "INCIDENT_STOP"
    CUTOVER_SUCCEEDED = "CUTOVER_SUCCEEDED"


class JournalOperationPhase(str, Enum):
    CHAIN_VERIFICATION = "CHAIN_VERIFICATION"
    PENDING_INTENT_PUBLICATION = "PENDING_INTENT_PUBLICATION"
    NEXT_FORWARD_INTENT = "NEXT_FORWARD_INTENT"
    FORWARD_ACTION = "FORWARD_ACTION"
    FORWARD_OBSERVATION = "FORWARD_OBSERVATION"
    REVERSE_ACTION = "REVERSE_ACTION"
    REVERSE_OBSERVATION = "REVERSE_OBSERVATION"
    AUTHORIZATION = "AUTHORIZATION"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True, repr=False)
class JournalOperationCountsV1:
    records: int
    pending: int
    forward_committed: int
    reverse_committed: int
    rejected: int

    def to_mapping(self) -> dict[str, int]:
        return {
            "records": self.records,
            "pending": self.pending,
            "forward_committed": self.forward_committed,
            "reverse_committed": self.reverse_committed,
            "rejected": self.rejected,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class JournalOperationResultV1:
    status: JournalOperationStatus
    receipt_fingerprint: str = field(repr=False)
    phase: JournalOperationPhase
    counts: JournalOperationCountsV1

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("JournalOperationResultV1 is inspection-issued")

    @classmethod
    def _create(
        cls,
        *,
        status: JournalOperationStatus,
        receipt_fingerprint: str,
        phase: JournalOperationPhase,
        counts: JournalOperationCountsV1,
    ) -> JournalOperationResultV1:
        if (
            type(status) is not JournalOperationStatus
            or type(phase) is not JournalOperationPhase
            or type(counts) is not JournalOperationCountsV1
            or not is_fingerprint(receipt_fingerprint)
            or not _valid_counts(counts)
        ):
            raise JournalContractError("JOURNAL_RESULT_INVALID")
        result = object.__new__(cls)
        object.__setattr__(result, "status", status)
        object.__setattr__(
            result, "receipt_fingerprint", receipt_fingerprint
        )
        object.__setattr__(result, "phase", phase)
        object.__setattr__(result, "counts", counts)
        return result

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "receipt_fingerprint": self.receipt_fingerprint,
            "phase": self.phase.value,
            "counts": self.counts.to_mapping(),
        }


def _valid_counts(counts: JournalOperationCountsV1) -> bool:
    return all(
        type(value) is int and 0 <= value <= 1_000_000
        for value in counts.to_mapping().values()
    )
