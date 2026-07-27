"""Separately authorized create-only evidence publication composition."""

from __future__ import annotations

from .canonical import fingerprint, is_fingerprint
from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    validate_real_host_authorization,
)
from .creator_bridge import (
    MigrationEvidenceCreationResult,
    MigrationEvidenceStatus,
    create_migration_evidence_package,
)
from .errors import MigrationEvidencePublicationError
from .package_observation import observe_created_package
from .profile_binding import _ProfileBindings, _profile_bindings_for_review
from .publication_receipts import (
    MigrationEvidenceCreatedReceiptV1,
    MigrationEvidencePackageCountsV1,
    _mint_created_receipt,
)
from .published_scope import _register_published_target
from .receipts import (
    MigrationEvidenceReviewReceiptV1,
    _ReviewReceiptBinding,
    _receipt_binding,
)
from .review_bridge import (
    MigrationEvidenceReview,
    prepare_migration_evidence_review,
)
from .selection import (
    ProfileBoundEvidenceSelectionV1,
    _ClaimedEvidenceSelection,
    _claim_selection_for_publication,
)


_ERROR = "MIGRATION_EVIDENCE_PUBLICATION_REJECTED"


def publish_reviewed_migration_evidence(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    selection: ProfileBoundEvidenceSelectionV1,
    review_receipt: MigrationEvidenceReviewReceiptV1,
    confirmed_review_fingerprint: str,
) -> MigrationEvidenceCreatedReceiptV1:
    """Rediscover and create exactly one reviewed synthetic package."""

    try:
        return _publish_reviewed_migration_evidence(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation_fingerprint,
            observed_at_epoch=observed_at_epoch,
            selection=selection,
            review_receipt=review_receipt,
            confirmed_review_fingerprint=confirmed_review_fingerprint,
        )
    except Exception:
        raise MigrationEvidencePublicationError(_ERROR) from None


def _publish_reviewed_migration_evidence(
    **values: object,
) -> MigrationEvidenceCreatedReceiptV1:
    profile = CutoverProfileV1.from_mapping(values["profile"].to_mapping())
    receipt = _receipt_binding(values["review_receipt"])
    _require_context(
        profile=profile,
        authorization=values["authorization"],
        operation_fingerprint=values["operation_fingerprint"],
        observed_at_epoch=values["observed_at_epoch"],
        receipt=receipt,
        confirmed_review_fingerprint=values[
            "confirmed_review_fingerprint"
        ],
    )
    claimed = _claim_selection_for_publication(
        selection=values["selection"],
        receipt=values["review_receipt"],
    )
    review, bindings = _rediscover(
        profile,
        values["operation_fingerprint"],
        values["observed_at_epoch"],
        claimed,
    )
    _require_unchanged(profile, receipt, claimed, review, bindings)
    creation = create_migration_evidence_package(
        review=review,
        confirmed_review_fingerprint=values[
            "confirmed_review_fingerprint"
        ],
        expected_source_snapshot_fingerprint=(
            bindings.source_snapshot_fingerprint
        ),
    )
    observation = observe_created_package(package=claimed.inputs.target)
    _require_created_result(
        creation,
        observation,
        receipt,
        bindings,
    )
    created = _created_receipt(
        receipt=receipt,
        observation=observation,
        authorization=values["authorization"],
    )
    _register_published_target(created, claimed.inputs.target)
    return created


def _require_context(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    receipt: _ReviewReceiptBinding,
    confirmed_review_fingerprint: str,
) -> None:
    if (
        type(authorization) is not EvidencePublicationAuthorizationV1
        or not is_fingerprint(confirmed_review_fingerprint)
        or confirmed_review_fingerprint != receipt.review_fingerprint
        or receipt.operation_fingerprint != operation_fingerprint
        or receipt.profile_fingerprint != profile.profile_fingerprint
        or receipt.master_fingerprint != _master_fingerprint(profile)
    ):
        raise ValueError(_ERROR)
    validation = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="evidence_publication",
        expected_operation_fingerprint=operation_fingerprint,
        expected_phase="evidence_publication",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    if validation.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise ValueError(_ERROR)


