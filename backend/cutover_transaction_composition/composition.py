"""Fixed journal-driven cutover transaction composition."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .contracts_bridge import (
    CompositionBindingV1,
    CompositionContractError,
    CompositionStage,
    CompositionStageReceiptV1,
    ProjectContainerReceiptChainV1,
    ReceiptChainState,
)
from .roles import CutoverTransactionRolesV1


_ERROR = "CUTOVER_TRANSACTION_COMPOSITION_REJECTED"
@dataclass(frozen=True, slots=True, repr=False)
class JournalOwnerV1:
    owner_fingerprint: str = field(repr=False)
    verify_head: Callable[[object], object] = field(repr=False)
    claim_gate: Callable[[object], object] = field(repr=False)
    now_epoch: Callable[[], object] = field(repr=False)


class CutoverTransactionComposition:
    """One single-owner execute, resume, or rollback action."""

    __slots__ = (
        "_binding",
        "_roles",
        "_journal_owner",
        "_initial",
        "_observed_at",
        "_state",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "CutoverTransactionComposition has no executable backend constructor"
        )

    def execute(self) -> ProjectContainerReceiptChainV1:
        self._claim()
        try:
            self._require_authorization_fresh()
            if (
                self._initial.state is not ReceiptChainState.PREFLIGHT_READY
                or self._initial.receipts[-1].stage
                is not CompositionStage.FINAL_AUDIT_READINESS
            ):
                raise ValueError
            receipts = self._append_roles(
                self._initial.receipts,
                self._execution_steps(),
            )
            self._require_authorization_fresh()
            prior = receipts[-1]
            success = self._roles.cutover_success(prior)
            _require_receipt(
                self._binding,
                prior,
                success,
                CompositionStage.CUTOVER_SUCCESS,
            )
            self._verify_journal(success)
            receipts = (*receipts, success)
            return self._chain(receipts)
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def rollback(self) -> ProjectContainerReceiptChainV1:
        self._claim()
        try:
            self._require_authorization_fresh()
            if self._initial.receipts[-1].stage not in {
                CompositionStage.ACTIVATION,
                CompositionStage.FINAL_AUDIT,
            }:
                raise ValueError
            self._verify_existing_head()
            receipts = self._append_roles(
                self._initial.receipts,
                self._recovery_steps(),
            )
            return self._chain(receipts)
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def resume(self) -> ProjectContainerReceiptChainV1:
        self._claim()
        try:
            self._require_authorization_fresh()
            self._verify_existing_head()
            resumed = self._roles.resume_committed(self._initial)
            _require_continuation(self._initial, resumed)
            self._require_authorization_fresh()
            for receipt in resumed.receipts[
                self._initial.receipt_count :
            ]:
                self._verify_journal(receipt)
            return resumed
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def _append_roles(self, receipts, steps):
        current = receipts
        for role, stage in steps:
            self._require_authorization_fresh()
            prior = current[-1]
            receipt = role(prior)
            _require_receipt(self._binding, prior, receipt, stage)
            if stage is CompositionStage.PRE_MUTATION_GATE:
                self._claim_pre_mutation_gate(receipt)
            elif stage is not CompositionStage.ACL_BASELINE:
                self._verify_journal(receipt)
            current = (*current, receipt)
        return current

    def _execution_steps(self):
        return (
            (self._roles.acl_baseline, CompositionStage.ACL_BASELINE),
            (
                self._roles.pre_mutation_gate,
                CompositionStage.PRE_MUTATION_GATE,
            ),
            (self._roles.acl_publication, CompositionStage.ACL_PUBLICATION),
            (
                self._roles.repository_transaction,
                CompositionStage.REPOSITORY_TRANSACTION,
            ),
            (
                self._roles.runtime_publication,
                CompositionStage.RUNTIME_PUBLICATION,
            ),
            (
                self._roles.database_publication,
                CompositionStage.DATABASE_PUBLICATION,
            ),
            (
                self._roles.artifact_publication,
                CompositionStage.ARTIFACT_PUBLICATION,
            ),
            (
                self._roles.config_publication,
                CompositionStage.CONFIG_PUBLICATION,
            ),
            (self._roles.activation, CompositionStage.ACTIVATION),
            (self._roles.final_audit, CompositionStage.FINAL_AUDIT),
        )

    def _recovery_steps(self):
        return (
            (
                self._roles.recovery_inspection,
                CompositionStage.RECOVERY_INSPECTION,
            ),
            (
                self._roles.failed_container_preservation,
                CompositionStage.FAILED_CONTAINER_PRESERVATION,
            ),
            (
                self._roles.rollback_restoration,
                CompositionStage.ROLLBACK_RESTORATION,
            ),
            (self._roles.legacy_health, CompositionStage.LEGACY_HEALTH),
        )

    def _verify_existing_head(self) -> None:
        receipt = self._initial.receipts[-1]
        self._verify_journal(receipt)

    def _verify_journal(self, receipt) -> None:
        if (
            receipt.journal_owner_fingerprint
            != self._journal_owner.owner_fingerprint
            or self._journal_owner.verify_head(receipt)
            != receipt.journal_head_fingerprint
        ):
            raise ValueError

    def _claim_pre_mutation_gate(self, receipt) -> None:
        now = self._require_authorization_fresh()
        if (
            now >= receipt.valid_until_epoch
            or self._journal_owner.claim_gate(receipt)
            != receipt.receipt_fingerprint
        ):
            raise ValueError

    def _require_authorization_fresh(self) -> int:
        now = self._journal_owner.now_epoch()
        if (
            type(now) is not int
            or not 0 <= now < self._binding.authorization_expires_at_epoch
        ):
            raise ValueError
        return now

    def _chain(self, receipts):
        return ProjectContainerReceiptChainV1.create(
            receipts=receipts,
            observed_at_epoch=self._observed_at,
        )

    def _claim(self) -> None:
        if not self._state.claim():
            raise CompositionContractError(_ERROR)


def _require_receipt(binding, prior, receipt, stage) -> None:
    if (
        type(receipt) is not CompositionStageReceiptV1
        or receipt.stage is not stage
        or receipt.prior_receipt_fingerprint != prior.receipt_fingerprint
        or receipt.prior_journal_head_fingerprint
        != prior.journal_head_fingerprint
        or receipt.binding_tuple() != _binding_tuple(binding)
    ):
        raise ValueError


def _require_continuation(initial, resumed) -> None:
    if (
        type(resumed) is not ProjectContainerReceiptChainV1
        or resumed.state
        not in {
            ReceiptChainState.CUTOVER_SUCCEEDED,
            ReceiptChainState.LEGACY_RECOVERED,
        }
        or resumed.receipt_count <= initial.receipt_count
        or resumed.receipts[: initial.receipt_count] != initial.receipts
        or _chain_binding(resumed) != _chain_binding(initial)
    ):
        raise ValueError


def _binding_tuple(binding):
    return (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )


def _chain_binding(chain):
    return (
        chain.operation_fingerprint,
        chain.profile_fingerprint,
        chain.governing_master_fingerprint,
        chain.operator_fingerprint,
        chain.authorization_sequence_fingerprint,
    )
