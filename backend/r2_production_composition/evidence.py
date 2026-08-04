"""State-bearing bridge to reviewed create-only evidence publication."""

from dataclasses import dataclass, field

from backend.cutover_composition_contracts import (
    CompositionStage,
    CompositionStageReceiptV1,
)
from backend.migration_evidence_publication_composition import (
    MigrationEvidencePublicationComposition,
)
from backend.r2_production_binding import (
    ProductionBindingError,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)

from .adapter_binding import (
    require_adapter_context_v1,
    require_composition_binding_v1,
)


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceAdapterOutcomeV1:
    reviewed_evidence_fingerprint: str = field(repr=False)
    evidence_identity_fingerprint: str = field(repr=False)
    package_fingerprint: str = field(repr=False)
    manifest_fingerprint: str = field(repr=False)
    provider_attempts: int
    created: int


class EvidenceProductionAdapterV1:
    """One stateful slot for the evidence-publication command."""

    __slots__ = ("_binding", "_composition", "_review_receipt")

    def __init__(self, *args, **kwargs):
        raise TypeError("EvidenceProductionAdapterV1 requires create()")

    @classmethod
    def create(cls, *, binding, composition, review_receipt):
        try:
            if (
                type(composition) is not MigrationEvidencePublicationComposition
                or type(review_receipt) is not CompositionStageReceiptV1
                or review_receipt.stage is not CompositionStage.EVIDENCE_REVIEW
            ):
                raise ProductionBindingError()
            require_composition_binding_v1(binding, composition._binding)
            if review_receipt.binding_tuple() != _binding_tuple(composition._binding):
                raise ProductionBindingError()
            value = object.__new__(cls)
            value._binding = binding
            value._composition = composition
            value._review_receipt = review_receipt
            return value
        except ProductionBindingError:
            raise
        except Exception:
            raise ProductionBindingError() from None

    def invoke(self, *, binding, claim):
        command = ProductionCommandV2.EVIDENCE_PUBLICATION
        require_adapter_context_v1(
            binding,
            claim,
            self._composition._binding,
            {command},
        )
        review = self._review_receipt
        if (
            binding is not self._binding
            or claim.action_fingerprint
            != production_action_fingerprint_v2(
                binding,
                command,
                subject_fingerprint=review.observation_fingerprint,
            )
        ):
            raise ProductionBindingError()
        publication = self._composition.publish(review)
        if (
            type(publication) is not CompositionStageReceiptV1
            or publication.stage is not CompositionStage.EVIDENCE_PUBLICATION
            or publication.prior_receipt_fingerprint
            != review.receipt_fingerprint
            or publication.binding_tuple()
            != _binding_tuple(self._composition._binding)
            or publication.accepted != 1
            or publication.rejected != 0
            or publication.provider_attempts != 0
        ):
            raise ProductionBindingError()
        return EvidenceAdapterOutcomeV1(
            review.observation_fingerprint,
            publication.receipt_fingerprint,
            publication.observation_fingerprint,
            review.receipt_fingerprint,
            publication.provider_attempts,
            1,
        )


def _binding_tuple(binding):
    return (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )
