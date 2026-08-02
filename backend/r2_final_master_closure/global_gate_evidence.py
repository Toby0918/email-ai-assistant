"""Nominal content-free evidence from one registered independent producer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError
from .global_gate_registry import (
    GateEvidenceProducerV1,
    ReviewDomainV1,
    gate_evidence_registry,
)
from .vocabulary import ClosureGate


ZERO_GATE_FIELDS = (
    "required_skip_count", "unclassified_skip_count", "platform_divergence_count",
    "leakage_finding_count", "private_data_access_count", "real_host_operation_count",
    "provider_attempt_count", "issue39_code_change_count",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2GlobalGateEvidenceV1:
    evidence_type: str
    binding_fingerprint: str = field(repr=False)
    gate: ClosureGate
    producer: GateEvidenceProducerV1
    review_domain: ReviewDomainV1
    evidence_fingerprint: str = field(repr=False)
    producer_fingerprint: str = field(repr=False)
    verified: int
    self_certified: int
    required_skip_count: int
    unclassified_skip_count: int
    platform_divergence_count: int
    leakage_finding_count: int
    private_data_access_count: int
    real_host_operation_count: int
    provider_attempt_count: int
    issue39_code_change_count: int
    evidence_record_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2GlobalGateEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values):
        try:
            return _allocate(_evidence_body(values))
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    @classmethod
    def from_json(cls, payload, *, binding):
        try:
            source = strict_json_object(payload)
            result = cls.create(
                binding=binding,
                gate=ClosureGate(source["gate"]),
                producer=GateEvidenceProducerV1(source["producer"]),
                review_domain=ReviewDomainV1(source["review_domain"]),
                evidence_fingerprint=source["evidence_fingerprint"],
                producer_fingerprint=source["producer_fingerprint"],
            )
            if payload != canonical_json(source) or source != result.to_mapping():
                raise FinalMasterClosureError()
            return result
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    def to_mapping(self):
        result = {}
        for name in self.__dataclass_fields__:
            item = getattr(self, name)
            result[name] = item.value if isinstance(item, Enum) else item
        return result

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _evidence_body(values):
    expected = {"binding", "gate", "producer", "review_domain",
                "evidence_fingerprint", "producer_fingerprint"}
    if set(values) != expected or type(values["binding"]) is not FinalMasterBindingV1:
        raise FinalMasterClosureError()
    registration = next(
        (item for item in gate_evidence_registry() if item.gate is values["gate"]), None
    )
    if registration is None or (values["producer"], values["review_domain"]) != (
            registration.producer, registration.review_domain):
        raise FinalMasterClosureError()
    evidence, producer = values["evidence_fingerprint"], values["producer_fingerprint"]
    if not is_fingerprint(evidence) or not is_fingerprint(producer):
        raise FinalMasterClosureError()
    if len({evidence, producer, values["binding"].binding_fingerprint}) != 3:
        raise FinalMasterClosureError()
    return {
        "evidence_type": "R2GlobalGateEvidenceV1",
        "binding_fingerprint": values["binding"].binding_fingerprint,
        "gate": values["gate"].value,
        "producer": values["producer"].value,
        "review_domain": values["review_domain"].value,
        "evidence_fingerprint": evidence,
        "producer_fingerprint": producer,
        "verified": 1,
        "self_certified": 0,
        **{name: 0 for name in ZERO_GATE_FIELDS},
    }


def _allocate(body):
    value = object.__new__(R2GlobalGateEvidenceV1)
    for name, item in body.items():
        enum = ClosureGate if name == "gate" else (
            GateEvidenceProducerV1 if name == "producer" else (
                ReviewDomainV1 if name == "review_domain" else None))
        object.__setattr__(value, name, enum(item) if enum else item)
    object.__setattr__(value, "evidence_record_fingerprint",
                       fingerprint("r2-global-gate-evidence-v1", body))
    return value
