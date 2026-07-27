"""The publication composition's exact create-only core bridge."""

from backend.migration_evidence import (
    MigrationEvidenceStatus,
)
from backend.migration_evidence.package import (
    create_migration_evidence_package_binding,
)
from backend.migration_evidence.results import (
    MigrationEvidenceCreationResult,
)


def create_migration_evidence_package(**values: object):
    """Call only the creator-owned commit-binding seam."""

    return create_migration_evidence_package_binding(**values)

__all__ = [
    "MigrationEvidenceCreationResult",
    "MigrationEvidenceStatus",
    "create_migration_evidence_package",
]
