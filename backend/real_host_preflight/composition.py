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
from .receipts import (
    FinalAuditCompositionReadyReceiptV1,
    _mint_final_audit_ready_receipt,
)


_READINESS_LIFETIME_SECONDS = 60


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FinalAuditCompositionV1:
    _policy: TrustedAuditPolicy
    _adapters: ContainerAuditAdapters
    _bindings: tuple[BoundAuditCallbackV1, ...]
    _readers: tuple[object, ...]
    policy_fingerprint: str
    composition_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated final audit composition required")

    def run(self) -> ContainerAuditResult:
        """Run the unchanged read-only audit through its narrow bridge."""

        if not _composition_is_valid(self):
            raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
        return run_final_container_audit(
            policy=self._policy,
            adapters=self._adapters,
        )


def prepare_final_audit_composition(
    *,
    policy: TrustedAuditPolicy,
    callbacks: FinalAuditCallbacksV1,
) -> FinalAuditCompositionV1:
    """Bind exact policy and seven readers without invoking any reader."""

    if (
        type(callbacks) is not FinalAuditCallbacksV1
        or not audit_policy_is_valid(policy)
    ):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    bindings = callbacks.ordered()
    if not _bindings_are_valid(bindings):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    readers = tuple(item.reader for item in bindings)
    adapters = compose_audit_adapters(
        filesystem=callbacks.filesystem.reader,
        acl=callbacks.acl.reader,
        volume=callbacks.volume.reader,
        git=callbacks.git.reader,
        worktree=callbacks.worktree.reader,
        runtime=callbacks.runtime.reader,
        sqlite=callbacks.sqlite.reader,
    )
    policy_fingerprint = _policy_fingerprint(policy)
    composition_fingerprint = fingerprint(
        "final-audit-composition-v1",
        {
            "callback_bindings": [
                item.binding_fingerprint for item in bindings
            ],
            "policy_fingerprint": policy_fingerprint,
        },
    )
    return _new_composition(
        policy,
        adapters,
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

    authorization_fingerprint, authorization_expiry = (
        require_preflight_authorization(
            authorization,
            profile=profile,
            operation_fingerprint=operation_fingerprint,
            phase="final_audit_readiness",
            observed_at_epoch=observed_at_epoch,
        )
    )
    if not _composition_is_valid(composition):
        raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
    expires_at = min(
        observed_at_epoch + _READINESS_LIFETIME_SECONDS,
        authorization_expiry,
    )
    envelope = _create_readiness_receipt(
        profile=profile,
        authorization_fingerprint=authorization_fingerprint,
        operation_fingerprint=operation_fingerprint,
        policy_fingerprint=composition.policy_fingerprint,
        observation_fingerprint=composition.composition_fingerprint,
        observed_at_epoch=observed_at_epoch,
        expires_at_epoch=expires_at,
    )
    return _mint_final_audit_ready_receipt(envelope)


def _new_composition(
    policy: TrustedAuditPolicy,
    adapters: ContainerAuditAdapters,
    bindings: tuple[BoundAuditCallbackV1, ...],
    readers: tuple[object, ...],
    policy_fingerprint: str,
    composition_fingerprint: str,
) -> FinalAuditCompositionV1:
    value = object.__new__(FinalAuditCompositionV1)
    object.__setattr__(value, "_policy", policy)
    object.__setattr__(value, "_adapters", adapters)
    object.__setattr__(value, "_bindings", bindings)
    object.__setattr__(value, "_readers", readers)
    object.__setattr__(value, "policy_fingerprint", policy_fingerprint)
    object.__setattr__(
        value,
        "composition_fingerprint",
        composition_fingerprint,
    )
    return value


def _composition_is_valid(value: object) -> bool:
    if (
        type(value) is not FinalAuditCompositionV1
        or type(value._adapters) is not ContainerAuditAdapters
        or not audit_policy_is_valid(value._policy)
        or not _bindings_are_valid(value._bindings)
        or type(value._readers) is not tuple
        or len(value._readers) != 7
        or any(
            binding.reader is not reader
            for binding, reader in zip(
                value._bindings,
                value._readers,
                strict=True,
            )
        )
        or not _adapters_match(value._adapters, value._readers)
    ):
        return False
    policy_fingerprint = _policy_fingerprint(value._policy)
    expected = fingerprint(
        "final-audit-composition-v1",
        {
            "callback_bindings": [
                item.binding_fingerprint for item in value._bindings
            ],
            "policy_fingerprint": policy_fingerprint,
        },
    )
    return (
        value.policy_fingerprint == policy_fingerprint
        and value.composition_fingerprint == expected
    )


def _bindings_are_valid(bindings: object) -> bool:
    return (
        type(bindings) is tuple
        and len(bindings) == 7
        and all(bound_audit_callback_is_intact(item) for item in bindings)
        and len({item.binding_fingerprint for item in bindings}) == 7
    )


def _adapters_match(
    adapters: ContainerAuditAdapters,
    readers: tuple[object, ...],
) -> bool:
    actual = (
        adapters.filesystem,
        adapters.acl,
        adapters.volume,
        adapters.git,
        adapters.worktree,
        adapters.runtime,
        adapters.sqlite,
    )
    return all(
        actual_reader is expected_reader
        for actual_reader, expected_reader in zip(
            actual,
            readers,
            strict=True,
        )
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
