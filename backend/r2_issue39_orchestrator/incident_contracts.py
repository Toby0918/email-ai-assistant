"""Content-free contract for the one reviewed closure-stage incident."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IncidentDispositionStatusV1(str, Enum):
    ARCHIVED = "INCIDENT_STAGE_ARCHIVED"
    ABSENT = "INCIDENT_STAGE_ABSENT"
    BLOCKED_SOURCE = "BLOCKED_INCIDENT_SOURCE"
    BLOCKED_DESTINATION = "BLOCKED_INCIDENT_DESTINATION"
    BLOCKED_ARTIFACT = "BLOCKED_INCIDENT_ARTIFACT"
    BLOCKED_DACL = "BLOCKED_INCIDENT_DACL"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, repr=False)
class IncidentStageContractV1:
    contract_fingerprint: str = field(repr=False)
    artifact_count: int
    move_count: int
    delete_count: int
    cleanup_count: int


@dataclass(frozen=True, slots=True)
class IncidentDispositionResultV1:
    status: IncidentDispositionStatusV1
    verified_artifacts: int
    moves: int
    deletions: int

    def counts(self) -> tuple[int, int, int]:
        return self.verified_artifacts, self.moves, self.deletions


def fixed_incident_stage_contract_v1() -> IncidentStageContractV1:
    return IncidentStageContractV1(
        "81ff139b39debf747b25d1bb5317d0424c61537881229844266f1834243493de",
        2,
        1,
        0,
        0,
    )
