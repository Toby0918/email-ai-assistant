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
    verification_public_key: bytes


_KEYS = tuple(bytes.fromhex(value) for value in (
    "9cb7cd1c4efdd4908f7af2a9b3bf450bf8072482b2d0398e1f904929d305beee",
    "609df0856a9fc70e7b09bb6c47337c649894826db7f144b84754cfb7b9c538d1",
    "c3c1f440f8706f1c18f71ac05c510f5296b05b77921dda59465a744cffdf2873",
    "c72347def07454e1d27b16deba6bd0c533b9612b258921ebbf900d77709acc8b",
    "79ba03a98f33e786429ffbfc384708dd4d4db002843d03b39cdfb18d805965aa",
    "473a3115d49d25a462fca247495faf15e9e95214ea78044abbee49e9d0efeb58",
    "c9db5d551b43bfb81d9d46adfa00061067ecd70067f405da1624e36033914633",
    "4dac025e27c1ec0a1e0493b014079009dc90a0f0271ae2bf20b700ffcc84e14c",
    "cee003c822ff18da86b79f448a79d0a3d8037340d42c23bb0402590419298b03",
    "1c43993142ba36e3db23a17969c8636bb345e03518d0110b04f1c812bd3d5fdf",
    "9c0a4374ee55a7762486f6dbc2400644ffbc2c4e1a9fb74118a3a85211b2f6a5",
    "6a398607d471583890c7040e4f653043221d312089566ce079168e8c98fbbbc5",
    "c07e985530416b1027ec2bc19dd648a8b366838cd1439133193cbcbf47ed09c8",
    "ecf1302df9f6a3086d4f57ccf3cdff4b9ed13b2bfbd4991bab22c97434b1a3e0",
))

_REGISTRY = tuple(
    GateEvidenceRegistrationV1(*values, key)
    for values, key in zip((
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
    ), _KEYS, strict=True)
)


def gate_evidence_registry():
    return _REGISTRY
