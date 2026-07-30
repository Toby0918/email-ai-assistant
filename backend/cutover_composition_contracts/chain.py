"""Strict ordered Project Container receipt chain."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import UNBOUND_FINGERPRINT, fingerprint
from .errors import CompositionContractError
from .receipts import CompositionStage, CompositionStageReceiptV1


class ReceiptChainState(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    PREFLIGHT_READY = "PREFLIGHT_READY"
    CUTOVER_SUCCEEDED = "CUTOVER_SUCCEEDED"
    LEGACY_RECOVERED = "LEGACY_RECOVERED"


_PREFIX = (
    CompositionStage.CURRENT_TOPOLOGY,
    CompositionStage.HOST_BASELINE,
    CompositionStage.EVIDENCE_REVIEW,
    CompositionStage.EVIDENCE_PUBLICATION,
    CompositionStage.EVIDENCE_VERIFICATION,
    CompositionStage.FINAL_AUDIT_READINESS,
    CompositionStage.ACL_BASELINE,
    CompositionStage.PRE_MUTATION_GATE,
    CompositionStage.ACL_PUBLICATION,
    CompositionStage.REPOSITORY_TRANSACTION,
    CompositionStage.RUNTIME_PUBLICATION,
    CompositionStage.DATABASE_PUBLICATION,
    CompositionStage.ARTIFACT_PUBLICATION,
    CompositionStage.CONFIG_PUBLICATION,
    CompositionStage.ACTIVATION,
)
_SUCCESS = (
    *_PREFIX,
    CompositionStage.FINAL_AUDIT,
    CompositionStage.CUTOVER_SUCCESS,
)
_RECOVERY = (
    *_PREFIX,
    CompositionStage.RECOVERY_INSPECTION,
    CompositionStage.FAILED_CONTAINER_PRESERVATION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
)
_POST_AUDIT_RECOVERY = (
    *_PREFIX,
    CompositionStage.FINAL_AUDIT,
    CompositionStage.RECOVERY_INSPECTION,
    CompositionStage.FAILED_CONTAINER_PRESERVATION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
)
_TRANSITIONS = {
    (left, right)
    for values in (_SUCCESS, _RECOVERY, _POST_AUDIT_RECOVERY)
    for left, right in zip(values, values[1:])
}
_ERROR = "PROJECT_CONTAINER_RECEIPT_CHAIN_INVALID"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ProjectContainerReceiptChainV1:
    state: ReceiptChainState
    receipt_count: int
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_fingerprint: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    authorization_sequence_fingerprint: str = field(repr=False)
    review_fingerprint: str = field(repr=False)
    package_verification_fingerprint: str = field(repr=False)
    acl_baseline_fingerprint: str = field(repr=False)
    pre_mutation_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    activation_fingerprint: str = field(repr=False)
    final_audit_fingerprint: str = field(repr=False)
    recovery_state_fingerprint: str = field(repr=False)
    terminal_receipt_fingerprint: str = field(repr=False)
    chain_fingerprint: str = field(repr=False)
    receipts: tuple[CompositionStageReceiptV1, ...] = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ProjectContainerReceiptChainV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        receipts: tuple[CompositionStageReceiptV1, ...],
        observed_at_epoch: int,
    ) -> ProjectContainerReceiptChainV1:
        try:
            body = _validated_chain(receipts, observed_at_epoch)
        except Exception:
            raise CompositionContractError(_ERROR) from None
        value = object.__new__(cls)
        for name, item in body.items():
            object.__setattr__(value, name, item)
        object.__setattr__(
            value,
            "chain_fingerprint",
            fingerprint(
                "project-container-receipt-chain-v1",
                {
                    **_public_body(body),
                    "stage_sequence": tuple(
                        item.stage.value for item in receipts
                    ),
                },
            ),
        )
        object.__setattr__(value, "receipts", receipts)
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            **_public_body(
                {
                    name: getattr(self, name)
                    for name in _PUBLIC_FIELDS
                }
            ),
            "chain_fingerprint": self.chain_fingerprint,
        }


_PUBLIC_FIELDS = (
    "state",
    "receipt_count",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_fingerprint",
    "operator_fingerprint",
    "authorization_sequence_fingerprint",
    "review_fingerprint",
    "package_verification_fingerprint",
    "acl_baseline_fingerprint",
    "pre_mutation_fingerprint",
    "journal_owner_fingerprint",
    "journal_head_fingerprint",
    "activation_fingerprint",
    "final_audit_fingerprint",
    "recovery_state_fingerprint",
    "terminal_receipt_fingerprint",
)


def _validated_chain(receipts, observed):
    if (
        type(receipts) is not tuple
        or not receipts
        or any(type(item) is not CompositionStageReceiptV1 for item in receipts)
        or type(observed) is not int
        or not 0 <= observed < 2**63
    ):
        raise ValueError
    _require_links_and_transitions(receipts)
    stages = tuple(item.stage for item in receipts)
    if not any(
        stages == candidate[: len(stages)]
        for candidate in (_SUCCESS, _RECOVERY, _POST_AUDIT_RECOVERY)
    ):
        raise ValueError
    _require_binding_and_journal(receipts)
    gate = _stage(receipts, CompositionStage.PRE_MUTATION_GATE)
    if gate is not None and observed >= gate.valid_until_epoch:
        raise ValueError
    state = _state(stages)
    if state is ReceiptChainState.CUTOVER_SUCCEEDED and stages != _SUCCESS:
        raise ValueError
    if (
        state is ReceiptChainState.LEGACY_RECOVERED
        and stages not in {_RECOVERY, _POST_AUDIT_RECOVERY}
    ):
        raise ValueError
    return _chain_body(receipts, state)


def _require_links_and_transitions(receipts) -> None:
    if receipts[0].prior_receipt_fingerprint != UNBOUND_FINGERPRINT:
        raise ValueError
    for prior, current in zip(receipts, receipts[1:]):
        if (
            current.prior_receipt_fingerprint != prior.receipt_fingerprint
            or (prior.stage, current.stage) not in _TRANSITIONS
        ):
            raise ValueError
    if len({item.stage for item in receipts}) != len(receipts):
        raise ValueError


def _require_binding_and_journal(receipts) -> None:
    binding = receipts[0].binding_tuple()
    owners = {
        item.journal_owner_fingerprint
        for item in receipts
        if item.journal_owner_fingerprint != UNBOUND_FINGERPRINT
    }
    if any(item.binding_tuple() != binding for item in receipts) or len(owners) > 1:
        raise ValueError
    prior_head = UNBOUND_FINGERPRINT
    for receipt in receipts:
        if receipt.journal_owner_fingerprint == UNBOUND_FINGERPRINT:
            if (
                receipt.prior_journal_head_fingerprint
                != UNBOUND_FINGERPRINT
            ):
                raise ValueError
            continue
        if receipt.prior_journal_head_fingerprint != prior_head:
            raise ValueError
        prior_head = receipt.journal_head_fingerprint


def _chain_body(receipts, state):
    first = receipts[0]
    last = receipts[-1]
    return {
        "state": state,
        "receipt_count": len(receipts),
        **dict(
            zip(
                (
                    "operation_fingerprint",
                    "profile_fingerprint",
                    "governing_master_fingerprint",
                    "operator_fingerprint",
                    "authorization_sequence_fingerprint",
                ),
                first.binding_tuple(),
                strict=True,
            )
        ),
        "review_fingerprint": _observation(receipts, CompositionStage.EVIDENCE_REVIEW),
        "package_verification_fingerprint": _observation(
            receipts, CompositionStage.EVIDENCE_VERIFICATION
        ),
        "acl_baseline_fingerprint": _observation(receipts, CompositionStage.ACL_BASELINE),
        "pre_mutation_fingerprint": _receipt_fingerprint(
            receipts, CompositionStage.PRE_MUTATION_GATE
        ),
        "journal_owner_fingerprint": last.journal_owner_fingerprint,
        "journal_head_fingerprint": last.journal_head_fingerprint,
        "activation_fingerprint": _observation(receipts, CompositionStage.ACTIVATION),
        "final_audit_fingerprint": _observation(receipts, CompositionStage.FINAL_AUDIT),
        "recovery_state_fingerprint": last.observation_fingerprint,
        "terminal_receipt_fingerprint": last.receipt_fingerprint,
    }


def _state(stages):
    if stages == _SUCCESS:
        return ReceiptChainState.CUTOVER_SUCCEEDED
    if stages in {_RECOVERY, _POST_AUDIT_RECOVERY}:
        return ReceiptChainState.LEGACY_RECOVERED
    if stages[-1] is CompositionStage.FINAL_AUDIT_READINESS:
        return ReceiptChainState.PREFLIGHT_READY
    return ReceiptChainState.IN_PROGRESS


def _stage(receipts, stage):
    return next((item for item in receipts if item.stage is stage), None)


def _observation(receipts, stage):
    value = _stage(receipts, stage)
    return value.observation_fingerprint if value else UNBOUND_FINGERPRINT


def _receipt_fingerprint(receipts, stage):
    value = _stage(receipts, stage)
    return value.receipt_fingerprint if value else UNBOUND_FINGERPRINT


def _public_body(body):
    return {
        name: (
            value.value if isinstance(value, Enum) else value
        )
        for name, value in body.items()
        if name in _PUBLIC_FIELDS
    }
