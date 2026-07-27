"""Reviewed Migration Evidence Package publication composition."""

__all__ = [
    "MigrationEvidenceCreatedReceiptV1",
    "MigrationEvidencePackageCountsV1",
    "MigrationEvidencePublicationError",
    "MigrationEvidenceReceiptSetV1",
    "MigrationEvidenceReviewCountsV1",
    "MigrationEvidenceReviewReceiptV1",
    "MigrationEvidenceVerifiedReceiptV1",
    "ProfileBoundEvidenceSelectionV1",
    "publish_reviewed_migration_evidence",
    "require_matching_migration_evidence_receipts",
    "review_profile_bound_migration_evidence",
    "verify_published_migration_evidence",
]


def _created_receipt():
    from .publication_receipts import MigrationEvidenceCreatedReceiptV1

    return MigrationEvidenceCreatedReceiptV1


def _package_counts():
    from .publication_receipts import MigrationEvidencePackageCountsV1

    return MigrationEvidencePackageCountsV1


def _publication_error():
    from .errors import MigrationEvidencePublicationError

    return MigrationEvidencePublicationError


def _receipt_set():
    from .receipt_set import MigrationEvidenceReceiptSetV1

    return MigrationEvidenceReceiptSetV1


def _review_counts():
    from .receipts import MigrationEvidenceReviewCountsV1

    return MigrationEvidenceReviewCountsV1


def _review_receipt():
    from .receipts import MigrationEvidenceReviewReceiptV1

    return MigrationEvidenceReviewReceiptV1


def _verified_receipt():
    from .publication_receipts import MigrationEvidenceVerifiedReceiptV1

    return MigrationEvidenceVerifiedReceiptV1


def _selection():
    from .selection import ProfileBoundEvidenceSelectionV1

    return ProfileBoundEvidenceSelectionV1


def _publish():
    from .publication import publish_reviewed_migration_evidence

    return publish_reviewed_migration_evidence


def _require_receipts():
    from .receipt_set import require_matching_migration_evidence_receipts

    return require_matching_migration_evidence_receipts


def _review():
    from .review import review_profile_bound_migration_evidence

    return review_profile_bound_migration_evidence


def _verify():
    from .verification_composition import (
        verify_published_migration_evidence,
    )

    return verify_published_migration_evidence


_LOADERS = {
    "MigrationEvidenceCreatedReceiptV1": _created_receipt,
    "MigrationEvidencePackageCountsV1": _package_counts,
    "MigrationEvidencePublicationError": _publication_error,
    "MigrationEvidenceReceiptSetV1": _receipt_set,
    "MigrationEvidenceReviewCountsV1": _review_counts,
    "MigrationEvidenceReviewReceiptV1": _review_receipt,
    "MigrationEvidenceVerifiedReceiptV1": _verified_receipt,
    "ProfileBoundEvidenceSelectionV1": _selection,
    "publish_reviewed_migration_evidence": _publish,
    "require_matching_migration_evidence_receipts": _require_receipts,
    "review_profile_bound_migration_evidence": _review,
    "verify_published_migration_evidence": _verify,
}


def __getattr__(name: str):
    """Load only the requested review, create, or verify capability."""

    try:
        loader = _LOADERS[name]
    except KeyError:
        raise AttributeError(name) from None
    return loader()
