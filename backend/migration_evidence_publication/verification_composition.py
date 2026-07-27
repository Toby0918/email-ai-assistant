"""Authorized parent composition for the read-only verifier process."""

from __future__ import annotations

from backend.migration_evidence_verifier import (
    PackageVerificationObservationV1,
    PackageVerificationStatus,
    verify_package_in_separate_process,
)

from .canonical import fingerprint
from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    RealPreflightAuthorizationV1,
    validate_real_host_authorization,
)
from .errors import MigrationEvidencePublicationError
from .publication_receipts import (
    MigrationEvidenceCreatedReceiptV1,
    MigrationEvidenceVerifiedReceiptV1,
    _PublicationBinding,
    _mint_verified_receipt,
    _publication_binding,
)
from .published_scope import _claim_published_target


_ERROR = "MIGRATION_EVIDENCE_VERIFICATION_REJECTED"


def verify_published_migration_evidence(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    created_receipt: MigrationEvidenceCreatedReceiptV1,
) -> MigrationEvidenceVerifiedReceiptV1:
    """Verify one published target through the fixed child process."""

    try:
        profile_snapshot = CutoverProfileV1.from_mapping(
            profile.to_mapping()
        )
        created = _publication_binding(created_receipt)
        _require_context(
            profile=profile_snapshot,
            authorization=authorization,
            operation_fingerprint=operation_fingerprint,
            observed_at_epoch=observed_at_epoch,
            created=created,
        )
        target = _claim_published_target(created_receipt)
        observation = verify_package_in_separate_process(package=target)
        _require_matching_observation(created, observation)
        return _mint_verified_receipt(
            created=created,
            authorization_fingerprint=(
                authorization.authorization_fingerprint
            ),
            process_fingerprint=observation.process_fingerprint,
        )
    except Exception:
        raise MigrationEvidencePublicationError(_ERROR) from None


def _require_context(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    created: _PublicationBinding,
) -> None:
    if (
        type(authorization) is not RealPreflightAuthorizationV1
        or created.receipt_type
        != "MigrationEvidenceCreatedReceiptV1"
        or created.operation_fingerprint != operation_fingerprint
        or created.profile_fingerprint != profile.profile_fingerprint
        or created.master_fingerprint != _master_fingerprint(profile)
    ):
        raise ValueError(_ERROR)
    validation = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="real_preflight",
        expected_operation_fingerprint=operation_fingerprint,
        expected_phase="evidence_verification",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    if validation.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise ValueError(_ERROR)


def _require_matching_observation(
    created: _PublicationBinding,
    observation: PackageVerificationObservationV1,
) -> None:
    counts = created.package_counts
    if (
        type(observation) is not PackageVerificationObservationV1
        or observation.status is not PackageVerificationStatus.VERIFIED
        or observation.review_fingerprint
        != created.review_fingerprint
        or observation.package_sha256 != created.package_sha256
        or observation.manifest_sha256 != created.manifest_sha256
        or observation.package_identity_fingerprint
        != created.package_identity_fingerprint
        or observation.counts_fingerprint
        != created.package_counts_fingerprint
        or (observation.files, observation.refs, observation.worktrees)
        != (counts.files, counts.refs, counts.worktrees)
    ):
        raise ValueError(_ERROR)


def _master_fingerprint(profile: CutoverProfileV1) -> str:
    return fingerprint(
        "migration-evidence-governing-master-v1",
        profile.governing_master_commit,
    )
