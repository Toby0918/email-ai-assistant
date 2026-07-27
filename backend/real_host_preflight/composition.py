"""Final ContainerAudit composition and non-executing readiness proof."""

from __future__ import annotations

from dataclasses import dataclass

from .audit_bridge import (
    ContainerAuditAdapters,
    ContainerAuditResult,
    TrustedAuditPolicy,
    audit_policy_is_valid,
    compose_audit_adapters,
    run_final_container_audit,
)
from .audit_types import (
    BoundAuditCallbackV1,
    FinalAuditCallbacksV1,
    bound_audit_callback_is_intact,
)
from .authorization_gate import require_preflight_authorization
from .canonical import fingerprint
from .contracts_bridge import CutoverProfileV1, ReceiptEnvelopeV1
from .profile_snapshot import snapshot_cutover_profile
from .receipts import (
    FinalAuditCompositionReadyReceiptV1,
    _mint_final_audit_ready_receipt,
)


_READINESS_LIFETIME_SECONDS = 60


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FinalAuditCompositionV1:
    _policy: TrustedAuditPolicy
    _bindings: tuple[BoundAuditCallbackV1, ...]
    _readers: tuple[object, ...]
    policy_fingerprint: str
    composition_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated final audit composition required")

    def run(self) -> ContainerAuditResult:
        """Run the unchanged read-only audit through its narrow bridge."""

        try:
            captured = _capture_composition(self)
            if not _composition_is_valid(captured):
                raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
            adapters = _compose_reader_snapshot(captured[2])
        except Exception:
            raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED") from None
        return run_final_container_audit(
            policy=captured[0],
            adapters=adapters,
        )


def prepare_final_audit_composition(
    *,
    policy: TrustedAuditPolicy,
    callbacks: FinalAuditCallbacksV1,
) -> FinalAuditCompositionV1:
    """Bind exact policy and seven readers without invoking any reader."""

    if type(callbacks) is not FinalAuditCallbacksV1:
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    policy_snapshot = _snapshot_policy(policy)
    bindings = callbacks.ordered()
    if not _bindings_are_valid(bindings):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    readers = tuple(item.reader for item in bindings)
    policy_fingerprint = _policy_fingerprint(policy_snapshot)
    composition_fingerprint = _composition_fingerprint(
        bindings, policy_fingerprint
    )
    return _new_composition(
        policy_snapshot,
        bindings,
        readers,
        policy_fingerprint,
        composition_fingerprint,
    )


def prove_final_audit_composition_ready(
    *,
    profile: CutoverProfileV1,
    authorization: object,
    operation_fingerprint: str,
    observed_at_epoch: int,
    composition: FinalAuditCompositionV1,
) -> FinalAuditCompositionReadyReceiptV1:
    """Issue readiness only; never invoke the composed audit."""

    profile_snapshot = snapshot_cutover_profile(profile)
    authorization_fingerprint, authorization_expiry = (
        require_preflight_authorization(
            authorization,
            profile=profile_snapshot,
            operation_fingerprint=operation_fingerprint,
            phase="final_audit_readiness",
            observed_at_epoch=observed_at_epoch,
        )
    )
    captured = _capture_composition(composition)
    if not _composition_is_valid(captured):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    expires_at = min(
        observed_at_epoch + _READINESS_LIFETIME_SECONDS,
        authorization_expiry,
    )
    envelope = _create_readiness_receipt(
        profile=profile_snapshot,
        authorization_fingerprint=authorization_fingerprint,
        operation_fingerprint=operation_fingerprint,
        policy_fingerprint=captured[3],
        observation_fingerprint=captured[4],
        observed_at_epoch=observed_at_epoch,
        expires_at_epoch=expires_at,
    )
    return _mint_final_audit_ready_receipt(envelope)


