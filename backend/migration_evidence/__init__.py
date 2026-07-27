"""Reviewed no-clobber migration evidence package interfaces."""

from .contract import (
    DirtyDisposition,
    DirtyEntryReview,
    DirtyReason,
    GitBaseline,
    HostBaseline,
    MigrationEvidenceCounts,
    MigrationEvidenceReview,
    MigrationEvidenceResult,
    MigrationEvidenceStatus,
    RemoteBaseline,
    ReviewedRef,
    ReviewedWorktree,
)
from .errors import MigrationEvidenceError

__all__ = [
    "DirtyDisposition",
    "DirtyEntryReview",
    "DirtyReason",
    "GitBaseline",
    "HostBaseline",
    "MigrationEvidenceCounts",
    "MigrationEvidenceError",
    "MigrationEvidenceReview",
    "MigrationEvidenceResult",
    "MigrationEvidenceStatus",
    "RemoteBaseline",
    "ReviewedRef",
    "ReviewedWorktree",
    "create_migration_evidence_package",
    "prepare_migration_evidence_review",
    "verify_migration_evidence_package",
]


def __getattr__(name: str):
    """Load only the exact requested capability."""

    if name == "create_migration_evidence_package":
        from .package import create_migration_evidence_package

        return create_migration_evidence_package
    if name == "prepare_migration_evidence_review":
        from .review import prepare_migration_evidence_review

        return prepare_migration_evidence_review
    if name == "verify_migration_evidence_package":
        from .verification import verify_migration_evidence_package

        return verify_migration_evidence_package
    raise AttributeError(name)
