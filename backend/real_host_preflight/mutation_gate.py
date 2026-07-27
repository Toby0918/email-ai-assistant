"""Fresh, nonce-bound, single-use pre-mutation observation gate."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock
from weakref import WeakKeyDictionary

from .authorization_gate import require_preflight_authorization
from .callbacks import CurrentTopologyCallbacks
from .canonical import fingerprint, is_fingerprint
from .collection import collect_current_topology
from .contracts_bridge import CutoverProfileV1, ReceiptEnvelopeV1
from .profile_snapshot import snapshot_cutover_profile
from .receipts import (
    CurrentTopologyPreflightReceiptV1,
    PreMutationGateReceiptV1,
    _claim_current_topology_receipt,
    _mint_pre_mutation_gate_receipt,
)


_GATE_LIFETIME_SECONDS = 60
_GATE_ERROR = "REAL_HOST_GATE_REJECTED"


@dataclass(slots=True)
class _GateState:
    topology_receipt: CurrentTopologyPreflightReceiptV1
    callbacks: CurrentTopologyCallbacks
    policy_fingerprint: str
    consumed: bool = False


_GATE_STATES: WeakKeyDictionary[object, _GateState] = WeakKeyDictionary()
_GATE_STATES_LOCK = Lock()


class PreMutationGate:
    """One in-memory gate that is consumed by its first attempt."""

    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated pre-mutation gate binding required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError(_GATE_ERROR)

    def __copy__(self) -> PreMutationGate:
        raise ValueError(_GATE_ERROR)

    def __deepcopy__(self, _memo: object) -> PreMutationGate:
        raise ValueError(_GATE_ERROR)

    def __reduce__(self) -> object:
        raise ValueError(_GATE_ERROR)

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError(_GATE_ERROR)

    @classmethod
    def bind(
        cls,
        *,
        current_topology_receipt: CurrentTopologyPreflightReceiptV1,
        callbacks: CurrentTopologyCallbacks,
        policy_fingerprint: str,
    ) -> PreMutationGate:
        try:
            return _bind_gate(
                cls=cls,
                topology_receipt=current_topology_receipt,
                callbacks=callbacks,
                policy_fingerprint=policy_fingerprint,
            )
        except Exception:
            raise ValueError(_GATE_ERROR) from None

    def evaluate(
        self,
        *,
        profile: CutoverProfileV1,
        authorization: object,
        operation_fingerprint: str,
        nonce: str,
        observed_at_epoch: int,
    ) -> PreMutationGateReceiptV1:
        state = _consume_gate(self)
        try:
            return self._evaluate_once(
                state=state,
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation_fingerprint,
                nonce=nonce,
                observed_at_epoch=observed_at_epoch,
            )
        except Exception:
            raise ValueError(_GATE_ERROR) from None

    def _evaluate_once(
        self,
        *,
        state: _GateState,
        profile: CutoverProfileV1,
        authorization: object,
        operation_fingerprint: str,
        nonce: str,
        observed_at_epoch: int,
    ) -> PreMutationGateReceiptV1:
        profile_snapshot = snapshot_cutover_profile(profile)
        prior = state.topology_receipt.to_mapping()
        _require_prior_binding(
            prior, profile_snapshot, operation_fingerprint, observed_at_epoch
        )
        _require_uuid4(nonce)
        authorization_fingerprint, authorization_expiry = (
            require_preflight_authorization(
                authorization,
                profile=profile_snapshot,
                operation_fingerprint=operation_fingerprint,
                phase="current_topology_preflight",
                observed_at_epoch=observed_at_epoch,
            )
        )
        observation = _repeat_gate_observation(
            callbacks=state.callbacks,
            profile=profile_snapshot,
            prior_observation_fingerprint=prior["observation_fingerprint"],
            prior_receipt_fingerprint=state.topology_receipt.receipt_fingerprint,
            operation_fingerprint=operation_fingerprint,
            nonce=nonce,
        )
        expires_at = min(
            observed_at_epoch + _GATE_LIFETIME_SECONDS,
            authorization_expiry,
            prior["validity"]["expires_at_epoch"],
        )
        envelope = _create_gate_receipt(
            profile=profile_snapshot,
            authorization_fingerprint=authorization_fingerprint,
            operation_fingerprint=operation_fingerprint,
            policy_fingerprint=state.policy_fingerprint,
            observation_fingerprint=observation,
            observed_at_epoch=observed_at_epoch,
            expires_at_epoch=expires_at,
        )
        return _mint_pre_mutation_gate_receipt(envelope)


def _bind_gate(
    *,
    cls: type[PreMutationGate],
    topology_receipt: CurrentTopologyPreflightReceiptV1,
    callbacks: CurrentTopologyCallbacks,
    policy_fingerprint: str,
) -> PreMutationGate:
    if (
        cls is not PreMutationGate
        or type(topology_receipt) is not CurrentTopologyPreflightReceiptV1
        or type(callbacks) is not CurrentTopologyCallbacks
        or not is_fingerprint(policy_fingerprint)
    ):
        raise ValueError(_GATE_ERROR)
    mapping = topology_receipt.to_mapping()
    expected_policy = {"role": "policy", "fingerprint": policy_fingerprint}
    if mapping["input_fingerprints"][2] != expected_policy:
        raise ValueError(_GATE_ERROR)
    bound_callbacks = CurrentTopologyCallbacks(
        source_root=callbacks.source_root,
        target_parent=callbacks.target_parent,
        finance_root=callbacks.finance_root,
        target_absence=callbacks.target_absence,
        git=callbacks.git,
        acl=callbacks.acl,
        volume=callbacks.volume,
    )
    _claim_current_topology_receipt(topology_receipt)
    gate = object.__new__(PreMutationGate)
    state = _GateState(topology_receipt, bound_callbacks, policy_fingerprint)
    with _GATE_STATES_LOCK:
        _GATE_STATES[gate] = state
    return gate


def _consume_gate(gate: object) -> _GateState:
    if type(gate) is not PreMutationGate:
        raise ValueError(_GATE_ERROR)
    with _GATE_STATES_LOCK:
        state = _GATE_STATES.get(gate)
        if state is None or state.consumed:
            raise ValueError(_GATE_ERROR)
        state.consumed = True
    return state


def _repeat_gate_observation(
    *,
    callbacks: CurrentTopologyCallbacks,
    profile: CutoverProfileV1,
    prior_observation_fingerprint: str,
    prior_receipt_fingerprint: str,
    operation_fingerprint: str,
    nonce: str,
) -> str:
    current = collect_current_topology(callbacks, profile=profile)
    repeated = fingerprint(
        "repeated-current-topology-v1",
        [
            current.observation_fingerprint,
            current.observation_fingerprint,
        ],
    )
    if repeated != prior_observation_fingerprint:
        raise ValueError("REAL_HOST_GATE_REJECTED")
    return fingerprint(
        "pre-mutation-gate-v1",
        {
            "current_observation": current.observation_fingerprint,
            "nonce": nonce,
            "operation_fingerprint": operation_fingerprint,
            "prior_receipt": prior_receipt_fingerprint,
        },
    )


def _require_prior_binding(
    prior: dict[str, object],
    profile: object,
    operation_fingerprint: object,
    observed_at_epoch: object,
) -> None:
    if (
        type(profile) is not CutoverProfileV1
        or prior["profile_fingerprint"] != profile.profile_fingerprint
        or prior["governing_master_commit"]
        != profile.governing_master_commit
        or prior["operation_fingerprint"] != operation_fingerprint
        or type(observed_at_epoch) is not int
        or not (
            prior["validity"]["issued_at_epoch"]
            <= observed_at_epoch
            < prior["validity"]["expires_at_epoch"]
        )
    ):
        raise ValueError("REAL_HOST_GATE_REJECTED")


def _require_uuid4(value: object) -> None:
    try:
        parsed = uuid.UUID(value) if type(value) is str else None
    except (ValueError, AttributeError):
        parsed = None
    if parsed is None or parsed.version != 4 or str(parsed) != value:
        raise ValueError("REAL_HOST_GATE_REJECTED")


def _create_gate_receipt(
    *,
    profile: CutoverProfileV1,
    authorization_fingerprint: str,
    operation_fingerprint: str,
    policy_fingerprint: str,
    observation_fingerprint: str,
    observed_at_epoch: int,
    expires_at_epoch: int,
) -> ReceiptEnvelopeV1:
    return ReceiptEnvelopeV1.create(
        {
            "receipt_type": "PreflightReceiptV1",
            "status": "PREFLIGHT_ACCEPTED",
            "operation": "real_preflight",
            "operation_fingerprint": operation_fingerprint,
            "profile_fingerprint": profile.profile_fingerprint,
            "governing_master_commit": profile.governing_master_commit,
            "authorization_fingerprint": authorization_fingerprint,
            "producer": "real_preflight_composition",
            "subject_role": "operation",
            "input_fingerprints": [
                {
                    "role": "profile",
                    "fingerprint": profile.profile_fingerprint,
                },
                {
                    "role": "authorization",
                    "fingerprint": authorization_fingerprint,
                },
                {"role": "policy", "fingerprint": policy_fingerprint},
            ],
            "observation_fingerprint": observation_fingerprint,
            "counts": {"accepted": 1, "rejected": 0},
            "validity": {
                "issued_at_epoch": observed_at_epoch,
                "expires_at_epoch": expires_at_epoch,
            },
            "details": {"observation_kind": "pre_mutation_gate"},
        }
    )
