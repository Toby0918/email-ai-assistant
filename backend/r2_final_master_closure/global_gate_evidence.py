"""Externally signed evidence from one fixed independent gate producer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

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
_SIGNED_FIELDS = (
    "evidence_type", "binding_fingerprint", "gate", "producer", "review_domain",
    "evidence_fingerprint", "producer_fingerprint", "verified", "self_certified",
    *ZERO_GATE_FIELDS,
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
    signature_hex: str = field(repr=False)
    evidence_record_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2GlobalGateEvidenceV1 requires from_signed_json()")

    @classmethod
    def from_signed_json(cls, payload, *, binding):
        try:
            source = strict_json_object(payload)
            if payload != canonical_json(source) or set(source) != {*_SIGNED_FIELDS, "signature_hex"}:
                raise FinalMasterClosureError()
            body = {name: source[name] for name in _SIGNED_FIELDS}
            registration = _validate_body(body, binding)
            signature = bytes.fromhex(source["signature_hex"])
            if len(signature) != 64:
                raise FinalMasterClosureError()
            Ed25519PublicKey.from_public_bytes(
                registration.verification_public_key
            ).verify(signature, canonical_json(body))
            return _allocate({**body, "signature_hex": source["signature_hex"]})
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    @classmethod
    def from_json(cls, payload, *, binding):
        return cls.from_signed_json(payload, binding=binding)

    def to_mapping(self):
        result = {}
        for name in self.__dataclass_fields__:
            item = getattr(self, name)
            result[name] = item.value if isinstance(item, Enum) else item
        return result

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def producer_fingerprint_v1(registration):
    return fingerprint("r2-gate-producer-v1", {
        "producer": registration.producer.value,
        "verification_public_key_hex": registration.verification_public_key.hex(),
    })


def _validate_body(body, binding):
    if type(binding) is not FinalMasterBindingV1:
        raise FinalMasterClosureError()
    try:
        gate = ClosureGate(body["gate"])
        producer = GateEvidenceProducerV1(body["producer"])
        domain = ReviewDomainV1(body["review_domain"])
    except Exception:
        raise FinalMasterClosureError() from None
    registration = next((item for item in gate_evidence_registry() if item.gate is gate), None)
    if registration is None or (producer, domain) != (
        registration.producer, registration.review_domain
    ):
        raise FinalMasterClosureError()
    expected = {
        "evidence_type": "R2SignedGlobalGateEvidenceV1",
        "binding_fingerprint": binding.binding_fingerprint,
        "gate": gate.value,
        "producer": producer.value,
        "review_domain": domain.value,
        "evidence_fingerprint": body["evidence_fingerprint"],
        "producer_fingerprint": producer_fingerprint_v1(registration),
        "verified": 1,
        "self_certified": 0,
        **{name: 0 for name in ZERO_GATE_FIELDS},
    }
    if body != expected or not is_fingerprint(body["evidence_fingerprint"]):
        raise FinalMasterClosureError()
    if body["evidence_fingerprint"] in {
        binding.binding_fingerprint, expected["producer_fingerprint"]
    }:
        raise FinalMasterClosureError()
    return registration


def _allocate(body):
    value = object.__new__(R2GlobalGateEvidenceV1)
    for name, item in body.items():
        enum = ClosureGate if name == "gate" else (
            GateEvidenceProducerV1 if name == "producer" else (
                ReviewDomainV1 if name == "review_domain" else None
            )
        )
        object.__setattr__(value, name, enum(item) if enum else item)
    object.__setattr__(value, "evidence_record_fingerprint",
                       fingerprint("r2-signed-global-gate-evidence-v1", body))
    return value
