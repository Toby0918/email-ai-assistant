"""State-bearing bridge to the reviewed cutover transaction composition."""

from dataclasses import dataclass, field

from backend.cutover_composition_contracts import (
    ProjectContainerReceiptChainV1,
    ReceiptChainState,
)
from backend.cutover_transaction_composition import CutoverTransactionComposition
from backend.r2_production_binding import (
    ProductionBindingError,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)
from backend.r2_production_binding._canonical import fingerprint, is_fingerprint

from .adapter_binding import (
    require_adapter_context_v1,
    require_composition_binding_v1,
)


_COMMANDS = {
    ProductionCommandV2.EXECUTE,
    ProductionCommandV2.RESUME,
    ProductionCommandV2.ROLLBACK,
}
_UNBOUND_PLAN = "0" * 64


@dataclass(frozen=True, slots=True, repr=False)
class TransactionAdapterOutcomeV1:
    command: ProductionCommandV2
    chain_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    terminal_receipt_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    remaining_reverse_plan_fingerprint: str = field(repr=False)
    provider_attempts: int
    mutations: int


class TransactionProductionAdapterV1:
    """One stateful slot for execute, resume, and rollback."""

    __slots__ = ("_binding", "_composition")

    def __init__(self, *args, **kwargs):
        raise TypeError("TransactionProductionAdapterV1 requires create()")

    @classmethod
    def create(cls, *, binding, composition):
        try:
            if type(composition) is not CutoverTransactionComposition:
                raise ProductionBindingError()
            require_composition_binding_v1(binding, composition._binding)
            value = object.__new__(cls)
            value._binding = binding
            value._composition = composition
            return value
        except ProductionBindingError:
            raise
        except Exception:
            raise ProductionBindingError() from None

    def invoke(
        self,
        *,
        binding,
        claim,
        journal_head_fingerprint,
        transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint,
    ):
        require_adapter_context_v1(
            binding,
            claim,
            self._composition._binding,
            _COMMANDS,
        )
        values = _require_transaction_inputs(
            self._binding,
            binding,
            claim,
            journal_head_fingerprint,
            transition_instance_fingerprint,
            remaining_reverse_plan_fingerprint,
        )
        chain = _invoke_composition(self._composition, claim.command)
        _require_transaction_chain(
            self._composition,
            claim,
            chain,
        )
        return TransactionAdapterOutcomeV1(
            claim.command,
            chain.chain_fingerprint,
            chain.journal_head_fingerprint,
            chain.terminal_receipt_fingerprint,
            values[1],
            values[2],
            0,
            1,
        )


def _invoke_composition(composition, command):
    return {
        ProductionCommandV2.EXECUTE: composition.execute,
        ProductionCommandV2.RESUME: composition.resume,
        ProductionCommandV2.ROLLBACK: composition.rollback,
    }[command]()


def _require_transaction_inputs(
    reviewed_binding, binding, claim, head, transition, plan
):
    values = (head, transition, plan)
    rollback = claim.command is ProductionCommandV2.ROLLBACK
    if (
        binding is not reviewed_binding
        or not all(is_fingerprint(value) for value in values)
        or claim.prior_journal_head_fingerprint != head
        or (rollback and plan == _UNBOUND_PLAN)
        or (not rollback and plan != _UNBOUND_PLAN)
        or claim.action_fingerprint
        != _action_fingerprint(binding, claim.command, *values)
    ):
        raise ProductionBindingError()
    return values


def _require_transaction_chain(composition, claim, chain):
    expected_states = {
        ProductionCommandV2.EXECUTE: {ReceiptChainState.CUTOVER_SUCCEEDED},
        ProductionCommandV2.RESUME: {
            ReceiptChainState.CUTOVER_SUCCEEDED,
            ReceiptChainState.LEGACY_RECOVERED,
        },
        ProductionCommandV2.ROLLBACK: {ReceiptChainState.LEGACY_RECOVERED},
    }
    if (
        type(chain) is not ProjectContainerReceiptChainV1
        or chain.state not in expected_states[claim.command]
        or _chain_binding_tuple(chain)
        != _composition_binding_tuple(composition._binding)
        or chain.journal_owner_fingerprint != claim.journal_owner_fingerprint
        or any(item.provider_attempts != 0 for item in chain.receipts)
    ):
        raise ProductionBindingError()


def _action_fingerprint(binding, command, head, transition, plan):
    subject = fingerprint(
        "r2-transaction-action-subject-v2",
        {
            "journal_head_fingerprint": head,
            "transition_instance_fingerprint": transition,
            "remaining_reverse_plan_fingerprint": plan,
        },
    )
    return production_action_fingerprint_v2(
        binding,
        command,
        subject_fingerprint=subject,
    )


def _composition_binding_tuple(binding):
    return (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )


def _chain_binding_tuple(chain):
    return (
        chain.operation_fingerprint,
        chain.profile_fingerprint,
        chain.governing_master_fingerprint,
        chain.operator_fingerprint,
        chain.authorization_sequence_fingerprint,
    )
