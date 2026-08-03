"""Fixed no-argument terminal verifier and human-review handoff."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._canonical import canonical_json, fingerprint
from .errors import FinalMasterClosureError
from .evidence import R2ClosureGapProofV1, R2ClosureGateReceiptV1
from .frozen_master import R2FrozenRemoteMasterV1
from .gap_completion import gap_completion_evidence_fingerprint_v1
from .global_gates import R2GlobalGateCoordinatorV1
from .reviewed_production import R2ReviewedProductionBindingReceiptV1
from .terminal import R2FinalMasterClosureReceiptV1
from .vocabulary import (
    ClosureGate,
    FinalMasterClosureStatus,
    closure_gap_registry,
)


class FinalReviewStatusV1(str, Enum):
    AWAITING_SINGLE_HUMAN_FINAL_REVIEW = "AWAITING_SINGLE_HUMAN_FINAL_REVIEW"
    BLOCKED_FROZEN_MASTER = "BLOCKED_FROZEN_MASTER"
    BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING = (
        "BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING"
    )
    BLOCKED_MISSING_EXTERNAL_GATE_EVIDENCE = "BLOCKED_MISSING_EXTERNAL_GATE_EVIDENCE"


@dataclass(frozen=True, slots=True, repr=False)
class R2FinalMasterClosurePendingV1:
    status: FinalReviewStatusV1
    missing_reviewed_production_binding_count: int
    missing_external_gate_evidence_count: int
    invalid_external_gate_evidence_count: int
    human_intervention_required: int
    eligibility_receipt_count: int
    approval_count: int
    execution_authority_count: int

    def to_mapping(self):
        return {
            name: (value.value if isinstance(value, Enum) else value)
            for name in self.__dataclass_fields__
            for value in (getattr(self, name),)
        }


_ZERO_FIELDS = (
    "open_finding_count", "contract_changing_finding_count",
    "decision_contradiction_finding_count", "security_incident_finding_count",
    "surface_completeness_defect_count", "evidence_defect_count",
    "required_skip_count", "unclassified_skip_count", "leakage_finding_count",
    "cleanup_operation_count", "provider_attempt_count", "real_host_operation_count",
    "private_data_access_count", "issue39_code_change_count", "human_review_completed",
    "approval_count", "execution_authority_count",
)

@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2FinalMasterReviewPackageV1:
    package_type: str
    status: FinalReviewStatusV1
    terminal_status: FinalMasterClosureStatus
    binding_fingerprint: str = field(repr=False)
    production_binding_receipt: R2ReviewedProductionBindingReceiptV1 = field(
        repr=False
    )
    production_binding_fingerprint: str = field(repr=False)
    operator_role_registry_fingerprint: str = field(repr=False)
    command_domain_registry_fingerprint: str = field(repr=False)
    public_key_registry_fingerprint: str = field(repr=False)
    production_role_registry_fingerprint: str = field(repr=False)
    frozen_master_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    closure_map_fingerprint: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    coordinator_receipt_fingerprint: str = field(repr=False)
    gate_receipt_set_fingerprint: str = field(repr=False)
    gap_proof_set_fingerprint: str = field(repr=False)
    terminal_receipt_fingerprint: str = field(repr=False)
    gap_proofs: tuple[R2ClosureGapProofV1, ...] = field(repr=False)
    gate_receipts: tuple[R2ClosureGateReceiptV1, ...] = field(repr=False)
    gap_proof_count: int
    gate_receipt_count: int
    human_review_required: int
    open_finding_count: int
    contract_changing_finding_count: int
    decision_contradiction_finding_count: int
    security_incident_finding_count: int
    surface_completeness_defect_count: int
    evidence_defect_count: int
    required_skip_count: int
    unclassified_skip_count: int
    leakage_finding_count: int
    cleanup_operation_count: int
    provider_attempt_count: int
    real_host_operation_count: int
    private_data_access_count: int
    issue39_code_change_count: int
    human_review_completed: int
    approval_count: int
    execution_authority_count: int
    review_package_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2FinalMasterReviewPackageV1 is created only by fixed verification")

    def to_mapping(self):
        result = _scalar_mapping(self)
        result["production_binding_receipt"] = (
            self.production_binding_receipt.to_mapping()
        )
        result["gap_proofs"] = _gap_mapping(self.gap_proofs)
        result["gate_receipts"] = _gate_mapping(self.gate_receipts)
        return result

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def verify_final_master_closure_v1():
    """Pure fail-closed seam; the fixed Git adapter lives in the no-arg script."""
    return _pending(
        FinalReviewStatusV1.BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING,
        1,
        0,
        0,
    )


def _assemble_review_package(frozen, production_binding_receipt, evidence):
    production_evidence = next(
        (item for item in evidence if item.gate is ClosureGate.PRODUCTION_COMPOSITION),
        None,
    )
    if (
        type(production_binding_receipt)
        is not R2ReviewedProductionBindingReceiptV1
        or production_binding_receipt.final_master_binding_fingerprint
        != frozen.binding.binding_fingerprint
        or production_evidence is None
        or production_evidence.evidence_fingerprint
        != production_binding_receipt.production_composition_evidence_fingerprint
    ):
        raise FinalMasterClosureError()
    coordinator = R2GlobalGateCoordinatorV1.create(
        binding=frozen.binding, evidence=evidence
    )
    gaps = tuple(
        R2ClosureGapProofV1.create(
            binding=frozen.binding,
            gap=registration.gap,
            evidence_fingerprint=gap_completion_evidence_fingerprint_v1(
                registration.gap, coordinator
            ),
        )
        for registration in closure_gap_registry()
    )
    terminal = R2FinalMasterClosureReceiptV1.create(
        binding=frozen.binding,
        gap_proofs=gaps,
        gate_receipts=coordinator.gate_receipts,
    )
    body = _body(
        frozen, production_binding_receipt, gaps, coordinator, terminal
    )
    return _allocate(
        body, production_binding_receipt, gaps, coordinator.gate_receipts
    )


def _body(frozen, production_binding_receipt, gaps, coordinator, terminal):
    binding = frozen.binding
    return {
        "package_type": "R2FinalMasterReviewPackageV1",
        "status": FinalReviewStatusV1.AWAITING_SINGLE_HUMAN_FINAL_REVIEW.value,
        "terminal_status": terminal.terminal_status.value,
        "binding_fingerprint": binding.binding_fingerprint,
        "production_binding_fingerprint": (
            production_binding_receipt.production_binding_fingerprint
        ),
        "operator_role_registry_fingerprint": (
            production_binding_receipt.operator_role_registry_fingerprint
        ),
        "command_domain_registry_fingerprint": (
            production_binding_receipt.command_domain_registry_fingerprint
        ),
        "public_key_registry_fingerprint": (
            production_binding_receipt.public_key_registry_fingerprint
        ),
        "production_role_registry_fingerprint": (
            production_binding_receipt.production_role_registry_fingerprint
        ),
        "frozen_master_fingerprint": frozen.observation_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "closure_map_fingerprint": binding.closure_map_fingerprint,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "workflow_fingerprint": binding.workflow_fingerprint,
        "coordinator_receipt_fingerprint": coordinator.coordinator_receipt_fingerprint,
        "gate_receipt_set_fingerprint": coordinator.gate_receipt_set_fingerprint,
        "gap_proof_set_fingerprint": fingerprint(
            "r2-final-gap-proof-set-v1", [item.proof_fingerprint for item in gaps]
        ),
        "terminal_receipt_fingerprint": terminal.receipt_fingerprint,
        "gap_proof_count": 8,
        "gate_receipt_count": 14,
        "human_review_required": 1,
        **{name: 0 for name in _ZERO_FIELDS},
    }


def _pending(status, missing_binding, missing, invalid):
    return R2FinalMasterClosurePendingV1(
        status, missing_binding, missing, invalid, 1, 0, 0, 0
    )


def _allocate(body, production_binding_receipt, gaps, receipts):
    value = object.__new__(R2FinalMasterReviewPackageV1)
    for name, item in body.items():
        enum = FinalReviewStatusV1 if name == "status" else (
            FinalMasterClosureStatus if name == "terminal_status" else None
        )
        object.__setattr__(value, name, enum(item) if enum else item)
    object.__setattr__(
        value, "production_binding_receipt", production_binding_receipt
    )
    object.__setattr__(value, "gap_proofs", gaps)
    object.__setattr__(value, "gate_receipts", receipts)
    public = {**body,
              "production_binding_receipt": production_binding_receipt.to_mapping(),
              "gap_proofs": _gap_mapping(gaps),
              "gate_receipts": _gate_mapping(receipts)}
    object.__setattr__(value, "review_package_fingerprint",
                       fingerprint("r2-final-master-review-package-v1", public))
    return value


def _scalar_mapping(value):
    result = {}
    for name in value.__dataclass_fields__:
        if name in {"production_binding_receipt", "gap_proofs", "gate_receipts"}:
            continue
        item = getattr(value, name)
        result[name] = item.value if isinstance(item, Enum) else item
    return result


def _gap_mapping(gaps):
    return [{"gap": item.gap.value, "proof_fingerprint": item.proof_fingerprint}
            for item in gaps]


def _gate_mapping(receipts):
    return [{"gate": item.gate.value, "receipt_fingerprint": item.receipt_fingerprint}
            for item in receipts]
