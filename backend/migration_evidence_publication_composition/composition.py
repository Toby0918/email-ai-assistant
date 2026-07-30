"""Fixed create-only evidence composition."""

from __future__ import annotations

from .contracts_bridge import (
    CompositionBindingV1,
    CompositionContractError,
    CompositionStage,
    CompositionStageReceiptV1,
)
from .roles import MigrationEvidencePublicationRolesV1


_ERROR = "MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED"


class MigrationEvidencePublicationComposition:
    """One confirmed-review create-only role."""

    __slots__ = ("_binding", "_roles", "_confirmed", "_published")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "MigrationEvidencePublicationComposition has no executable "
            "backend constructor"
        )

    def publish(
        self,
        review_receipt: CompositionStageReceiptV1,
    ) -> CompositionStageReceiptV1:
        if self._published:
            raise CompositionContractError(_ERROR)
        try:
            _require_review(self._binding, review_receipt, self._confirmed)
            receipt = self._roles.publish_confirmed_review(review_receipt)
            _require_publication(self._binding, review_receipt, receipt)
            self._published = True
            return receipt
        except Exception:
            raise CompositionContractError(_ERROR) from None


def _require_review(binding, receipt, confirmed) -> None:
    if (
        type(receipt) is not CompositionStageReceiptV1
        or receipt.stage is not CompositionStage.EVIDENCE_REVIEW
        or receipt.observation_fingerprint != confirmed
        or receipt.binding_tuple() != _binding_tuple(binding)
    ):
        raise ValueError


def _require_publication(binding, review, receipt) -> None:
    if (
        type(receipt) is not CompositionStageReceiptV1
        or receipt.stage is not CompositionStage.EVIDENCE_PUBLICATION
        or receipt.prior_receipt_fingerprint != review.receipt_fingerprint
        or receipt.binding_tuple() != _binding_tuple(binding)
    ):
        raise ValueError


def _binding_tuple(binding):
    return (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )
