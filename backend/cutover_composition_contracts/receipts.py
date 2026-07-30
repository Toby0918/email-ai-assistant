"""Closed composition-stage receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .binding import CompositionBindingV1
from .canonical import UNBOUND_FINGERPRINT, fingerprint, is_fingerprint
from .errors import CompositionContractError


class CompositionStage(str, Enum):
    CURRENT_TOPOLOGY = "current_topology"
    HOST_BASELINE = "host_baseline"
    EVIDENCE_REVIEW = "evidence_review"
    EVIDENCE_PUBLICATION = "evidence_publication"
    EVIDENCE_VERIFICATION = "evidence_verification"
    FINAL_AUDIT_READINESS = "final_audit_readiness"
    ACL_BASELINE = "acl_baseline"
    PRE_MUTATION_GATE = "pre_mutation_gate"
    ACL_PUBLICATION = "acl_publication"
    REPOSITORY_TRANSACTION = "repository_transaction"
    RUNTIME_PUBLICATION = "runtime_publication"
    DATABASE_PUBLICATION = "database_publication"
    ARTIFACT_PUBLICATION = "artifact_publication"
    CONFIG_PUBLICATION = "config_publication"
    ACTIVATION = "activation"
    FINAL_AUDIT = "final_audit"
    CUTOVER_SUCCESS = "cutover_success"
    RECOVERY_INSPECTION = "recovery_inspection"
    FAILED_CONTAINER_PRESERVATION = "failed_container_preservation"
    ROLLBACK_RESTORATION = "rollback_restoration"
    LEGACY_HEALTH = "legacy_health"


_JOURNAL_STAGES = {
    CompositionStage.ACL_PUBLICATION,
    CompositionStage.REPOSITORY_TRANSACTION,
    CompositionStage.RUNTIME_PUBLICATION,
    CompositionStage.DATABASE_PUBLICATION,
    CompositionStage.ARTIFACT_PUBLICATION,
    CompositionStage.CONFIG_PUBLICATION,
    CompositionStage.ACTIVATION,
    CompositionStage.FINAL_AUDIT,
    CompositionStage.CUTOVER_SUCCESS,
    CompositionStage.RECOVERY_INSPECTION,
    CompositionStage.FAILED_CONTAINER_PRESERVATION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
}
_WORKTREE_STAGES = {
    CompositionStage.REPOSITORY_TRANSACTION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
}
_ERROR = "PROJECT_CONTAINER_STAGE_RECEIPT_INVALID"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class CompositionStageReceiptV1:
    stage: CompositionStage
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_fingerprint: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    authorization_sequence_fingerprint: str = field(repr=False)
    prior_receipt_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    valid_until_epoch: int
    accepted: int
    rejected: int
    worktrees: int
    provider_attempts: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CompositionStageReceiptV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        binding: CompositionBindingV1,
        stage: CompositionStage,
        prior_receipt_fingerprint: str,
        observation_fingerprint: str,
        journal_owner_fingerprint: str,
        prior_journal_head_fingerprint: str,
        journal_head_fingerprint: str,
        valid_until_epoch: int,
        accepted: int,
        rejected: int,
        worktrees: int,
        provider_attempts: int,
    ) -> CompositionStageReceiptV1:
        body = _receipt_body(locals())
        value = object.__new__(cls)
        for name, item in body.items():
            object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "receipt_fingerprint",
            fingerprint("project-container-stage-receipt-v1", body),
        )
        return value

    def binding_tuple(self) -> tuple[str, ...]:
        return (
            self.operation_fingerprint,
            self.profile_fingerprint,
            self.governing_master_fingerprint,
            self.operator_fingerprint,
            self.authorization_sequence_fingerprint,
        )


def _receipt_body(values: dict[str, object]) -> dict[str, object]:
    binding = values["binding"]
    stage = values["stage"]
    if type(binding) is not CompositionBindingV1 or type(stage) is not CompositionStage:
        raise CompositionContractError(_ERROR)
    _require_field_types(values)
    _require_stage_values(stage, values)
    return {
        "stage": stage,
        **{
            name: getattr(binding, name)
            for name in (
                "operation_fingerprint",
                "profile_fingerprint",
                "governing_master_fingerprint",
                "operator_fingerprint",
                "authorization_sequence_fingerprint",
            )
        },
        **{
            name: values[name]
            for name in (
                "prior_receipt_fingerprint",
                "observation_fingerprint",
                "journal_owner_fingerprint",
                "prior_journal_head_fingerprint",
                "journal_head_fingerprint",
                "valid_until_epoch",
                "accepted",
                "rejected",
                "worktrees",
                "provider_attempts",
            )
        },
    }


def _require_field_types(values: dict[str, object]) -> None:
    fingerprints = (
        values["prior_receipt_fingerprint"],
        values["observation_fingerprint"],
        values["journal_owner_fingerprint"],
        values["prior_journal_head_fingerprint"],
        values["journal_head_fingerprint"],
    )
    counts = (
        values["valid_until_epoch"],
        values["accepted"],
        values["rejected"],
        values["worktrees"],
        values["provider_attempts"],
    )
    if not all(is_fingerprint(item) for item in fingerprints):
        raise CompositionContractError(_ERROR)
    if any(type(item) is not int or item < 0 for item in counts):
        raise CompositionContractError(_ERROR)


def _require_stage_values(stage: CompositionStage, values) -> None:
    journal_bound = stage in _JOURNAL_STAGES
    owner = values["journal_owner_fingerprint"]
    prior_head = values["prior_journal_head_fingerprint"]
    head = values["journal_head_fingerprint"]
    if (
        values["accepted"] != 1
        or values["rejected"] != 0
        or values["provider_attempts"] != 0
        or values["worktrees"] != (11 if stage in _WORKTREE_STAGES else 0)
        or (
            values["valid_until_epoch"] <= 0
            if stage is CompositionStage.PRE_MUTATION_GATE
            else values["valid_until_epoch"] != 0
        )
        or journal_bound != (owner != UNBOUND_FINGERPRINT)
        or journal_bound != (head != UNBOUND_FINGERPRINT)
        or (not journal_bound and prior_head != UNBOUND_FINGERPRINT)
    ):
        raise CompositionContractError(_ERROR)