def _rediscover(
    profile: CutoverProfileV1,
    operation_fingerprint: str,
    observed_at_epoch: int,
    claimed: _ClaimedEvidenceSelection,
) -> tuple[MigrationEvidenceReview, _ProfileBindings]:
    inputs = claimed.inputs
    baseline = inputs.baseline_collector.collect(
        profile=profile,
        authorization=inputs.baseline_authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    review = prepare_migration_evidence_review(
        repository_root=inputs.repository_root,
        target=inputs.target,
        approved_dirty_paths=inputs.approved_dirty_paths,
        reviewed_refs=inputs.reviewed_refs,
        approved_worktrees=inputs.approved_worktrees,
        host_baseline=baseline,
    )
    return review, _profile_bindings_for_review(
        review,
        inputs.approved_worktrees,
    )


def _require_unchanged(
    profile: CutoverProfileV1,
    receipt: _ReviewReceiptBinding,
    claimed: _ClaimedEvidenceSelection,
    review: MigrationEvidenceReview,
    bindings: _ProfileBindings,
) -> None:
    mapping = profile.to_mapping()
    if (
        review != claimed.confirmed_review
        or bindings != claimed.bindings
        or review.review_fingerprint != receipt.review_fingerprint
        or bindings.selection_fingerprint
        != receipt.selection_fingerprint
        or bindings.git_fingerprint != receipt.git_fingerprint
        or bindings.host_fingerprint != receipt.host_fingerprint
        or bindings.counts_fingerprint != receipt.counts_fingerprint
        or mapping["evidence_roles"] != bindings.evidence_roles
        or mapping["reviewed_git_selections"]
        != bindings.reviewed_git_selections
        or mapping["worktree_roster"] != list(bindings.worktree_roster)
    ):
        raise ValueError(_ERROR)


def _require_created_result(
    creation: object,
    observation: object,
    receipt: _ReviewReceiptBinding,
    bindings: _ProfileBindings,
) -> None:
    if type(creation) is not MigrationEvidenceCreationResult:
        raise ValueError(_ERROR)
    result = creation.result
    counts = result.counts
    observed_counts = observation.counts
    if (
        result.status is not MigrationEvidenceStatus.CREATED
        or counts.packages != 1
        or counts.verified != 0
        or counts.rejected != 0
        or (counts.files, counts.refs, counts.worktrees)
        != (
            observed_counts.files,
            observed_counts.refs,
            observed_counts.worktrees,
        )
        or observation.review_fingerprint
        != receipt.review_fingerprint
        or creation.review_fingerprint
        != receipt.review_fingerprint
        or creation.source_snapshot_fingerprint
        != bindings.source_snapshot_fingerprint
        or creation.package_sha256 != observation.package_sha256
        or creation.manifest_sha256 != observation.manifest_sha256
        or creation.package_identity_fingerprint
        != observation.package_identity_fingerprint
    ):
        raise ValueError(_ERROR)


def _created_receipt(
    *,
    receipt: _ReviewReceiptBinding,
    observation: object,
    authorization: EvidencePublicationAuthorizationV1,
) -> MigrationEvidenceCreatedReceiptV1:
    common = {
        "operation_fingerprint": receipt.operation_fingerprint,
        "profile_fingerprint": receipt.profile_fingerprint,
        "master_fingerprint": receipt.master_fingerprint,
        "review_fingerprint": receipt.review_fingerprint,
        "selection_fingerprint": receipt.selection_fingerprint,
        "git_fingerprint": receipt.git_fingerprint,
        "host_fingerprint": receipt.host_fingerprint,
        "review_counts_fingerprint": receipt.counts_fingerprint,
        "package_sha256": observation.package_sha256,
        "manifest_sha256": observation.manifest_sha256,
        "package_identity_fingerprint": (
            observation.package_identity_fingerprint
        ),
        "package_counts_fingerprint": observation.counts_fingerprint,
    }
    package_counts = MigrationEvidencePackageCountsV1(
        files=observation.counts.files,
        refs=observation.counts.refs,
        worktrees=observation.counts.worktrees,
    )
    return _mint_created_receipt(
        common=common,
        review_receipt_fingerprint=receipt.receipt_fingerprint,
        package_counts=package_counts,
        authorization_fingerprint=authorization.authorization_fingerprint,
    )


def _master_fingerprint(profile: CutoverProfileV1) -> str:
    return fingerprint(
        "migration-evidence-governing-master-v1",
        profile.governing_master_commit,
    )
