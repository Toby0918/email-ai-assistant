"""Nominal read-only views over the closed Issue #51 receipt envelope."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from weakref import WeakKeyDictionary

from .contracts_bridge import ReceiptEnvelopeV1


_RECEIPT_ERROR = "REAL_HOST_RECEIPT_INVALID"


@dataclass(slots=True)
class _ReceiptState:
    envelope: ReceiptEnvelopeV1
    observation_kind: str
    claimed: bool = False


_RECEIPT_STATES: WeakKeyDictionary[object, _ReceiptState] = (
    WeakKeyDictionary()
)
_RECEIPT_STATES_LOCK = Lock()


class _ReceiptView:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated receipt construction required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError(_RECEIPT_ERROR)

    def __delattr__(self, _name: str) -> None:
        raise ValueError(_RECEIPT_ERROR)

    def __copy__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __deepcopy__(self, _memo: object) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __reduce__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __getstate__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    @property
    def receipt_fingerprint(self) -> str:
        return _receipt_envelope(self).receipt_fingerprint

    def to_mapping(self) -> dict[str, object]:
        return _receipt_envelope(self).to_mapping()

    def to_canonical_json(self) -> bytes:
        return _receipt_envelope(self).to_canonical_json()


class CurrentTopologyPreflightReceiptV1(_ReceiptView):
    """An accepted repeated-current-topology receipt."""

    __slots__ = ()

    @property
    def observation_fingerprint(self) -> str:
        return _receipt_envelope(self).observation_fingerprint


class PreMutationGateReceiptV1(_ReceiptView):
    """An accepted short-lived pre-mutation gate receipt."""

    __slots__ = ()

    @property
    def observation_fingerprint(self) -> str:
        return _receipt_envelope(self).observation_fingerprint


class FinalAuditCompositionReadyReceiptV1(_ReceiptView):
    """A readiness receipt that makes no final-layout pass claim."""

    __slots__ = ()


def _mint_current_topology_receipt(
    envelope: ReceiptEnvelopeV1,
) -> CurrentTopologyPreflightReceiptV1:
    return _mint_receipt(
        CurrentTopologyPreflightReceiptV1,
        envelope,
        "repeated_current_topology",
    )


def _mint_pre_mutation_gate_receipt(
    envelope: ReceiptEnvelopeV1,
) -> PreMutationGateReceiptV1:
    return _mint_receipt(
        PreMutationGateReceiptV1,
        envelope,
        "pre_mutation_gate",
    )


def _mint_final_audit_ready_receipt(
    envelope: ReceiptEnvelopeV1,
) -> FinalAuditCompositionReadyReceiptV1:
    return _mint_receipt(
        FinalAuditCompositionReadyReceiptV1,
        envelope,
        "final_audit_readiness",
    )


def _claim_current_topology_receipt(
    receipt: CurrentTopologyPreflightReceiptV1,
) -> None:
    if type(receipt) is not CurrentTopologyPreflightReceiptV1:
        raise ValueError(_RECEIPT_ERROR)
    with _RECEIPT_STATES_LOCK:
        state = _RECEIPT_STATES.get(receipt)
        if (
            state is None
            or state.observation_kind != "repeated_current_topology"
            or state.claimed
        ):
            raise ValueError(_RECEIPT_ERROR)
        state.claimed = True


def _mint_receipt(
    receipt_type: type[_ReceiptView],
    envelope: ReceiptEnvelopeV1,
    observation_kind: str,
) -> object:
    canonical = _round_trip_envelope(envelope)
    _require_preflight_receipt(canonical, observation_kind)
    receipt = object.__new__(receipt_type)
    state = _ReceiptState(canonical, observation_kind)
    with _RECEIPT_STATES_LOCK:
        _RECEIPT_STATES[receipt] = state
    return receipt


def _receipt_envelope(receipt: object) -> ReceiptEnvelopeV1:
    if type(receipt) not in (
        CurrentTopologyPreflightReceiptV1,
        PreMutationGateReceiptV1,
        FinalAuditCompositionReadyReceiptV1,
    ):
        raise ValueError(_RECEIPT_ERROR)
    with _RECEIPT_STATES_LOCK:
        state = _RECEIPT_STATES.get(receipt)
    if state is None:
        raise ValueError(_RECEIPT_ERROR)
    return state.envelope


def _round_trip_envelope(envelope: object) -> ReceiptEnvelopeV1:
    try:
        if type(envelope) is not ReceiptEnvelopeV1:
            raise ValueError(_RECEIPT_ERROR)
        mapping = envelope.to_mapping()
        canonical = ReceiptEnvelopeV1.from_mapping(mapping)
        if canonical.to_canonical_json() != envelope.to_canonical_json():
            raise ValueError(_RECEIPT_ERROR)
        return canonical
    except Exception:
        raise ValueError(_RECEIPT_ERROR) from None


def _require_preflight_receipt(
    envelope: ReceiptEnvelopeV1,
    observation_kind: str,
) -> None:
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
        raise ValueError(_RECEIPT_ERROR)
