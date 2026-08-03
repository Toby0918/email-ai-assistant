"""Closed operator phases generated from the executable command catalog."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.r2_production_binding.catalog import (
    OperatorCommandEffectV2,
    command_catalog_v2,
)
from backend.r2_retention_ledger_v2 import RetentionObjectKindV2
from backend.r2_transaction_journal_v2 import JournalRecordTypeV2, TerminalStateV2
from backend.r2_transaction_journal_v2._canonical import fingerprint


class OperatorPhaseV2(str, Enum):
    PREFLIGHT = "preflight"
    EVIDENCE_PUBLICATION = "evidence_publication"
    FORWARD = "forward"
    FORWARD_RECOVERY = "forward_recovery"
    ROLLBACK = "rollback"
    ROLLBACK_RECOVERY = "rollback_recovery"
    RETENTION_RECONCILIATION = "retention_reconciliation"
    HUMAN_FINAL_REVIEW = "human_final_review"


@dataclass(frozen=True, slots=True)
class R2OperatorPhaseRuleV2:
    phase: OperatorPhaseV2
    allowed_commands: tuple[str, ...]
    allowed_effects: tuple[OperatorCommandEffectV2, ...]
    next_phases: tuple[OperatorPhaseV2, ...]
    required_evidence: tuple[str, ...]
    deletion_capability_count: int

    def to_mapping(self):
        return {
            "phase": self.phase.value,
            "allowed_commands": list(self.allowed_commands),
            "allowed_effects": [item.value for item in self.allowed_effects],
            "next_phases": [item.value for item in self.next_phases],
            "required_evidence": list(self.required_evidence),
            "deletion_capability_count": self.deletion_capability_count,
        }


def operator_state_machine_v2():
    by_verb = {item.verb: item for item in command_catalog_v2()}
    definitions = (
        (OperatorPhaseV2.PREFLIGHT, tuple(item.verb for item in command_catalog_v2() if item.effect is OperatorCommandEffectV2.READ_ONLY), (OperatorPhaseV2.EVIDENCE_PUBLICATION,), ("exact_preflight_receipts",)),
        (OperatorPhaseV2.EVIDENCE_PUBLICATION, ("publish",), (OperatorPhaseV2.FORWARD,), ("reviewed_evidence_genesis",)),
        (OperatorPhaseV2.FORWARD, ("execute",), (OperatorPhaseV2.FORWARD, OperatorPhaseV2.FORWARD_RECOVERY, OperatorPhaseV2.RETENTION_RECONCILIATION), ("unified_journal_commit",)),
        (OperatorPhaseV2.FORWARD_RECOVERY, ("recovery-inspection", "resume", "rollback"), (OperatorPhaseV2.FORWARD, OperatorPhaseV2.ROLLBACK), ("tri_state_inspection", "fresh_authority")),
        (OperatorPhaseV2.ROLLBACK, ("rollback",), (OperatorPhaseV2.ROLLBACK, OperatorPhaseV2.ROLLBACK_RECOVERY, OperatorPhaseV2.RETENTION_RECONCILIATION), ("lifo_reverse_commit",)),
        (OperatorPhaseV2.ROLLBACK_RECOVERY, ("recovery-inspection", "rollback"), (OperatorPhaseV2.ROLLBACK, OperatorPhaseV2.RETENTION_RECONCILIATION), ("tri_state_inspection", "fresh_recovery_authority")),
        (OperatorPhaseV2.RETENTION_RECONCILIATION, (), (OperatorPhaseV2.HUMAN_FINAL_REVIEW,), ("object_level_retention_proof", "zero_deletion_capability")),
        (OperatorPhaseV2.HUMAN_FINAL_REVIEW, (), (), ("human_review_only", "no_execution_authority")),
    )
    return tuple(_rule(phase, commands, next_phases, evidence, by_verb) for phase, commands, next_phases, evidence in definitions)


def operator_package_semantics_fingerprint_v2():
    body = {
        "catalog": [item.to_mapping() for item in command_catalog_v2()],
        "state_machine": [item.to_mapping() for item in operator_state_machine_v2()],
        "retention_objects": [item.value for item in RetentionObjectKindV2],
        "journal_records": [item.value for item in JournalRecordTypeV2],
        "terminal_states": [item.value for item in TerminalStateV2],
        "historical_command_count": 0,
        "deletion_capability_count": 0,
    }
    return fingerprint("r2-operator-package-semantics-v2", body)


def _rule(phase, commands, next_phases, evidence, by_verb):
    effects = tuple(dict.fromkeys(by_verb[verb].effect for verb in commands))
    return R2OperatorPhaseRuleV2(phase, commands, effects, next_phases, evidence, 0)
