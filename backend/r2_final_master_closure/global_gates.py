"""Same-binding fourteen-gate coordinator derived from independent evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError
from .evidence import R2ClosureGateReceiptV1
from .global_gate_evidence import R2GlobalGateEvidenceV1, ZERO_GATE_FIELDS
from .global_gate_registry import GlobalGateStatusV1, ReviewDomainV1, gate_evidence_registry
from .vocabulary import closure_gate_registry


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2GlobalGateCoordinatorV1:
    coordinator_type: str
    status: GlobalGateStatusV1
    binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    coordinator_fingerprint: str = field(repr=False)
    gate_evidence: tuple[R2GlobalGateEvidenceV1, ...] = field(repr=False)
    gate_receipts: tuple[R2ClosureGateReceiptV1, ...] = field(repr=False)
    gate_evidence_count: int
    gate_receipt_count: int
    independent_producer_count: int
    review_domain_count: int
    missing_gate_count: int
    duplicate_gate_count: int
    stale_binding_count: int
    self_certified_count: int
    required_skip_count: int
    unclassified_skip_count: int
    platform_divergence_count: int
    leakage_finding_count: int
    private_data_access_count: int
    real_host_operation_count: int
    provider_attempt_count: int
    issue39_code_change_count: int
    gate_receipt_set_fingerprint: str = field(repr=False)
    coordinator_receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2GlobalGateCoordinatorV1 requires create()")

    @classmethod
    def create(cls, *, binding, evidence):
        try:
            coordinator_fingerprint = _coordinator_fingerprint()
            _require(binding, coordinator_fingerprint, evidence)
            receipts = _derive_receipts(binding, evidence)
            body = _body(binding, coordinator_fingerprint, receipts)
            return _allocate(body, evidence, receipts)
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    @classmethod
    def from_json(cls, payload, **values):
        try:
            source = strict_json_object(payload)
            result = cls.create(**values)
            if payload != canonical_json(source) or source != result.to_mapping():
                raise FinalMasterClosureError()
            return result
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    def to_mapping(self):
        result = _scalar_mapping(self)
        result["gate_evidence"] = _evidence_mapping(self.gate_evidence)
        result["gate_receipts"] = _receipt_mapping(self.gate_receipts)
        return result

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _require(binding, coordinator, evidence):
    if type(binding) is not FinalMasterBindingV1 or not is_fingerprint(coordinator):
        raise FinalMasterClosureError()
    observed = tuple(
        item.gate for item in evidence if type(item) is R2GlobalGateEvidenceV1
    ) if type(evidence) is tuple else ()
    if observed != closure_gate_registry() or len(evidence) != 14:
        raise FinalMasterClosureError()
    if any(item.binding_fingerprint != binding.binding_fingerprint for item in evidence):
        raise FinalMasterClosureError()
    producers = {item.producer_fingerprint for item in evidence}
    records = {item.evidence_record_fingerprint for item in evidence}
    if len(producers) != 14 or len(records) != 14:
        raise FinalMasterClosureError()
    if coordinator in producers or coordinator in records or coordinator == binding.binding_fingerprint:
        raise FinalMasterClosureError()
    if {item.review_domain for item in evidence} != set(ReviewDomainV1):
        raise FinalMasterClosureError()


def _coordinator_fingerprint():
    return fingerprint("r2-fixed-global-gate-coordinator-v1", [
        {
            "gate": item.gate.value,
            "producer": item.producer.value,
            "review_domain": item.review_domain.value,
            "verification_public_key_hex": item.verification_public_key.hex(),
        }
        for item in gate_evidence_registry()
    ])


def _derive_receipts(binding, evidence):
    return tuple(
        R2ClosureGateReceiptV1.create(
            binding=binding,
            gate=item.gate,
            evidence_fingerprint=item.evidence_record_fingerprint,
            producer_fingerprint=item.producer_fingerprint,
        )
        for item in evidence
    )


def _body(binding, coordinator, receipts):
    zeros = {"missing_gate_count": 0, "duplicate_gate_count": 0,
             "stale_binding_count": 0, "self_certified_count": 0,
             **{name: 0 for name in ZERO_GATE_FIELDS}}
    return {
        "coordinator_type": "R2GlobalGateCoordinatorV1",
        "status": GlobalGateStatusV1.GLOBAL_GATES_VERIFIED.value,
        "binding_fingerprint": binding.binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "workflow_fingerprint": binding.workflow_fingerprint,
        "coordinator_fingerprint": coordinator,
        "gate_evidence_count": 14,
        "gate_receipt_count": 14,
        "independent_producer_count": 14,
        "review_domain_count": len(ReviewDomainV1),
        **zeros,
        "gate_receipt_set_fingerprint": fingerprint(
            "r2-global-gate-receipt-set-v1",
            [item.receipt_fingerprint for item in receipts],
        ),
    }


def _allocate(body, evidence, receipts):
    value = object.__new__(R2GlobalGateCoordinatorV1)
    for name, item in body.items():
        object.__setattr__(value, name, GlobalGateStatusV1(item) if name == "status" else item)
    object.__setattr__(value, "gate_evidence", evidence)
    object.__setattr__(value, "gate_receipts", receipts)
    public = {**body, "gate_evidence": _evidence_mapping(evidence),
              "gate_receipts": _receipt_mapping(receipts)}
    object.__setattr__(value, "coordinator_receipt_fingerprint",
                       fingerprint("r2-global-gate-coordinator-v1", public))
    return value


def _scalar_mapping(value):
    result = {}
    for name in value.__dataclass_fields__:
        if name in {"gate_evidence", "gate_receipts"}:
            continue
        item = getattr(value, name)
        result[name] = item.value if isinstance(item, Enum) else item
    return result


def _evidence_mapping(evidence):
    return [{"gate": item.gate.value,
             "evidence_record_fingerprint": item.evidence_record_fingerprint}
            for item in evidence]


def _receipt_mapping(receipts):
    return [{"gate": item.gate.value, "receipt_fingerprint": item.receipt_fingerprint}
            for item in receipts]
