"""Two-pass current-topology preflight with fixed read-only callbacks."""

from __future__ import annotations

from .authorization_gate import require_preflight_authorization
from .callbacks import CurrentTopologyCallbacks
from .canonical import fingerprint, is_fingerprint
from .collection import collect_current_topology
from .contracts_bridge import CutoverProfileV1, ReceiptEnvelopeV1
from .receipts import (
    CurrentTopologyPreflightReceiptV1,
    _mint_current_topology_receipt,
)


_RECEIPT_LIFETIME_SECONDS = 60


def run_current_topology_preflight(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    policy_fingerprint: str,
    observed_at_epoch: int,
    callbacks: CurrentTopologyCallbacks,
) -> CurrentTopologyPreflightReceiptV1:
    """Require two complete identical seven-reader observations."""

    authorization_fingerprint, authorization_expiry = (
        require_preflight_authorization(
            authorization,
            profile=profile,
            operation_fingerprint=operation_fingerprint,
            phase="current_topology_preflight",
            observed_at_epoch=observed_at_epoch,
        )
    )
    if (
        type(callbacks) is not CurrentTopologyCallbacks
        or not is_fingerprint(policy_fingerprint)
    ):
        raise ValueError("REAL_HOST_TOPOLOGY_REJECTED")
    first = collect_current_topology(callbacks, profile=profile)
    second = collect_current_topology(callbacks, profile=profile)
    if second != first:
        raise ValueError("REAL_HOST_TOPOLOGY_REJECTED")
    repeated = fingerprint(
        "repeated-current-topology-v1",
        [first.observation_fingerprint, second.observation_fingerprint],
    )
    expires_at = min(
        observed_at_epoch + _RECEIPT_LIFETIME_SECONDS,
        authorization_expiry,
    )
    envelope = _create_receipt(
        profile=profile,
        authorization_fingerprint=authorization_fingerprint,
        operation_fingerprint=operation_fingerprint,
        policy_fingerprint=policy_fingerprint,
        observation_fingerprint=repeated,
        observed_at_epoch=observed_at_epoch,
        expires_at_epoch=expires_at,
    )
    return _mint_current_topology_receipt(envelope)


def _create_receipt(
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
            "details": {
                "observation_kind": "repeated_current_topology",
            },
        }
    )