def _new_composition(
    policy: TrustedAuditPolicy,
    bindings: tuple[BoundAuditCallbackV1, ...],
    readers: tuple[object, ...],
    policy_fingerprint: str,
    composition_fingerprint: str,
) -> FinalAuditCompositionV1:
    value = object.__new__(FinalAuditCompositionV1)
    names = ("_policy", "_bindings", "_readers", "policy_fingerprint",
             "composition_fingerprint")
    values = (policy, bindings, readers, policy_fingerprint,
              composition_fingerprint)
    for name, item in zip(names, values, strict=True):
        object.__setattr__(value, name, item)
    return value


def _capture_composition(value: object) -> tuple[object, ...]:
    if type(value) is not FinalAuditCompositionV1:
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    return (_snapshot_policy(value._policy), value._bindings, value._readers,
            value.policy_fingerprint, value.composition_fingerprint)


def _composition_is_valid(value: object) -> bool:
    if type(value) is not tuple or len(value) != 5:
        return False
    policy, bindings, readers, policy_binding, composition_binding = value
    if (
        not audit_policy_is_valid(policy)
        or not _bindings_are_valid(bindings)
        or type(readers) is not tuple
        or len(readers) != 7
        or any(
            binding.reader is not reader
            for binding, reader in zip(
                bindings,
                readers,
                strict=True,
            )
        )
    ):
        return False
    policy_fingerprint = _policy_fingerprint(policy)
    expected = _composition_fingerprint(bindings, policy_fingerprint)
    return (
        policy_binding == policy_fingerprint
        and composition_binding == expected
    )


def _bindings_are_valid(bindings: object) -> bool:
    return (
        type(bindings) is tuple
        and len(bindings) == 7
        and all(bound_audit_callback_is_intact(item) for item in bindings)
        and len({item.binding_fingerprint for item in bindings}) == 7
    )


def _composition_fingerprint(
    bindings: tuple[BoundAuditCallbackV1, ...],
    policy_fingerprint: str,
) -> str:
    return fingerprint(
        "final-audit-composition-v1",
        {
            "callback_bindings": [item.binding_fingerprint for item in bindings],
            "policy_fingerprint": policy_fingerprint,
        },
    )


def _snapshot_policy(policy: object) -> TrustedAuditPolicy:
    if not audit_policy_is_valid(policy):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    try:
        snapshot = TrustedAuditPolicy(
            schema_version=policy.schema_version,
            container_identity=policy.container_identity,
            container_acl_fingerprint=policy.container_acl_fingerprint,
            operator_private_acl_fingerprint=(
                policy.operator_private_acl_fingerprint
            ),
            volume_identity=policy.volume_identity,
            approved_worktrees=tuple(policy.approved_worktrees),
            require_clean_worktrees=policy.require_clean_worktrees,
            sqlite_expectation=policy.sqlite_expectation,
        )
    except Exception:
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED") from None
    if (
        not audit_policy_is_valid(snapshot)
        or _policy_fingerprint(snapshot) != _policy_fingerprint(policy)
    ):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    return snapshot


def _compose_reader_snapshot(
    readers: tuple[object, ...],
) -> ContainerAuditAdapters:
    return compose_audit_adapters(
        filesystem=readers[0],
        acl=readers[1],
        volume=readers[2],
        git=readers[3],
        worktree=readers[4],
        runtime=readers[5],
        sqlite=readers[6],
    )


def _policy_fingerprint(policy: TrustedAuditPolicy) -> str:
    return fingerprint(
        "final-container-audit-policy-v1",
        {
            "approved_worktrees": list(policy.approved_worktrees),
            "container_acl_fingerprint": policy.container_acl_fingerprint,
            "container_identity": policy.container_identity,
            "operator_private_acl_fingerprint": (
                policy.operator_private_acl_fingerprint
            ),
            "require_clean_worktrees": policy.require_clean_worktrees,
            "schema_version": policy.schema_version,
            "sqlite_expectation": policy.sqlite_expectation.value,
            "volume_identity": policy.volume_identity,
        },
    )


def _create_readiness_receipt(
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
                "observation_kind": "final_audit_readiness",
            },
        }
    )
