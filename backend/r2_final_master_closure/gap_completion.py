"""Semantic partition from eight closure gaps to fourteen gate receipts."""

from ._canonical import fingerprint
from .errors import FinalMasterClosureError
from .global_gates import R2GlobalGateCoordinatorV1
from .vocabulary import ClosureGate, ClosureGap


_GAP_GATE_OWNERSHIP = {
    ClosureGap.TERMINAL_CONTRACT: (
        ClosureGate.FINAL_MASTER_BINDING,
        ClosureGate.CLOSURE_SURFACE_COMPLETENESS,
    ),
    ClosureGap.PRODUCTION_COMPOSITION: (ClosureGate.PRODUCTION_COMPOSITION,),
    ClosureGap.GIT_BYTE_REPRODUCIBILITY: (ClosureGate.GIT_BYTES,),
    ClosureGap.CRASH_RECOVERY: (ClosureGate.CRASH_RECOVERY,),
    ClosureGap.RETENTION_NO_DELETION: (ClosureGate.RETENTION_NO_DELETION,),
    ClosureGap.RUNBOOK_SEMANTIC_CLOSURE: (ClosureGate.RUNBOOK_SEMANTICS,),
    ClosureGap.WINDOWS_CI_PROVENANCE: (
        ClosureGate.DEPENDENCY_ACTION_PROVENANCE,
        ClosureGate.WINDOWS_NATIVE,
        ClosureGate.PORTABLE_FULL_SUITE,
    ),
    ClosureGap.GLOBAL_GATES: (
        ClosureGate.DOCUMENTATION,
        ClosureGate.MECHANICAL_ARCHITECTURE,
        ClosureGate.LEAKAGE,
        ClosureGate.MAINTENANCE_SCOPE,
    ),
}


def gap_completion_evidence_fingerprint_v1(gap, coordinator):
    owned = tuple(
        gate for gates in _GAP_GATE_OWNERSHIP.values() for gate in gates
    )
    if (
        type(gap) is not ClosureGap
        or type(coordinator) is not R2GlobalGateCoordinatorV1
        or len(owned) != len(ClosureGate)
        or set(owned) != set(ClosureGate)
    ):
        raise FinalMasterClosureError()
    receipt_by_gate = {item.gate: item for item in coordinator.gate_receipts}
    return fingerprint(
        "r2-closure-gap-completion-evidence-v1",
        {
            "gap": gap.value,
            "coordinator_receipt_fingerprint": (
                coordinator.coordinator_receipt_fingerprint
            ),
            "gate_receipts": [
                {
                    "gate": gate.value,
                    "receipt_fingerprint": receipt_by_gate[gate].receipt_fingerprint,
                }
                for gate in _GAP_GATE_OWNERSHIP[gap]
            ],
        },
    )
