"""Fresh, nonce-bound, single-use pre-mutation observation gate."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from threading import Lock

from .authorization_gate import require_preflight_authorization
from .callbacks import CurrentTopologyCallbacks
from .canonical import fingerprint, is_fingerprint
from .collection import collect_current_topology
from .contracts_bridge import CutoverProfileV1, ReceiptEnvelopeV1
from .receipts import (
    CurrentTopologyPreflightReceiptV1,
    PreMutationGateReceiptV1,
)


_GATE_LIFETIME_SECONDS = 60


@dataclass(slots=True, init=False, repr=False)
class PreMutationGate:
    """One in-memory gate that is consumed by its first attempt."""

    _topology_receipt: CurrentTopologyPreflightReceiptV1
    _callbacks: CurrentTopologyCallbacks
    _policy_fingerprint: str
    _consumed: bool
    _consume_lock: Lock

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated pre-mutation gate binding required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError("REAL_HOST_GATE_REJECTED")

    def __copy__(self) -> PreMutationGate:
        raise ValueError("REAL_HOST_GATE_REJECTED")

    def __deepcopy__(self, _memo: object) -> PreMutationGate:
        raise ValueError("REAL_HOST_GATE_REJECTED")

    def __reduce__(self) -> object:
        raise ValueError("REAL_HOST_GATE_REJECTED")

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError("REAL_HOST_GATE_REJECTED")

    def __getstate__(self) -> object:
        raise ValueError("REAL_HOST_GATE_REJECTED")

    @classmethod
    def bind(
        cls,
        *,
        current_topology_receipt: CurrentTopologyPreflightReceiptV1,
        callbacks: CurrentTopologyCallbacks,
        policy_fingerprint: str,
    ) -> PreMutationGate:
        if (
            type(current_topology_receipt)
            is not CurrentTopologyPreflightReceiptV1
            or type(callbacks) is not CurrentTopologyCallbacks
            or not is_fingerprint(policy_fingerprint)
        ):
            raise ValueError("REAL_HOST_GATE_REJECTED")
        mapping = current_topology_receipt.to_mapping()
        policy_input = mapping["input_fingerprints"][2]
        if policy_input != {
            "role": "policy",
            "fingerprint": policy_fingerprint,
        }:
            raise ValueError("REAL_HOST_GATE_REJECTED")
        gate = object.__new__(cls)
        object.__setattr__(
            gate,
            "_topology_receipt",
            current_topology_receipt,
        )
        object.__setattr__(gate, "_callbacks", callbacks)
        object.__setattr__(
            gate,
            "_policy_fingerprint",
            policy_fingerprint,
        )
        object.__setattr__(gate, "_consumed", False)
        object.__setattr__(gate, "_consume_lock", Lock())
        return gate

    def evaluate(
        self,
        *,
        profile: CutoverProfileV1,
        authorization: object,
        operation_fingerprint: str,
        nonce: str,
        observed_at_epoch: int,
    ) -> PreMutationGateReceiptV1:
        with self._consume_lock:
            if self._consumed:
                raise ValueError("REAL_HOST_GATE_REJECTED")
            object.__setattr__(self, "_consumed", True)
        try:
            return self._evaluate_once(
                profile=profile,
                authorization=authorization,
                operation_fingerprint=operation_fingerprint,
                nonce=nonce,
                observed_at_epoch=observed_at_epoch,
            )
        except Exception:
            raise ValueError("REAL_HOST_GATE_REJECTED") from None

    def _evaluate_once(
        self,
        *,
        profile: CutoverProfileV1,
        authorization: object,
        operation_fingerprint: str,
        nonce: str,
        observed_at_epoch: int,
    ) -> PreMutationGateReceiptV1:
        prior = self._topology_receipt.to_mapping()
        _require_prior_binding(
            prior, profile, operation_fingerprint, observed_at_epoch
        )
        _require_uuid4(nonce)
        authorization_fingerprint, authorization_expiry = (
            require_preflight_authorization(
                authorization,
                profile=profile,
                operation_fingerprint=operation_fingerprint,
                phase="current_topology_preflight",
                observed_at_epoch=observed_at_epoch,
            )
        )
        observation = _repeat_gate_observation(
            callbacks=self._callbacks,
            prior_observation_fingerprint=prior["observation_fingerprint"],
            prior_receipt_fingerprint=(
                self._topology_receipt.receipt_fingerprint
            ),
            operation_fingerprint=operation_fingerprint,
            nonce=nonce,
        )
        expires_at = min(
            observed_at_epoch + _GATE_LIFETIME_SECONDS,
            authorization_expiry,
            prior["validity"]["expires_at_epoch"],
        )
        envelope = _create_gate_receipt(
            profile=profile,
            authorization_fingerprint=authorization_fingerprint,
            operation_fingerprint=operation_fingerprint,
            policy_fingerprint=self._policy_fingerprint,
            observation_fingerprint=observation,
            observed_at_epoch=observed_at_epoch,
            expires_at_epoch=expires_at,
        )
        return PreMutationGateReceiptV1.from_envelope(envelope)


def _repeat_gate_observation(
    *,
    callbacks: CurrentTopologyCallbacks,
    prior_observation_fingerprint: str,
    prior_receipt_fingerprint: str,
    operation_fingerprint: str,
    nonce: str,
) -> str:
    current = collect_current_topology(callbacks)
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
