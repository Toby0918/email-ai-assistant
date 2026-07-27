"""Profile-bound review composition for Issue #54."""

from __future__ import annotations

from .contracts_bridge import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    RealPreflightAuthorizationV1,
    validate_real_host_authorization,
)
from .review_bridge import (
    prepare_migration_evidence_review as _prepare_review,
)

from .canonical import fingerprint
from .errors import MigrationEvidencePublicationError
from .profile_binding import _profile_bindings_for_review
from .receipts import (
    MigrationEvidenceReviewReceiptV1,
    _mint_review_receipt,
)
from .selection import (
    ProfileBoundEvidenceSelectionV1,
    _begin_selection_review,
    _cancel_selection_review,
    _complete_selection_review,
)


def review_profile_bound_migration_evidence(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    selection: ProfileBoundEvidenceSelectionV1,
) -> MigrationEvidenceReviewReceiptV1:
    """Recompute the complete review through one opaque bound selection."""

    try:
        return _compose_review(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation_fingerprint,
            observed_at_epoch=observed_at_epoch,
            selection=selection,
        )
    except Exception:
        raise MigrationEvidencePublicationError() from None


def _compose_review(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    selection: ProfileBoundEvidenceSelectionV1,
) -> MigrationEvidenceReviewReceiptV1:
    profile = CutoverProfileV1.from_mapping(profile.to_mapping())
    _require_authorization(
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    inputs = _begin_selection_review(
        selection,
        profile=profile,
        operation_fingerprint=operation_fingerprint,
    )
    try:
        return _finish_review(
            profile=profile,
            selection=selection,
            inputs=inputs,
            operation_fingerprint=operation_fingerprint,
            observed_at_epoch=observed_at_epoch,
        )
    except Exception:
        _cancel_selection_review(selection)
        raise


def _finish_review(
    *,
    profile: CutoverProfileV1,
    selection: ProfileBoundEvidenceSelectionV1,
    inputs: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> MigrationEvidenceReviewReceiptV1:
    review, bindings = _discover_review(
        profile, inputs, operation_fingerprint, observed_at_epoch
    )
    _require_profile_bindings(profile, bindings)
    receipt = _mint_review_receipt(
        operation_fingerprint=operation_fingerprint,
        profile_fingerprint=profile.profile_fingerprint,
        master_fingerprint=fingerprint(
            "migration-evidence-governing-master-v1",
            profile.governing_master_commit,
        ),
        review_fingerprint=review.review_fingerprint,
        bindings=bindings,
    )
    _complete_selection_review(
        selection,
        review=review,
        bindings=bindings,
        receipt_fingerprint=receipt.receipt_fingerprint,
    )
    return receipt


def _discover_review(
    profile: CutoverProfileV1,
    inputs: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> tuple[object, object]:
    baseline = inputs.baseline_collector.collect(
        profile=profile,
        authorization=inputs.baseline_authorization,
        operation_fingerprint=operation_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    review = _prepare_review(
        repository_root=inputs.repository_root,
        target=inputs.target,
        approved_dirty_paths=inputs.approved_dirty_paths,
        reviewed_refs=inputs.reviewed_refs,
        approved_worktrees=inputs.approved_worktrees,
        host_baseline=baseline,
    )
    bindings = _profile_bindings_for_review(
        review,
        inputs.approved_worktrees,
    )
    return review, bindings


def _require_authorization(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
) -> None:
    if type(authorization) is not RealPreflightAuthorizationV1:
        raise ValueError("MIGRATION_EVIDENCE_REVIEW_REJECTED")
    validation = validate_real_host_authorization(
        authorization,
        profile=profile,
        expected_operation="real_preflight",
        expected_operation_fingerprint=operation_fingerprint,
        expected_phase="evidence_review",
        expected_operator_fingerprint=profile.operator_fingerprint,
        observed_at_epoch=observed_at_epoch,
    )
    if validation.status is not AuthorizationValidationStatus.AUTHORIZED:
        raise ValueError("MIGRATION_EVIDENCE_REVIEW_REJECTED")


def _require_profile_bindings(
    profile: CutoverProfileV1,
    bindings: object,
) -> None:
    mapping = profile.to_mapping()
    if (
        mapping["evidence_roles"] != bindings.evidence_roles
        or mapping["reviewed_git_selections"]
        != bindings.reviewed_git_selections
        or mapping["worktree_roster"]
        != list(bindings.worktree_roster)
    ):
        raise ValueError("MIGRATION_EVIDENCE_REVIEW_REJECTED")
