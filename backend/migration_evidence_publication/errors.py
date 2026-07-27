"""Fixed content-free failures for Issue #54 composition."""


_ERROR_CODES = frozenset(
    {
        "MIGRATION_EVIDENCE_REVIEW_REJECTED",
        "MIGRATION_EVIDENCE_PUBLICATION_REJECTED",
        "MIGRATION_EVIDENCE_VERIFICATION_REJECTED",
        "MIGRATION_EVIDENCE_RECEIPT_CHAIN_REJECTED",
    }
)


class MigrationEvidencePublicationError(ValueError):
    """A failure that intentionally carries no diagnostic input."""

    def __init__(
        self,
        code: str = "MIGRATION_EVIDENCE_REVIEW_REJECTED",
    ) -> None:
        if code not in _ERROR_CODES:
            code = "MIGRATION_EVIDENCE_REVIEW_REJECTED"
        super().__init__(code)
