"""Nominal read-only views over the closed Issue #51 receipt envelope."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts_bridge import ReceiptEnvelopeV1


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CurrentTopologyPreflightReceiptV1:
    """An accepted repeated-current-topology receipt."""

    _envelope: ReceiptEnvelopeV1

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated receipt construction required")

    @classmethod
    def from_envelope(
        cls,
        envelope: ReceiptEnvelopeV1,
    ) -> CurrentTopologyPreflightReceiptV1:
        _require_preflight_receipt(envelope, "repeated_current_topology")
        value = object.__new__(cls)
        object.__setattr__(value, "_envelope", envelope)
        return value

    @property
    def receipt_fingerprint(self) -> str:
        return self._envelope.receipt_fingerprint

    @property
    def observation_fingerprint(self) -> str:
        return self._envelope.observation_fingerprint

    def to_mapping(self) -> dict[str, object]:
        return self._envelope.to_mapping()

    def to_canonical_json(self) -> bytes:
        return self._envelope.to_canonical_json()


@dataclass(frozen=True, slots=True, init=False, repr=False)
class PreMutationGateReceiptV1:
    """An accepted short-lived pre-mutation gate receipt."""

    _envelope: ReceiptEnvelopeV1

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated receipt construction required")

    @classmethod
    def from_envelope(
        cls,
        envelope: ReceiptEnvelopeV1,
    ) -> PreMutationGateReceiptV1:
        _require_preflight_receipt(envelope, "pre_mutation_gate")
        value = object.__new__(cls)
        object.__setattr__(value, "_envelope", envelope)
        return value

    @property
    def receipt_fingerprint(self) -> str:
        return self._envelope.receipt_fingerprint

    @property
    def observation_fingerprint(self) -> str:
        return self._envelope.observation_fingerprint

    def to_mapping(self) -> dict[str, object]:
        return self._envelope.to_mapping()

    def to_canonical_json(self) -> bytes:
        return self._envelope.to_canonical_json()


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FinalAuditCompositionReadyReceiptV1:
    """A readiness receipt that makes no final-layout pass claim."""

    _envelope: ReceiptEnvelopeV1

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated receipt construction required")

    @classmethod
    def from_envelope(
        cls,
        envelope: ReceiptEnvelopeV1,
    ) -> FinalAuditCompositionReadyReceiptV1:
        _require_preflight_receipt(envelope, "final_audit_readiness")
        value = object.__new__(cls)
        object.__setattr__(value, "_envelope", envelope)
        return value

    @property
    def receipt_fingerprint(self) -> str:
        return self._envelope.receipt_fingerprint

    def to_mapping(self) -> dict[str, object]:
        return self._envelope.to_mapping()

    def to_canonical_json(self) -> bytes:
        return self._envelope.to_canonical_json()


def _require_preflight_receipt(
    envelope: object,
    observation_kind: str,
) -> None:
    if type(envelope) is not ReceiptEnvelopeV1:
        raise ValueError("REAL_HOST_RECEIPT_INVALID")
    mapping = envelope.to_mapping()
    if (
        mapping["receipt_type"] != "PreflightReceiptV1"
        or mapping["status"] != "PREFLIGHT_ACCEPTED"
        or mapping["operation"] != "real_preflight"
        or mapping["producer"] != "real_preflight_composition"
        or mapping["subject_role"] != "operation"
        or mapping["details"]
        != {"observation_kind": observation_kind}
    ):
        raise ValueError("REAL_HOST_RECEIPT_INVALID")
