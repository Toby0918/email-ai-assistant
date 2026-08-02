"""Only terminal evidence receipt for one complete frozen final master."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import canonical_json, fingerprint, strict_json_object
from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError
from .evidence import R2ClosureGapProofV1, R2ClosureGateReceiptV1
from .vocabulary import (
    FinalMasterClosureStatus,
    closure_gate_registry,
    closure_gap_registry,
)


_TYPE = "R2FinalMasterClosureReceiptV1"
_ZERO_FIELDS = (
    "open_findings",
    "surface_omissions",
    "required_skips",
    "unclassified_skips",
    "leakage_findings",
    "cleanup_operations",
    "provider_attempts",
    "real_host_operations",
    "issue39_code_changes_required",
)
_BODY_FIELDS = (
    "receipt_type",
    "terminal_status",
    "binding_fingerprint",
    "final_commit_oid",
    "final_tree_oid",
    "closure_map_fingerprint",
    "source_package_fingerprint",
    "runbook_fingerprint",
    "workflow_fingerprint",
    "gap_proofs",
    "gate_receipts",
    "gap_proof_count",
    "gate_receipt_count",
    *_ZERO_FIELDS,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2FinalMasterClosureReceiptV1:
    receipt_type: str = field(repr=False)
    terminal_status: FinalMasterClosureStatus
    binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    closure_map_fingerprint: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    gap_proofs: tuple[tuple[str, str], ...] = field(repr=False)
    gate_receipts: tuple[tuple[str, str], ...] = field(repr=False)
    gap_proof_count: int
    gate_receipt_count: int
    open_findings: int
    surface_omissions: int
    required_skips: int
    unclassified_skips: int
    leakage_findings: int
    cleanup_operations: int
    provider_attempts: int
    real_host_operations: int
    issue39_code_changes_required: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2FinalMasterClosureReceiptV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        binding: object,
        gap_proofs: object,
        gate_receipts: object,
    ) -> R2FinalMasterClosureReceiptV1:
        body = _terminal_body(binding, gap_proofs, gate_receipts)
        return _construct(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        binding: object,
        gap_proofs: object,
        gate_receipts: object,
    ) -> R2FinalMasterClosureReceiptV1:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise FinalMasterClosureError()
            if set(source) != {*_BODY_FIELDS, "receipt_fingerprint"}:
                raise FinalMasterClosureError()
            body = _terminal_body(binding, gap_proofs, gate_receipts)
            if any(source[name] != body[name] for name in _BODY_FIELDS):
                raise FinalMasterClosureError()
            expected = fingerprint("r2-final-master-closure-receipt-v1", body)
            if source["receipt_fingerprint"] != expected:
                raise FinalMasterClosureError()
            return _construct(body)
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    def to_mapping(self) -> dict[str, object]:
        values = {name: getattr(self, name) for name in _BODY_FIELDS}
        values["terminal_status"] = self.terminal_status.value
        values["gap_proofs"] = [
            {"gap": gap, "proof_fingerprint": proof}
            for gap, proof in self.gap_proofs
        ]
        values["gate_receipts"] = [
            {"gate": gate, "receipt_fingerprint": receipt}
            for gate, receipt in self.gate_receipts
        ]
        values["receipt_fingerprint"] = self.receipt_fingerprint
        return values

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _terminal_body(binding, gap_proofs, gate_receipts) -> dict[str, object]:
    _validate_inputs(binding, gap_proofs, gate_receipts)
    gap_values = [
        {
            "gap": proof.gap.value,
            "proof_fingerprint": proof.proof_fingerprint,
        }
        for proof in gap_proofs
    ]
    gate_values = [
        {
            "gate": receipt.gate.value,
            "receipt_fingerprint": receipt.receipt_fingerprint,
        }
        for receipt in gate_receipts
    ]
    return {
        "receipt_type": _TYPE,
        "terminal_status": (
            FinalMasterClosureStatus.ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW.value
        ),
        "binding_fingerprint": binding.binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "closure_map_fingerprint": binding.closure_map_fingerprint,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "workflow_fingerprint": binding.workflow_fingerprint,
        "gap_proofs": gap_values,
        "gate_receipts": gate_values,
        "gap_proof_count": len(gap_values),
        "gate_receipt_count": len(gate_values),
        **{name: 0 for name in _ZERO_FIELDS},
    }


def _validate_inputs(binding, gap_proofs, gate_receipts) -> None:
    expected_gaps = tuple(item.gap for item in closure_gap_registry())
    expected_gates = closure_gate_registry()
    if (
        type(binding) is not FinalMasterBindingV1
        or type(gap_proofs) is not tuple
        or type(gate_receipts) is not tuple
        or tuple(
            proof.gap
            for proof in gap_proofs
            if type(proof) is R2ClosureGapProofV1
        )
        != expected_gaps
        or len(gap_proofs) != len(expected_gaps)
        or tuple(
            receipt.gate
            for receipt in gate_receipts
            if type(receipt) is R2ClosureGateReceiptV1
        )
        != expected_gates
        or len(gate_receipts) != len(expected_gates)
    ):
        raise FinalMasterClosureError()
    evidence = (*gap_proofs, *gate_receipts)
    if any(item.binding_fingerprint != binding.binding_fingerprint for item in evidence):
        raise FinalMasterClosureError()


def _construct(body: dict[str, object]) -> R2FinalMasterClosureReceiptV1:
    value = object.__new__(R2FinalMasterClosureReceiptV1)
    for name in _BODY_FIELDS:
        item = body[name]
        if name == "terminal_status":
            item = FinalMasterClosureStatus(item)
        elif name == "gap_proofs":
            item = tuple(
                (entry["gap"], entry["proof_fingerprint"])
                for entry in item
            )
        elif name == "gate_receipts":
            item = tuple(
                (entry["gate"], entry["receipt_fingerprint"])
                for entry in item
            )
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "receipt_fingerprint",
        fingerprint("r2-final-master-closure-receipt-v1", body),
    )
    return value
