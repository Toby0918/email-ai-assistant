"""Nominal content-free completion proof for one registered closure gap."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError
from .vocabulary import ClosureGate, ClosureGap


_GAP_TYPE = "R2ClosureGapProofV1"
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
_GAP_BODY_FIELDS = (
    "proof_type",
    "binding_fingerprint",
    "gap",
    "evidence_fingerprint",
    "completed",
    *_ZERO_FIELDS,
)
_GATE_TYPE = "R2ClosureGateReceiptV1"
_GATE_BODY_FIELDS = (
    "receipt_type",
    "binding_fingerprint",
    "gate",
    "evidence_fingerprint",
    "producer_fingerprint",
    "verified",
    "self_certified",
    "required_skips",
    "unclassified_skips",
    "leakage_findings",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ClosureGapProofV1:
    proof_type: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    gap: ClosureGap = field(repr=False)
    evidence_fingerprint: str = field(repr=False)
    completed: int
    open_findings: int
    surface_omissions: int
    required_skips: int
    unclassified_skips: int
    leakage_findings: int
    cleanup_operations: int
    provider_attempts: int
    real_host_operations: int
    issue39_code_changes_required: int
    proof_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ClosureGapProofV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        binding: object,
        gap: object,
        evidence_fingerprint: object,
    ) -> R2ClosureGapProofV1:
        body = _gap_body(binding, gap, evidence_fingerprint)
        return _construct_gap(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        binding: object,
    ) -> R2ClosureGapProofV1:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise FinalMasterClosureError()
            if set(source) != {*_GAP_BODY_FIELDS, "proof_fingerprint"}:
                raise FinalMasterClosureError()
            gap = ClosureGap(source["gap"])
            body = _gap_body(binding, gap, source["evidence_fingerprint"])
            if any(source[name] != body[name] for name in _GAP_BODY_FIELDS):
                raise FinalMasterClosureError()
            expected = fingerprint("r2-closure-gap-proof-v1", body)
            if source["proof_fingerprint"] != expected:
                raise FinalMasterClosureError()
            return _construct_gap(body)
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    def to_mapping(self) -> dict[str, object]:
        return {
            **{
                name: (
                    self.gap.value if name == "gap" else getattr(self, name)
                )
                for name in _GAP_BODY_FIELDS
            },
            "proof_fingerprint": self.proof_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ClosureGateReceiptV1:
    receipt_type: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    gate: ClosureGate = field(repr=False)
    evidence_fingerprint: str = field(repr=False)
    producer_fingerprint: str = field(repr=False)
    verified: int
    self_certified: int
    required_skips: int
    unclassified_skips: int
    leakage_findings: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ClosureGateReceiptV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        binding: object,
        gate: object,
        evidence_fingerprint: object,
        producer_fingerprint: object,
    ) -> R2ClosureGateReceiptV1:
        body = _gate_body(
            binding,
            gate,
            evidence_fingerprint,
            producer_fingerprint,
        )
        return _construct_gate(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        binding: object,
    ) -> R2ClosureGateReceiptV1:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise FinalMasterClosureError()
            if set(source) != {*_GATE_BODY_FIELDS, "receipt_fingerprint"}:
                raise FinalMasterClosureError()
            gate = ClosureGate(source["gate"])
            body = _gate_body(
                binding,
                gate,
                source["evidence_fingerprint"],
                source["producer_fingerprint"],
            )
            if any(source[name] != body[name] for name in _GATE_BODY_FIELDS):
                raise FinalMasterClosureError()
            expected = fingerprint("r2-closure-gate-receipt-v1", body)
            if source["receipt_fingerprint"] != expected:
                raise FinalMasterClosureError()
            return _construct_gate(body)
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    def to_mapping(self) -> dict[str, object]:
        return {
            **{
                name: (
                    self.gate.value if name == "gate" else getattr(self, name)
                )
                for name in _GATE_BODY_FIELDS
            },
            "receipt_fingerprint": self.receipt_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _gap_body(binding, gap, evidence_fingerprint) -> dict[str, object]:
    if (
        type(binding) is not FinalMasterBindingV1
        or type(gap) is not ClosureGap
        or not is_fingerprint(evidence_fingerprint)
    ):
        raise FinalMasterClosureError()
    return {
        "proof_type": _GAP_TYPE,
        "binding_fingerprint": binding.binding_fingerprint,
        "gap": gap.value,
        "evidence_fingerprint": evidence_fingerprint,
        "completed": 1,
        **{name: 0 for name in _ZERO_FIELDS},
    }


def _gate_body(
    binding,
    gate,
    evidence_fingerprint,
    producer_fingerprint,
) -> dict[str, object]:
    if (
        type(binding) is not FinalMasterBindingV1
        or type(gate) is not ClosureGate
        or not is_fingerprint(evidence_fingerprint)
        or not is_fingerprint(producer_fingerprint)
    ):
        raise FinalMasterClosureError()
    return {
        "receipt_type": _GATE_TYPE,
        "binding_fingerprint": binding.binding_fingerprint,
        "gate": gate.value,
        "evidence_fingerprint": evidence_fingerprint,
        "producer_fingerprint": producer_fingerprint,
        "verified": 1,
        "self_certified": 0,
        "required_skips": 0,
        "unclassified_skips": 0,
        "leakage_findings": 0,
    }


def _construct_gap(body: dict[str, object]) -> R2ClosureGapProofV1:
    value = object.__new__(R2ClosureGapProofV1)
    for name in _GAP_BODY_FIELDS:
        item = ClosureGap(body[name]) if name == "gap" else body[name]
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "proof_fingerprint",
        fingerprint("r2-closure-gap-proof-v1", body),
    )
    return value


def _construct_gate(body: dict[str, object]) -> R2ClosureGateReceiptV1:
    value = object.__new__(R2ClosureGateReceiptV1)
    for name in _GATE_BODY_FIELDS:
        item = ClosureGate(body[name]) if name == "gate" else body[name]
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "receipt_fingerprint",
        fingerprint("r2-closure-gate-receipt-v1", body),
    )
    return value
