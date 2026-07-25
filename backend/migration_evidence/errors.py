"""Fixed failures for migration-evidence review and package operations."""

from __future__ import annotations


class MigrationEvidenceError(RuntimeError):
    """A fixed-code failure with no native detail."""

    def __init__(self, code: str = "migration_evidence_review_failed") -> None:
        super().__init__(code)
        self.code = code
