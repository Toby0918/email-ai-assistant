"""Dormant single-verb evidence root for Issue #110."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum

from backend.r2_production_binding.catalog import (
    OperatorSurfaceV2,
    executable_verb_map_v2,
)


EVIDENCE_PRODUCTION_VERBS_V2 = executable_verb_map_v2(
    OperatorSurfaceV2.EVIDENCE
)


class EvidenceProductionStatusV2(str, Enum):
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
class EvidenceProductionResultV2:
    status: EvidenceProductionStatusV2
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


def run_evidence_production_v2(
    *,
    argv,
    terminal=None,
    binding=None,
    adapter=None,
    reviewed_evidence_fingerprint=None,
    execution_confirmation_claims=None,
    expected_prior_journal_head_fingerprint=None,
    observed_at_epoch=None,
    journal_owner_fingerprint=None,
    genesis_nonce=None,
):
    """Return before inspecting every argument or acquiring a capability."""

    return _dormant()


def dormant_evidence_production_v2(*, argv):
    """Return the only Issue #110 production state without reading ``argv``."""

    return _dormant()


def main(*, argv=None, bootstrap=None) -> int:
    """Emit one content-free line; neither argument is inspected."""

    result = _dormant()
    sys.stdout.write(
        f"{result.status.value} accepted=0 rejected=0 published=0\n"
    )
    sys.stdout.flush()
    return 0


def _dormant() -> EvidenceProductionResultV2:
    return EvidenceProductionResultV2(
        EvidenceProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        0,
        0,
        0,
    )
