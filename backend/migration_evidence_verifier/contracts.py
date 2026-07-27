"""Closed content-free outputs from the verifier process."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PackageVerificationStatus(str, Enum):
    """Fixed package-verification outcomes."""

    VERIFIED = "migration_evidence_package_verified"
    REJECTED = "migration_evidence_package_rejected"


@dataclass(frozen=True, slots=True, repr=False)
class PackageVerificationObservationV1:
    """Opaque hashes and bounded aggregate counts only."""

    status: PackageVerificationStatus
    review_fingerprint: str
    package_sha256: str
    manifest_sha256: str
    package_identity_fingerprint: str
    files: int
    refs: int
    worktrees: int
    counts_fingerprint: str
    process_fingerprint: str

    def __repr__(self) -> str:
        return "<PackageVerificationObservationV1>"
