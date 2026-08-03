"""Synthetic-only binder for the transaction process seam."""

from __future__ import annotations

from backend.cutover_composition_contracts import (
    ApprovedCutoverBindingV1,
    UNBOUND_FINGERPRINT,
)
from backend.cutover_composition_contracts.canonical import is_fingerprint
from backend.cutover_contracts import CutoverProfileV1

from .contracts import (
    TRANSACTION_VERBS,
    TransactionProcessStatus,
    result,
)
from .entry import run_authorization_gate
from .production_v2 import (
    UNBOUND_REVERSE_PLAN_V2,
    _create_synthetic_roles_v2,
    complete_transaction_action_v2,
    run_transaction_production_v2,
)
from backend.r2_production_binding import ApprovedCutoverBindingV2, ProductionCommandV2
from backend.r2_production_binding.role_binding import _synthetic_bound_callable_v2
from backend.r2_transaction_journal_v2 import R2JournalGenesisV2


class SyntheticTransactionProcess:
    __slots__ = (
        "_actions",
        "_binding",
        "_claimed_crash",
        "_claimed_envelopes",
        "_execution_key",
        "_head",
        "_locked",
        "_now",
        "_operation",
        "_owner",
        "_plan",
        "_profile",
        "_recovery_key",
        "action_acquisitions",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticTransactionProcess requires create()")

    @classmethod
    def create(cls, **values) -> SyntheticTransactionProcess:
        _require_context(values)
        process = object.__new__(cls)
        for target, source in (
            ("_profile", "profile"),
            ("_binding", "binding"),
            ("_operation", "operation_fingerprint"),
            ("_owner", "journal_owner_fingerprint"),
            ("_head", "current_journal_head"),
            ("_plan", "remaining_reverse_plan"),
            ("_now", "observed_at_epoch"),
            ("_execution_key", "execution_public_key"),
            ("_recovery_key", "recovery_public_key"),
            ("_locked", "real_locked"),
        ):
            setattr(process, target, values[source])
        process._actions = {
            name: values[name] for name in TRANSACTION_VERBS
        }
        process._claimed_envelopes = set()
        process._claimed_crash = set()
        process.action_acquisitions = 0
        return process

    def run(self, *, argv: object, terminal: object):
        authorized = run_authorization_gate(
            argv=argv,
            terminal=terminal,
            profile=self._profile,
            operation_fingerprint=self._operation,
            execution_public_key=self._execution_key,
            recovery_public_key=self._recovery_key,
            observed_at_epoch=self._now,
            claim_nonce=self._claim_envelope,
            claim_crash_nonce=self._claim_crash_nonce,
            expected_context=self._expected_context,
        )
        if authorized.status is not TransactionProcessStatus.BLOCKED_NO_APPROVED_COMMAND:
            return authorized
        if self._locked:
            return authorized
        return self._perform(argv[0])

    def _expected_context(self, verb, context):
        crash_nonce = context.get("crash_nonce")
        expected = {
            "context_type": "R2TransactionAuthorizationContextV1",
            "approved_binding_fingerprint": self._binding.binding_fingerprint,
            "journal_owner_fingerprint": self._owner,
            "journal_head_fingerprint": self._head(),
            "remaining_plan_fingerprint": (
                self._plan() if verb == "rollback" else UNBOUND_FINGERPRINT
            ),
            "boundary_epoch": self._now(),
            "crash_nonce": crash_nonce,
        }
        if not is_fingerprint(crash_nonce) or context != expected:
            raise ValueError
        return expected

    def _perform(self, verb):
        self.action_acquisitions += 1
        try:
            completed = self._actions[verb]()
        except Exception:
            return result(TransactionProcessStatus.BLOCKED_ACTION)
        status = (
            TransactionProcessStatus.ACTION_COMPLETE
            if completed == 1
            else TransactionProcessStatus.BLOCKED_ACTION
        )
        return result(status)

    def _claim_envelope(self, nonce):
        if nonce in self._claimed_envelopes:
            return False
        self._claimed_envelopes.add(nonce)
        return True

    def _claim_crash_nonce(self, nonce):
        if nonce in self._claimed_crash:
            return False
        self._claimed_crash.add(nonce)
        return True


def _require_context(values) -> None:
    expected = {
        "profile",
        "binding",
        "operation_fingerprint",
        "journal_owner_fingerprint",
        "current_journal_head",
        "remaining_reverse_plan",
        "observed_at_epoch",
        "execution_public_key",
        "recovery_public_key",
        "execute",
        "resume",
        "rollback",
        "real_locked",
    }
    if type(values) is not dict or set(values) != expected:
        raise ValueError("R2_TRANSACTION_SYNTHETIC_BINDING_INVALID")
    profile = values["profile"]
    binding = values["binding"]
    if (
        type(profile) is not CutoverProfileV1
        or type(binding) is not ApprovedCutoverBindingV1
        or binding.profile_fingerprint != profile.profile_fingerprint
        or binding.operation_fingerprint != values["operation_fingerprint"]
        or not is_fingerprint(values["journal_owner_fingerprint"])
        or type(values["execution_public_key"]) is not bytes
        or len(values["execution_public_key"]) != 32
        or type(values["recovery_public_key"]) is not bytes
        or len(values["recovery_public_key"]) != 32
        or type(values["real_locked"]) is not bool
        or not all(
            callable(values[name])
            for name in (
                "current_journal_head",
                "remaining_reverse_plan",
                "observed_at_epoch",
                "execute",
                "resume",
                "rollback",
            )
        )
    ):
        raise ValueError("R2_TRANSACTION_SYNTHETIC_BINDING_INVALID")


class SyntheticTransactionProductionV2:
    __slots__ = (
        "_actions",
        "_binding",
        "_genesis",
        "_invoked",
        "_now",
        "_plan",
        "_roles",
        "_transition",
        "total_action_acquisitions",
    )

    def __init__(self, *args, **kwargs):
        raise TypeError("SyntheticTransactionProductionV2 requires create()")

    @classmethod
    def create(cls, **values):
        _require_v2_context(values)
        process = object.__new__(cls)
        process._binding = values["binding"]
        process._genesis = values["reconstructed_genesis"]
        process._transition = values["transition_instance_fingerprint"]
        process._plan = values["remaining_reverse_plan_fingerprint"]
        process._now = values["observed_at_epoch"]
        process._actions = {
            command: values[command.value]
            for command in (
                ProductionCommandV2.EXECUTE,
                ProductionCommandV2.RESUME,
                ProductionCommandV2.ROLLBACK,
            )
        }
        process._invoked = False
        process.total_action_acquisitions = 0
        process._roles = _create_synthetic_roles_v2(tuple(
            _synthetic_bound_callable_v2(
                command, _action_callback(process, command), process._binding
            )
            for command in process._actions
        ))
        return process

    def run(self, *, argv, terminal):
        command = (
            ProductionCommandV2(argv[0])
            if type(argv) is tuple and len(argv) == 1 and argv[0] in {"execute", "resume", "rollback"}
            else None
        )
        plan = (
            self._plan
            if command is ProductionCommandV2.ROLLBACK
            else UNBOUND_REVERSE_PLAN_V2
        )
        return run_transaction_production_v2(
            argv=argv,
            terminal=terminal,
            binding=self._binding,
            roles=self._roles,
            durable_claims=(self._genesis.authority_claim,),
            current_journal_head_fingerprint=self._genesis.head_fingerprint,
            transition_instance_fingerprint=self._transition,
            remaining_reverse_plan_fingerprint=plan,
            observed_at_epoch=self._now,
        )

    def _perform(self, command, binding, claim, head, transition, plan):
        if self._invoked or claim.command is not command:
            raise ValueError("R2_TRANSACTION_V2_SINGLE_ACTION_INVALID")
        self._invoked = True
        self.total_action_acquisitions += 1
        if self._actions[command]() != 1:
            raise ValueError("R2_TRANSACTION_V2_ACTION_FAILED")
        return complete_transaction_action_v2(
            binding,
            claim,
            head,
            transition,
            plan,
        )


def _action_callback(process, command):
    return lambda binding, claim, head, transition, plan: process._perform(
        command, binding, claim, head, transition, plan
    )


def _require_v2_context(values):
    expected = {
        "binding",
        "reconstructed_genesis",
        "transition_instance_fingerprint",
        "remaining_reverse_plan_fingerprint",
        "observed_at_epoch",
        "execute",
        "resume",
        "rollback",
    }
    if (
        type(values) is not dict
        or set(values) != expected
        or type(values["binding"]) is not ApprovedCutoverBindingV2
        or type(values["reconstructed_genesis"]) is not R2JournalGenesisV2
        or values["reconstructed_genesis"].binding_fingerprint
        != values["binding"].binding_fingerprint
        or not is_fingerprint(values["transition_instance_fingerprint"])
        or not is_fingerprint(values["remaining_reverse_plan_fingerprint"])
        or not all(
            callable(values[name])
            for name in ("observed_at_epoch", "execute", "resume", "rollback")
        )
    ):
        raise ValueError("R2_TRANSACTION_SYNTHETIC_V2_BINDING_INVALID")
