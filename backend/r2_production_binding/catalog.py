"""Single executable R2 command catalog shared by all process roots."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vocabulary import ProductionCommandV2


class OperatorSurfaceV2(str, Enum):
    PREFLIGHT = "preflight"
    EVIDENCE = "evidence"
    TRANSACTION = "transaction"


class OperatorCommandEffectV2(str, Enum):
    READ_ONLY = "read_only"
    PUBLICATION = "publication"
    FORWARD = "forward"
    RESUME = "resume"
    ROLLBACK = "rollback"


@dataclass(frozen=True, slots=True)
class R2OperatorCommandV2:
    ordinal: int
    surface: OperatorSurfaceV2
    verb: str
    command: ProductionCommandV2
    effect: OperatorCommandEffectV2
    acknowledgement: str
    max_operations: int
    destructive_capability_count: int

    def to_mapping(self):
        return {
            "ordinal": self.ordinal,
            "surface": self.surface.value,
            "verb": self.verb,
            "command": self.command.value,
            "effect": self.effect.value,
            "acknowledgement": self.acknowledgement,
            "max_operations": self.max_operations,
            "destructive_capability_count": self.destructive_capability_count,
        }


_PREFLIGHT = "ACKNOWLEDGE_R2_PREFLIGHT"
_EVIDENCE = "ACKNOWLEDGE_R2_EVIDENCE_PUBLICATION"
_TRANSACTION = "ACKNOWLEDGE_R2_TRANSACTION_ACTION"
_DEFINITIONS = (
    (OperatorSurfaceV2.PREFLIGHT, "current-topology", ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT, OperatorCommandEffectV2.READ_ONLY, _PREFLIGHT),
    (OperatorSurfaceV2.PREFLIGHT, "host-baseline", ProductionCommandV2.HOST_BASELINE, OperatorCommandEffectV2.READ_ONLY, _PREFLIGHT),
    (OperatorSurfaceV2.PREFLIGHT, "evidence-review", ProductionCommandV2.EVIDENCE_REVIEW, OperatorCommandEffectV2.READ_ONLY, _PREFLIGHT),
    (OperatorSurfaceV2.PREFLIGHT, "evidence-verification", ProductionCommandV2.EVIDENCE_VERIFICATION, OperatorCommandEffectV2.READ_ONLY, _PREFLIGHT),
    (OperatorSurfaceV2.PREFLIGHT, "final-audit-readiness", ProductionCommandV2.FINAL_AUDIT_READINESS, OperatorCommandEffectV2.READ_ONLY, _PREFLIGHT),
    (OperatorSurfaceV2.PREFLIGHT, "recovery-inspection", ProductionCommandV2.RECOVERY_INSPECTION, OperatorCommandEffectV2.READ_ONLY, _PREFLIGHT),
    (OperatorSurfaceV2.EVIDENCE, "publish", ProductionCommandV2.EVIDENCE_PUBLICATION, OperatorCommandEffectV2.PUBLICATION, _EVIDENCE),
    (OperatorSurfaceV2.TRANSACTION, "execute", ProductionCommandV2.EXECUTE, OperatorCommandEffectV2.FORWARD, _TRANSACTION),
    (OperatorSurfaceV2.TRANSACTION, "resume", ProductionCommandV2.RESUME, OperatorCommandEffectV2.RESUME, _TRANSACTION),
    (OperatorSurfaceV2.TRANSACTION, "rollback", ProductionCommandV2.ROLLBACK, OperatorCommandEffectV2.ROLLBACK, _TRANSACTION),
)
_CATALOG = tuple(R2OperatorCommandV2(index, *definition, 1, 0) for index, definition in enumerate(_DEFINITIONS))


def command_catalog_v2():
    return _CATALOG


def executable_verb_map_v2(surface):
    if type(surface) is not OperatorSurfaceV2:
        raise ValueError("R2_OPERATOR_RUNBOOK_INVALID")
    return {item.verb: item.command for item in _CATALOG if item.surface is surface}


def resolve_operator_command_v2(surface, verb):
    if type(surface) is not OperatorSurfaceV2 or type(verb) is not str:
        raise ValueError("R2_OPERATOR_RUNBOOK_INVALID")
    matches = tuple(item for item in _CATALOG if item.surface is surface and item.verb == verb)
    if len(matches) != 1:
        raise ValueError("R2_OPERATOR_RUNBOOK_INVALID")
    return matches[0]
