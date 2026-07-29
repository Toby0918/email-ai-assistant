"""Closed synthetic transaction interruption and receipt values."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from .errors import RepositoryTransactionError
from .journal_types import ForwardBoundary, ReverseBoundary


class SyntheticCrashGap(str, Enum):
    NONE = "none"
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_OBSERVED = "after_observed"
    AFTER_COMMITTED = "after_committed"


class SyntheticTransactionDirection(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


class RestartClassification(str, Enum):
    SAFE_ABORT = "SAFE_ABORT"
    SAFE_COMMIT_FACTS = "SAFE_COMMIT_FACTS"
    INCIDENT_STOP = "INCIDENT_STOP"
    NO_INTERRUPTION = "NO_INTERRUPTION"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class SyntheticFailureSelectorV1:
    direction: SyntheticTransactionDirection | None
    boundary: ForwardBoundary | ReverseBoundary | None
    mutation_index: int
    gap: SyntheticCrashGap

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated failure selector required")

    @classmethod
    def none(cls) -> SyntheticFailureSelectorV1:
        return cls._create(None, None, 0, SyntheticCrashGap.NONE)

    @classmethod
    def create(
        cls,
        *,
        direction: SyntheticTransactionDirection,
        boundary: ForwardBoundary | ReverseBoundary,
        mutation_index: int,
        gap: SyntheticCrashGap,
    ) -> SyntheticFailureSelectorV1:
        valid_boundary = (
            type(boundary) is ForwardBoundary
            if direction is SyntheticTransactionDirection.FORWARD
            else type(boundary) is ReverseBoundary
        )
        if (
            type(direction) is not SyntheticTransactionDirection
            or not valid_boundary
            or type(mutation_index) is not int
            or not 1 <= mutation_index <= 1_000
            or type(gap) is not SyntheticCrashGap
            or gap is SyntheticCrashGap.NONE
        ):
            raise RepositoryTransactionError(
                "repository_failure_selector_invalid"
            )
        return cls._create(direction, boundary, mutation_index, gap)

    @classmethod
    def _create(cls, direction, boundary, mutation_index, gap):
        value = object.__new__(cls)
        object.__setattr__(value, "direction", direction)
        object.__setattr__(value, "boundary", boundary)
        object.__setattr__(value, "mutation_index", mutation_index)
        object.__setattr__(value, "gap", gap)
        return value

    def matches(self, direction, boundary, mutation_index, gap) -> bool:
        return (
            self.direction is direction
            and self.boundary is boundary
            and self.mutation_index == mutation_index
            and self.gap is gap
        )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RepositoryTransactionReceiptV1:
    direction: str
    status: str
    boundary_count: int
    mutation_count: int
    journal_record_count: int
    worktree_count: int
    embedded_count: int
    external_count: int
    failed_state_preserved: bool
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated transaction receipt required")

    @classmethod
    def create(
        cls,
        *,
        direction: SyntheticTransactionDirection,
        boundary_count: int,
        mutation_count: int,
        journal_record_count: int,
        failed_state_preserved: bool,
    ) -> RepositoryTransactionReceiptV1:
        body = {
            "direction": direction.value,
            "status": "complete",
            "boundary_count": boundary_count,
            "mutation_count": mutation_count,
            "journal_record_count": journal_record_count,
            "worktree_count": 11,
            "embedded_count": 8,
            "external_count": 3,
            "failed_state_preserved": failed_state_preserved,
        }
        if (
            type(direction) is not SyntheticTransactionDirection
            or type(boundary_count) is not int
            or boundary_count not in {1, 3, 4, 5, 8}
            or type(mutation_count) is not int
            or mutation_count < 1
            or journal_record_count < mutation_count * 3
            or type(failed_state_preserved) is not bool
        ):
            raise RepositoryTransactionError(
                "repository_receipt_invalid"
            )
        fingerprint = hashlib.sha256(
            json.dumps(
                body, ensure_ascii=True, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        value = object.__new__(cls)
        for name, item in body.items():
            object.__setattr__(value, name, item)
        object.__setattr__(value, "receipt_fingerprint", fingerprint)
        return value
