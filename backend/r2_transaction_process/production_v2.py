"""Dormant transaction root plus pure V3 completion values."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ExecutionConfirmationClaimV1,
    ProductionCommandV2,
)
from backend.r2_production_binding.catalog import (
    OperatorSurfaceV2,
    executable_verb_map_v2,
)

from ._production_v2_canonical import (
    fingerprint,
    is_fingerprint,
    transaction_action_fingerprint_v2,
)


TRANSACTION_PRODUCTION_VERBS_V2 = executable_verb_map_v2(
    OperatorSurfaceV2.TRANSACTION
)


class TransactionProductionStatusV2(str, Enum):
    ACTION_COMPLETE = "TRANSACTION_ACTION_COMPLETE"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_EXECUTION_CONFIRMATION = "BLOCKED_EXECUTION_CONFIRMATION"
    BLOCKED_FINGERPRINT = "BLOCKED_FINGERPRINT"
    BLOCKED_REPLAY = "BLOCKED_REPLAY"
    BLOCKED_ACTION = "BLOCKED_ACTION"
    DORMANT_NO_ISSUE39_APPROVAL = "DORMANT_NO_ISSUE39_APPROVAL"


@dataclass(frozen=True, slots=True)
class TransactionProductionResultV2:
    status: TransactionProductionStatusV2
    accepted: int
    rejected: int
    mutations: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.mutations

    def to_mapping(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "mutations": self.mutations,
        }


@dataclass(frozen=True, slots=True, repr=False)
class TransactionActionCompletionV2:
    binding_fingerprint: str = field(repr=False)
    command: ProductionCommandV2
    claim_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    remaining_reverse_plan_fingerprint: str = field(repr=False)
    completion_fingerprint: str = field(repr=False)
    mutations: int


def run_transaction_production_v2(
    *,
    argv,
    terminal=None,
    binding=None,
    adapter=None,
    execution_confirmation_claims=None,
    current_journal_head_fingerprint=None,
    transition_instance_fingerprint=None,
    remaining_reverse_plan_fingerprint=None,
    observed_at_epoch=None,
):
    """Return before inspecting every argument or acquiring a capability."""

    return _dormant()


def dormant_transaction_production_v2(*, argv):
    """Return the only Issue #110 production state without reading ``argv``."""

    return _dormant()


def main(*, argv=None, bootstrap=None) -> int:
    """Emit one content-free line; neither argument is inspected."""

    result = _dormant()
    sys.stdout.write(
        f"{result.status.value} accepted=0 rejected=0 mutations=0\n"
    )
    sys.stdout.flush()
    return 0


def complete_transaction_action_v2(binding, claim, head, transition, plan):
    """Create a pure completion only after an exact latent V3 claim."""

    try:
        _require_completion_inputs(binding, claim, head, transition, plan)
        values = {
            "binding_fingerprint": binding.binding_fingerprint,
            "command": claim.command.value,
            "claim_fingerprint": claim.claim_fingerprint,
            "prior_journal_head_fingerprint": head,
            "transition_instance_fingerprint": transition,
            "remaining_reverse_plan_fingerprint": plan,
            "mutations": 1,
        }
        return TransactionActionCompletionV2(
            binding.binding_fingerprint,
            claim.command,
            claim.claim_fingerprint,
            head,
            transition,
            plan,
            fingerprint("r2-transaction-action-completion-v2", values),
            1,
        )
    except Exception:
        raise TypeError("R2_TRANSACTION_ACTION_COMPLETION_INVALID") from None


def _require_completion_inputs(binding, claim, head, transition, plan):
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(claim) is not ExecutionConfirmationClaimV1
        or claim.production_binding_fingerprint != binding.binding_fingerprint
        or claim.prior_journal_head_fingerprint != head
        or claim.transition_instance_fingerprint != transition
        or claim.remaining_reverse_plan_fingerprint != plan
        or not all(is_fingerprint(value) for value in (head, transition, plan))
        or claim.action_fingerprint
        != transaction_action_fingerprint_v2(
            binding,
            claim.command,
            journal_head_fingerprint=head,
            transition_instance_fingerprint=transition,
            remaining_reverse_plan_fingerprint=plan,
        )
    ):
        raise TypeError


def _dormant() -> TransactionProductionResultV2:
    return TransactionProductionResultV2(
        TransactionProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        0,
        0,
        0,
    )
