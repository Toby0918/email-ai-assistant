"""Pure contracts for fresh R2 synthetic verification evidence."""

from .contracts import (
    R2VerificationBundleV1,
    R2VerificationEvidenceV1,
    build_verification_evidence,
)
from .matrix import R2SemanticGapCaseV1, semantic_gap_matrix

__all__ = [
    "R2SemanticGapCaseV1",
    "R2VerificationBundleV1",
    "R2VerificationEvidenceV1",
    "build_verification_evidence",
    "semantic_gap_matrix",
]
