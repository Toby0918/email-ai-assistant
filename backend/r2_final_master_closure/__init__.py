"""Pure contracts for the finite R2 final-master closure program."""

from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError
from .evidence import R2ClosureGapProofV1, R2ClosureGateReceiptV1
from .global_gate_registry import (
    GateEvidenceProducerV1,
    GateEvidenceRegistrationV1,
    GlobalGateStatusV1,
    ReviewDomainV1,
    gate_evidence_registry,
)
from .global_gate_evidence import R2GlobalGateEvidenceV1
from .global_gates import R2GlobalGateCoordinatorV1
from .terminal import R2FinalMasterClosureReceiptV1
from .vocabulary import (
    ClosureGate,
    ClosureGap,
    ClosureGapRegistrationV1,
    FinalMasterClosureStatus,
    FindingClassification,
    closure_gate_registry,
    closure_gap_registry,
    closure_map_fingerprint,
    finding_classification_registry,
)

__all__ = [
    "ClosureGate",
    "ClosureGap",
    "ClosureGapRegistrationV1",
    "FinalMasterBindingV1",
    "FinalMasterClosureError",
    "FinalMasterClosureStatus",
    "FindingClassification",
    "GateEvidenceProducerV1",
    "GateEvidenceRegistrationV1",
    "GlobalGateStatusV1",
    "R2ClosureGateReceiptV1",
    "R2ClosureGapProofV1",
    "R2FinalMasterClosureReceiptV1",
    "R2GlobalGateCoordinatorV1",
    "R2GlobalGateEvidenceV1",
    "ReviewDomainV1",
    "closure_gate_registry",
    "closure_gap_registry",
    "closure_map_fingerprint",
    "finding_classification_registry",
    "gate_evidence_registry",
]
