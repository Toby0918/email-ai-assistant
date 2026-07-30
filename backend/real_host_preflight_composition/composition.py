"""Fixed read-only composition."""

from __future__ import annotations

from .contracts_bridge import (
    CompositionBindingV1,
    CompositionContractError,
    CompositionStage,
    CompositionStageReceiptV1,
    ProjectContainerReceiptChainV1,
    UNBOUND_FINGERPRINT,
)
from .roles import RealHostPreflightRolesV1


_ERROR = "REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED"


class RealHostPreflightComposition:
    """Six fixed read-only roles with no host selector surface."""

    __slots__ = (
        "_binding",
        "_roles",
        "_observed_at",
        "_receipts",
        "_recovery_inspected",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "RealHostPreflightComposition has no executable backend constructor"
        )

    def run_current_topology(self) -> CompositionStageReceiptV1:
        return self._append(
            self._roles.current_topology,
            CompositionStage.CURRENT_TOPOLOGY,
        )

    def collect_host_baseline(self) -> CompositionStageReceiptV1:
        return self._append(
            self._roles.host_baseline,
            CompositionStage.HOST_BASELINE,
        )

    def review_evidence(self) -> CompositionStageReceiptV1:
        return self._append(
            self._roles.evidence_review,
            CompositionStage.EVIDENCE_REVIEW,
        )

    def verify_evidence(
        self,
        publication_receipt: CompositionStageReceiptV1,
    ) -> CompositionStageReceiptV1:
        try:
            review = self._receipts[-1]
            _require_receipt(
                self._binding,
                publication_receipt,
                CompositionStage.EVIDENCE_PUBLICATION,
                review,
            )
            self._receipts = (*self._receipts, publication_receipt)
            return self._append(
                self._roles.evidence_verification,
                CompositionStage.EVIDENCE_VERIFICATION,
            )
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def prove_final_audit_readiness(self) -> CompositionStageReceiptV1:
        return self._append(
            self._roles.final_audit_readiness,
            CompositionStage.FINAL_AUDIT_READINESS,
        )

    def inspect_recovery(
        self,
        prior_receipt: CompositionStageReceiptV1,
    ) -> CompositionStageReceiptV1:
        if self._recovery_inspected:
            raise CompositionContractError(_ERROR)
        try:
            if prior_receipt.stage not in {
                CompositionStage.ACTIVATION,
                CompositionStage.FINAL_AUDIT,
            }:
                raise ValueError
            receipt = self._roles.recovery_inspection(prior_receipt)
            _require_receipt(
                self._binding,
                receipt,
                CompositionStage.RECOVERY_INSPECTION,
                prior_receipt,
            )
            self._recovery_inspected = True
            return receipt
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def receipt_chain(self) -> ProjectContainerReceiptChainV1:
        try:
            return ProjectContainerReceiptChainV1.create(
                receipts=self._receipts,
                observed_at_epoch=self._observed_at,
            )
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def _append(self, role, stage) -> CompositionStageReceiptV1:
        prior = self._receipts[-1] if self._receipts else None
        _require_predecessor(stage, prior)
        try:
            receipt = role(prior)
            _require_receipt(
                self._binding,
                receipt,
                stage,
                prior,
            )
            self._receipts = (*self._receipts, receipt)
            return receipt
        except Exception:
            raise CompositionContractError(_ERROR) from None


def _require_receipt(binding, receipt, stage, prior) -> None:
    expected_binding = (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )
    expected_prior = (
        prior.receipt_fingerprint
        if type(prior) is CompositionStageReceiptV1
        else UNBOUND_FINGERPRINT
    )
    expected_prior_head = (
        prior.journal_head_fingerprint
        if type(prior) is CompositionStageReceiptV1
        else UNBOUND_FINGERPRINT
    )
    if (
        type(receipt) is not CompositionStageReceiptV1
        or receipt.stage is not stage
        or receipt.prior_receipt_fingerprint != expected_prior
        or receipt.prior_journal_head_fingerprint != expected_prior_head
        or receipt.binding_tuple() != expected_binding
        or (
            type(prior) is CompositionStageReceiptV1
            and prior.binding_tuple() != expected_binding
        )
    ):
        raise ValueError


def _require_predecessor(stage, prior) -> None:
    previous = {
        CompositionStage.CURRENT_TOPOLOGY: None,
        CompositionStage.HOST_BASELINE: CompositionStage.CURRENT_TOPOLOGY,
        CompositionStage.EVIDENCE_REVIEW: CompositionStage.HOST_BASELINE,
        CompositionStage.EVIDENCE_VERIFICATION: (
            CompositionStage.EVIDENCE_PUBLICATION
        ),
        CompositionStage.FINAL_AUDIT_READINESS: (
            CompositionStage.EVIDENCE_VERIFICATION
        ),
    }[stage]
    actual = prior.stage if prior else None
    if actual is not previous:
        raise CompositionContractError(_ERROR)
