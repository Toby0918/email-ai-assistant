"""Closed gap vocabulary and dependency-ordered ownership registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClosureGap(str, Enum):
    TERMINAL_CONTRACT = "terminal_contract"
    PRODUCTION_COMPOSITION = "production_composition"
    GIT_BYTE_REPRODUCIBILITY = "git_byte_reproducibility"
    CRASH_RECOVERY = "crash_recovery"
    RETENTION_NO_DELETION = "retention_no_deletion"
    RUNBOOK_SEMANTIC_CLOSURE = "runbook_semantic_closure"
    WINDOWS_CI_PROVENANCE = "windows_ci_provenance"
    GLOBAL_GATES = "global_gates"


class ClosureGate(str, Enum):
    FINAL_MASTER_BINDING = "final_master_binding"
    CLOSURE_SURFACE_COMPLETENESS = "closure_surface_completeness"
    PRODUCTION_COMPOSITION = "production_composition"
    GIT_BYTES = "git_bytes"
    DEPENDENCY_ACTION_PROVENANCE = "dependency_action_provenance"
    WINDOWS_NATIVE = "windows_native"
    PORTABLE_FULL_SUITE = "portable_full_suite"
    RUNBOOK_SEMANTICS = "runbook_semantics"
    CRASH_RECOVERY = "crash_recovery"
    RETENTION_NO_DELETION = "retention_no_deletion"
    DOCUMENTATION = "documentation"
    MECHANICAL_ARCHITECTURE = "mechanical_architecture"
    LEAKAGE = "leakage"
    MAINTENANCE_SCOPE = "maintenance_scope"


class FindingClassification(str, Enum):
    EXISTING_GAP_INSTANCE = "existing_gap_instance"
    SURFACE_COMPLETENESS_DEFECT = "surface_completeness_defect"
    EVIDENCE_DEFECT = "evidence_defect"
    EXTERNAL_AUTHORITY_OR_STATE = "external_authority_or_state"
    OUT_OF_SCOPE_NONBLOCKING = "out_of_scope_nonblocking"
    SECURITY_INCIDENT = "security_incident"
    DECISION_CONTRADICTION = "decision_contradiction"
    DUPLICATE_OR_HISTORICAL = "duplicate_or_historical"


class FinalMasterClosureStatus(str, Enum):
    ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW = (
        "ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW"
    )


@dataclass(frozen=True, slots=True)
class ClosureGapRegistrationV1:
    gap: ClosureGap
    blocked_by: tuple[ClosureGap, ...]
    owning_issues: tuple[int, ...]
    decision_ids: tuple[str, ...]


_ORDERED_GAPS = (
    (
        ClosureGap.TERMINAL_CONTRACT,
        (86,),
        ("D-R2-CLOSURE-1", "D-R2-FINITE-MAP-1"),
    ),
    (
        ClosureGap.PRODUCTION_COMPOSITION,
        (87, 88, 89, 90, 91, 94, 95, 96),
        ("D-R2-COMPOSITION-1",),
    ),
    (
        ClosureGap.GIT_BYTE_REPRODUCIBILITY,
        (92,),
        ("D-R2-GIT-BYTES-1",),
    ),
    (
        ClosureGap.CRASH_RECOVERY,
        (93, 94, 95, 96, 97),
        ("D-R2-CRASH-RECOVERY-1",),
    ),
    (
        ClosureGap.RETENTION_NO_DELETION,
        (98,),
        ("D-R2-RETENTION-1",),
    ),
    (
        ClosureGap.RUNBOOK_SEMANTIC_CLOSURE,
        (99,),
        ("D-R2-RUNBOOK-DRIFT-1",),
    ),
    (
        ClosureGap.WINDOWS_CI_PROVENANCE,
        (100,),
        ("D-R2-CI-PROVENANCE-1",),
    ),
    (
        ClosureGap.GLOBAL_GATES,
        (101, 102),
        ("D-R2-GLOBAL-GATES-1",),
    ),
)

_ORDERED_GATES = tuple(ClosureGate)
_FINDING_CLASSIFICATIONS = tuple(FindingClassification)


def closure_gap_registry() -> tuple[ClosureGapRegistrationV1, ...]:
    """Return the exact finite dependency-ordered closure map."""

    return tuple(
        ClosureGapRegistrationV1(
            gap=gap,
            blocked_by=(() if index == 0 else (_ORDERED_GAPS[index - 1][0],)),
            owning_issues=issues,
            decision_ids=decisions,
        )
        for index, (gap, issues, decisions) in enumerate(_ORDERED_GAPS)
    )


def closure_map_fingerprint() -> str:
    """Fingerprint the exact gaps, dependencies, issue owners, and decisions."""

    from ._canonical import fingerprint

    return fingerprint(
        "r2-final-master-closure-map-v1",
        [
            {
                "gap": item.gap.value,
                "blocked_by": [gap.value for gap in item.blocked_by],
                "owning_issues": list(item.owning_issues),
                "decision_ids": list(item.decision_ids),
            }
            for item in closure_gap_registry()
        ],
    )


def closure_gate_registry() -> tuple[ClosureGate, ...]:
    """Return the exact fourteen final-master gate kinds."""

    return _ORDERED_GATES


def finding_classification_registry() -> tuple[FindingClassification, ...]:
    """Return the closed taxonomy for findings discovered after #86."""

    return _FINDING_CLASSIFICATIONS
