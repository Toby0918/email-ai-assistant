"""State-bearing bridge to the reviewed read-only preflight composition."""

from dataclasses import dataclass, field

from backend.cutover_composition_contracts import (
    CompositionStage,
    CompositionStageReceiptV1,
)
from backend.r2_production_binding import (
    ProductionBindingError,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)
from backend.real_host_preflight_composition import RealHostPreflightComposition

from .adapter_binding import (
    require_adapter_context_v1,
    require_composition_binding_v1,
)


_COMMAND_STAGES = {
    ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT: (
        CompositionStage.CURRENT_TOPOLOGY
    ),
    ProductionCommandV2.HOST_BASELINE: CompositionStage.HOST_BASELINE,
    ProductionCommandV2.EVIDENCE_REVIEW: CompositionStage.EVIDENCE_REVIEW,
    ProductionCommandV2.EVIDENCE_VERIFICATION: (
        CompositionStage.EVIDENCE_VERIFICATION
    ),
    ProductionCommandV2.FINAL_AUDIT_READINESS: (
        CompositionStage.FINAL_AUDIT_READINESS
    ),
    ProductionCommandV2.RECOVERY_INSPECTION: (
        CompositionStage.RECOVERY_INSPECTION
    ),
}


@dataclass(frozen=True, slots=True, repr=False)
class PreflightAdapterOutcomeV1:
    command: ProductionCommandV2
    stage: CompositionStage
    receipt_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    provider_attempts: int
    read_operations: int


class PreflightProductionAdapterV1:
    """One stateful slot for all six preflight commands."""

    __slots__ = (
        "_binding",
        "_composition",
        "_evidence_publication_receipt",
        "_recovery_receipt",
    )

    def __init__(self, *args, **kwargs):
        raise TypeError("PreflightProductionAdapterV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        binding,
        composition,
        evidence_publication_receipt,
        recovery_receipt,
    ):
        try:
            if type(composition) is not RealHostPreflightComposition:
                raise ProductionBindingError()
            require_composition_binding_v1(binding, composition._binding)
            for receipt in (evidence_publication_receipt, recovery_receipt):
                if receipt is not None and type(receipt) is not CompositionStageReceiptV1:
                    raise ProductionBindingError()
            value = object.__new__(cls)
            value._binding = binding
            value._composition = composition
            value._evidence_publication_receipt = evidence_publication_receipt
            value._recovery_receipt = recovery_receipt
            return value
        except ProductionBindingError:
            raise
        except Exception:
            raise ProductionBindingError() from None

    def invoke(self, *, binding, claim):
        require_adapter_context_v1(
            binding,
            claim,
            self._composition._binding,
            set(_COMMAND_STAGES),
        )
        if (
            binding is not self._binding
            or claim.action_fingerprint
            != production_action_fingerprint_v2(binding, claim.command)
        ):
            raise ProductionBindingError()
        receipt = self._invoke_composition(claim.command)
        expected_stage = _COMMAND_STAGES[claim.command]
        if (
            type(receipt) is not CompositionStageReceiptV1
            or receipt.stage is not expected_stage
            or receipt.binding_tuple()
            != _composition_binding_tuple(self._composition._binding)
            or receipt.accepted != 1
            or receipt.rejected != 0
            or receipt.provider_attempts != 0
        ):
            raise ProductionBindingError()
        return PreflightAdapterOutcomeV1(
            claim.command,
            expected_stage,
            receipt.receipt_fingerprint,
            receipt.observation_fingerprint,
            receipt.provider_attempts,
            1,
        )

    def _invoke_composition(self, command):
        if command is ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT:
            return self._composition.run_current_topology()
        if command is ProductionCommandV2.HOST_BASELINE:
            return self._composition.collect_host_baseline()
        if command is ProductionCommandV2.EVIDENCE_REVIEW:
            return self._composition.review_evidence()
        if command is ProductionCommandV2.EVIDENCE_VERIFICATION:
            return self._composition.verify_evidence(
                self._evidence_publication_receipt
            )
        if command is ProductionCommandV2.FINAL_AUDIT_READINESS:
            return self._composition.prove_final_audit_readiness()
        return self._composition.inspect_recovery(self._recovery_receipt)


def _composition_binding_tuple(binding):
    return (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )
