"""Closed independent producer and review-domain registry for fourteen gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vocabulary import ClosureGate


class ReviewDomainV1(str, Enum):
    STANDARDS = "standards"
    SPEC = "spec"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    MECHANICAL = "mechanical"
    LEAKAGE = "leakage"
    OPERATOR_REVIEW = "operator_review"


class GateEvidenceProducerV1(str, Enum):
    FINAL_MASTER_VERIFIER = "final_master_verifier"
    SPEC_REVIEW = "spec_review"
    SECURITY_REVIEW = "security_review"
    GIT_BYTE_VERIFIER = "git_byte_verifier"
    CI_PROVENANCE_RECONCILER = "ci_provenance_reconciler"
    WINDOWS_NATIVE_VERIFIER = "windows_native_verifier"
    PORTABLE_SUITE_VERIFIER = "portable_suite_verifier"
    OPERATOR_RUNBOOK_REVIEW = "operator_runbook_review"
    CRASH_RECOVERY_VERIFIER = "crash_recovery_verifier"
    RETENTION_VERIFIER = "retention_verifier"
    DOCUMENTATION_REVIEW = "documentation_review"
    STANDARDS_REVIEW = "standards_review"
    LEAKAGE_SCANNER = "leakage_scanner"
    MAINTENANCE_REVIEW = "maintenance_review"


class GlobalGateStatusV1(str, Enum):
    GLOBAL_GATES_VERIFIED = "GLOBAL_GATES_VERIFIED"


@dataclass(frozen=True, slots=True)
class GateEvidenceRegistrationV1:
    gate: ClosureGate
    producer: GateEvidenceProducerV1
    review_domain: ReviewDomainV1


_REGISTRY = tuple(
    GateEvidenceRegistrationV1(*values)
    for values in (
        (ClosureGate.FINAL_MASTER_BINDING, GateEvidenceProducerV1.FINAL_MASTER_VERIFIER, ReviewDomainV1.SPEC),
        (ClosureGate.CLOSURE_SURFACE_COMPLETENESS, GateEvidenceProducerV1.SPEC_REVIEW, ReviewDomainV1.SPEC),
        (ClosureGate.PRODUCTION_COMPOSITION, GateEvidenceProducerV1.SECURITY_REVIEW, ReviewDomainV1.SECURITY),
        (ClosureGate.GIT_BYTES, GateEvidenceProducerV1.GIT_BYTE_VERIFIER, ReviewDomainV1.SECURITY),
        (ClosureGate.DEPENDENCY_ACTION_PROVENANCE, GateEvidenceProducerV1.CI_PROVENANCE_RECONCILER, ReviewDomainV1.SECURITY),
        (ClosureGate.WINDOWS_NATIVE, GateEvidenceProducerV1.WINDOWS_NATIVE_VERIFIER, ReviewDomainV1.STANDARDS),
        (ClosureGate.PORTABLE_FULL_SUITE, GateEvidenceProducerV1.PORTABLE_SUITE_VERIFIER, ReviewDomainV1.STANDARDS),
        (ClosureGate.RUNBOOK_SEMANTICS, GateEvidenceProducerV1.OPERATOR_RUNBOOK_REVIEW, ReviewDomainV1.OPERATOR_REVIEW),
        (ClosureGate.CRASH_RECOVERY, GateEvidenceProducerV1.CRASH_RECOVERY_VERIFIER, ReviewDomainV1.SECURITY),
        (ClosureGate.RETENTION_NO_DELETION, GateEvidenceProducerV1.RETENTION_VERIFIER, ReviewDomainV1.SECURITY),
        (ClosureGate.DOCUMENTATION, GateEvidenceProducerV1.DOCUMENTATION_REVIEW, ReviewDomainV1.DOCUMENTATION),
        (ClosureGate.MECHANICAL_ARCHITECTURE, GateEvidenceProducerV1.STANDARDS_REVIEW, ReviewDomainV1.MECHANICAL),
        (ClosureGate.LEAKAGE, GateEvidenceProducerV1.LEAKAGE_SCANNER, ReviewDomainV1.LEAKAGE),
        (ClosureGate.MAINTENANCE_SCOPE, GateEvidenceProducerV1.MAINTENANCE_REVIEW, ReviewDomainV1.OPERATOR_REVIEW),
    )
)


def gate_evidence_registry():
    return _REGISTRY
