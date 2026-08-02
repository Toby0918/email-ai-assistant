"""Exact one-authority, one-action V2 transaction dispatcher."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum

from backend.r2_operator_process import verify_production_authority_v2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    ProductionCommandV2,
)

from .contracts import TRANSACTION_ACKNOWLEDGEMENT
from ._production_v2_canonical import (
    UNBOUND_REVERSE_PLAN_V2,
    fingerprint,
    is_fingerprint,
    transaction_action_fingerprint_v2,
)


TRANSACTION_PRODUCTION_VERBS_V2 = {
    "execute": ProductionCommandV2.EXECUTE,
    "resume": ProductionCommandV2.RESUME,
    "rollback": ProductionCommandV2.ROLLBACK,
}


class TransactionProductionStatusV2(str, Enum):
    ACTION_COMPLETE = "TRANSACTION_ACTION_COMPLETE"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_ENVELOPE = "BLOCKED_ENVELOPE"
    BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
    BLOCKED_ACTION = "BLOCKED_ACTION"
    DORMANT_NO_EXTERNAL_ISSUER = "DORMANT_NO_EXTERNAL_ISSUER"


@dataclass(frozen=True, slots=True)
class TransactionProductionResultV2:
    status: TransactionProductionStatusV2
    accepted: int
    rejected: int
    mutations: int
    command: object = field(default=None, repr=False)
    prior_journal_head_fingerprint: str = field(default="", repr=False)
    action_completion_fingerprint: str = field(default="", repr=False)

    def counts(self):
        return self.accepted, self.rejected, self.mutations

    def to_mapping(self):
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "mutations": self.mutations,
            "action_completion_fingerprint": self.action_completion_fingerprint,
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


@dataclass(frozen=True, slots=True, repr=False)
class TransactionProductionRolesV2:
    execute: object = field(repr=False)
    resume: object = field(repr=False)
    rollback: object = field(repr=False)

    def __post_init__(self):
        if not all(callable(value) for value in self._values()):
            raise TypeError("R2_TRANSACTION_PRODUCTION_ROLES_INVALID")

    def select(self, command):
        if type(command) is not ProductionCommandV2:
            raise TypeError("R2_TRANSACTION_PRODUCTION_ROLES_INVALID")
        return {
            ProductionCommandV2.EXECUTE: self.execute,
            ProductionCommandV2.RESUME: self.resume,
            ProductionCommandV2.ROLLBACK: self.rollback,
        }[command]

    def _values(self):
        return self.execute, self.resume, self.rollback


def run_transaction_production_v2(
    *,
    argv,
    terminal,
    binding,
    roles,
    durable_claims,
    current_journal_head_fingerprint,
    transition_instance_fingerprint,
    remaining_reverse_plan_fingerprint,
    observed_at_epoch,
):
    if not _valid_argv(argv):
        return _blocked(TransactionProductionStatusV2.BLOCKED_COMMAND)
    ingress = _read_ingress(terminal)
    if type(ingress) is TransactionProductionStatusV2:
        return _blocked(ingress)
    command = TRANSACTION_PRODUCTION_VERBS_V2[argv[0]]
    try:
        action = transaction_action_fingerprint_v2(
            binding,
            command,
            journal_head_fingerprint=current_journal_head_fingerprint,
            transition_instance_fingerprint=transition_instance_fingerprint,
            remaining_reverse_plan_fingerprint=remaining_reverse_plan_fingerprint,
        )
        claim = verify_production_authority_v2(
            ingress,
            binding=binding,
            expected_command=command,
            durable_claims=durable_claims,
            expected_prior_journal_head_fingerprint=current_journal_head_fingerprint,
            observed_at_epoch=observed_at_epoch(),
            expected_action_fingerprint=action,
        )
    except Exception:
        return _blocked(TransactionProductionStatusV2.BLOCKED_AUTHORITY)
    return _invoke_action(
        binding,
        roles,
        claim,
        current_journal_head_fingerprint,
        transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint,
    )


def dormant_transaction_production_v2(*, argv):
    if not _valid_argv(argv):
        return _blocked(TransactionProductionStatusV2.BLOCKED_COMMAND)
    return TransactionProductionResultV2(
        TransactionProductionStatusV2.DORMANT_NO_EXTERNAL_ISSUER,
        0,
        0,
        0,
    )


def main(*, argv=None):
    arguments = tuple(sys.argv[1:]) if argv is None else argv
    result = dormant_transaction_production_v2(argv=arguments)
    sys.stdout.write(
        f"{result.status.value} accepted={result.accepted} "
        f"rejected={result.rejected} mutations={result.mutations}\n"
    )
    sys.stdout.flush()
    return 2 if result.status is TransactionProductionStatusV2.BLOCKED_COMMAND else 0


def complete_transaction_action_v2(
    binding,
    claim,
    head,
    transition,
    plan,
):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(claim) is not DurableAuthorityClaimV2
        or claim.binding_fingerprint != binding.binding_fingerprint
        or claim.prior_journal_head_fingerprint != head
        or not is_fingerprint(transition)
        or not is_fingerprint(plan)
    ):
        raise TypeError("R2_TRANSACTION_ACTION_COMPLETION_INVALID")
    values = {
        "binding_fingerprint": binding.binding_fingerprint,
        "command": claim.command.value,
        "claim_fingerprint": claim.claim_fingerprint,
        "prior_journal_head_fingerprint": head,
        "transition_instance_fingerprint": transition,
        "remaining_reverse_plan_fingerprint": plan,
        "mutations": 1,
    }
    completion = fingerprint("r2-transaction-action-completion-v2", values)
    return TransactionActionCompletionV2(
        binding.binding_fingerprint,
        claim.command,
        claim.claim_fingerprint,
        head,
        transition,
        plan,
        completion,
        1,
    )


def _invoke_action(binding, roles, claim, head, transition, plan):
    try:
        if type(roles) is not TransactionProductionRolesV2:
            raise TypeError
        completion = roles.select(claim.command)(
            binding, claim, head, transition, plan
        )
        if (
            type(completion) is not TransactionActionCompletionV2
            or completion.binding_fingerprint != binding.binding_fingerprint
            or completion.command is not claim.command
            or completion.claim_fingerprint != claim.claim_fingerprint
            or completion.prior_journal_head_fingerprint != head
            or completion.transition_instance_fingerprint != transition
            or completion.remaining_reverse_plan_fingerprint != plan
            or completion.mutations != 1
        ):
            raise TypeError
    except Exception:
        return _blocked(TransactionProductionStatusV2.BLOCKED_ACTION)
    return TransactionProductionResultV2(
        TransactionProductionStatusV2.ACTION_COMPLETE,
        1,
        0,
        1,
        claim.command,
        head,
        completion.completion_fingerprint,
    )


def _read_ingress(terminal):
    try:
        if terminal.tty_state() != (True, True, True):
            return TransactionProductionStatusV2.BLOCKED_TTY
        if terminal.read_acknowledgement() != TRANSACTION_ACKNOWLEDGEMENT:
            return TransactionProductionStatusV2.BLOCKED_ACKNOWLEDGEMENT
        envelope = terminal.read_hidden_envelope(65_536)
        if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
            return TransactionProductionStatusV2.BLOCKED_ENVELOPE
        return envelope
    except Exception:
        return TransactionProductionStatusV2.BLOCKED_ENVELOPE


def _valid_argv(argv):
    return (
        type(argv) is tuple
        and len(argv) == 1
        and type(argv[0]) is str
        and argv[0] in TRANSACTION_PRODUCTION_VERBS_V2
    )


def _blocked(status):
    return TransactionProductionResultV2(status, 0, 1, 0)
