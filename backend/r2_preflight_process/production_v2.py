"""Dormant six-verb preflight root for Issue #110."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum

from backend.r2_production_binding.catalog import (
    OperatorSurfaceV2,
    executable_verb_map_v2,
)


PREFLIGHT_PRODUCTION_VERBS_V2 = executable_verb_map_v2(
    OperatorSurfaceV2.PREFLIGHT
)


class PreflightProductionStatusV2(str, Enum):
    COMPLETED = "PREFLIGHT_COMPLETE"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_EXECUTION_CONFIRMATION = "BLOCKED_EXECUTION_CONFIRMATION"
    BLOCKED_FINGERPRINT = "BLOCKED_FINGERPRINT"
    BLOCKED_REPLAY = "BLOCKED_REPLAY"
    BLOCKED_ACTION = "BLOCKED_ACTION"
    DORMANT_NO_ISSUE39_APPROVAL = "DORMANT_NO_ISSUE39_APPROVAL"


@dataclass(frozen=True, slots=True)
class PreflightProductionResultV2:
    status: PreflightProductionStatusV2
    accepted: int
    rejected: int
    read_operations: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.read_operations

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "read_operations": self.read_operations,
        }


def run_preflight_production_v2(
    *,
    argv,
    terminal=None,
    binding=None,
    adapter=None,
    execution_confirmation_claims=None,
    expected_prior_journal_head_fingerprint=None,
    observed_at_epoch=None,
):
    """Return before inspecting every argument or acquiring a capability."""

    return _dormant()


def dormant_preflight_production_v2(*, argv):
    """Return the only Issue #110 production state without reading ``argv``."""

    return _dormant()


def main(*, argv=None, bootstrap=None) -> int:
    """Emit one content-free line; neither argument is inspected."""

    result = _dormant()
    sys.stdout.write(
        f"{result.status.value} accepted=0 rejected=0 read_operations=0\n"
    )
    sys.stdout.flush()
    return 0


def _dormant() -> PreflightProductionResultV2:
    return PreflightProductionResultV2(
        PreflightProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        0,
        0,
        0,
    )
