"""Synthetic-only binder for the transaction process seam."""

from __future__ import annotations

from backend.cutover_composition_contracts import (
    ApprovedCutoverBindingV1,
    UNBOUND_FINGERPRINT,
)
from backend.cutover_composition_contracts.canonical import is_fingerprint
from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    RecoveryAuthorizationV1,
)
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeReplay,
    decode_authorization_envelope_context,
    verify_authorization_envelope,
)

from .contracts import (
    TRANSACTION_ACKNOWLEDGEMENT,
    TRANSACTION_VERBS,
    TransactionProcessStatus,
    result,
)


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
        if (
            type(argv) is not tuple
            or len(argv) != 1
            or argv[0] not in TRANSACTION_VERBS
        ):
            return result(TransactionProcessStatus.BLOCKED_COMMAND)
        if _tty_state(terminal) != (True, True, True):
            return result(TransactionProcessStatus.BLOCKED_TTY)
        try:
            acknowledgement = terminal.read_acknowledgement()
        except Exception:
            return result(TransactionProcessStatus.BLOCKED_ACKNOWLEDGEMENT)
        if acknowledgement != TRANSACTION_ACKNOWLEDGEMENT:
            return result(TransactionProcessStatus.BLOCKED_ACKNOWLEDGEMENT)
        return self._authorize(argv[0], terminal)

    def _authorize(self, verb, terminal):
        try:
            envelope = terminal.read_hidden_envelope(65_536)
            if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
                return result(TransactionProcessStatus.BLOCKED_ENVELOPE)
            context = decode_authorization_envelope_context(envelope)
            expected = self._expected_context(verb, context)
            domain, kind, operation, key = self._authorization_spec(verb)
            verify_authorization_envelope(
                envelope,
                expected_domain=domain,
                verification_public_key=key,
                profile=self._profile,
                operation_fingerprint=self._operation,
                expected_phase=verb,
                observed_at_epoch=self._now(),
                claim_nonce=self._claim_envelope,
                authorization_type=kind,
                expected_operation=operation,
                expected_context=expected,
            )
            if not self._claim_crash_nonce(context["crash_nonce"]):
                raise AuthorizationEnvelopeReplay
        except AuthorizationEnvelopeReplay:
            return result(TransactionProcessStatus.BLOCKED_REPLAY)
        except Exception:
            return result(TransactionProcessStatus.BLOCKED_AUTHORIZATION)
        if self._locked:
            return result(TransactionProcessStatus.BLOCKED_NO_APPROVED_COMMAND)
        return self._perform(verb)

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

    def _authorization_spec(self, verb):
        if verb == "rollback":
            return (
                AuthorizationEnvelopeDomain.RECOVERY,
                RecoveryAuthorizationV1,
                "recovery",
                self._recovery_key,
            )
        return (
            AuthorizationEnvelopeDomain.EXECUTION,
            CutoverExecutionAuthorizationV1,
            "cutover_execution",
            self._execution_key,
        )

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


def _tty_state(terminal):
    try:
        state = terminal.tty_state()
    except Exception:
        return None
    return state if type(state) is tuple and len(state) == 3 else None


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
