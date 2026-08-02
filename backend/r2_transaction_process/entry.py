"""Production transaction entry remains locked before Issue #39."""

from __future__ import annotations

import sys

from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    RecoveryAuthorizationV1,
)
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeReplay,
    decode_authorization_envelope_context,
    verify_authorization_envelope,
)
from backend.r2_operator_process.dormant_context import (
    DORMANT_PROFILE,
    EXECUTION_PUBLIC_KEY,
    RECOVERY_PUBLIC_KEY,
    TRANSACTION_OPERATION,
    claim_crash_nonce,
    claim_envelope_nonce,
    expected_transaction_context,
    observed_at_epoch,
)

from .contracts import (
    TRANSACTION_ACKNOWLEDGEMENT,
    TRANSACTION_VERBS,
    TransactionProcessStatus,
    result,
)
from .terminal import SystemTerminal


def main() -> int:
    value = run_authorization_gate(
        argv=tuple(sys.argv[1:]),
        terminal=SystemTerminal(),
        profile=DORMANT_PROFILE,
        operation_fingerprint=TRANSACTION_OPERATION,
        execution_public_key=EXECUTION_PUBLIC_KEY,
        recovery_public_key=RECOVERY_PUBLIC_KEY,
        observed_at_epoch=observed_at_epoch,
        claim_nonce=claim_envelope_nonce,
        claim_crash_nonce=claim_crash_nonce,
        expected_context=expected_transaction_context,
    )
    return _write(value, _exit_code(value.status))


def run_authorization_gate(
    *,
    argv,
    terminal,
    profile=None,
    operation_fingerprint=None,
    execution_public_key=None,
    recovery_public_key=None,
    observed_at_epoch=None,
    claim_nonce=None,
    claim_crash_nonce=None,
    expected_context=None,
):
    if (
        type(argv) is not tuple
        or len(argv) != 1
        or type(argv[0]) is not str
        or argv[0] not in TRANSACTION_VERBS
    ):
        return result(TransactionProcessStatus.BLOCKED_COMMAND)
    ingress = _read_ingress(terminal)
    if type(ingress) is TransactionProcessStatus:
        return result(ingress)
    return _verify_locked_authorization(
        argv[0],
        ingress,
        profile,
        operation_fingerprint,
        execution_public_key,
        recovery_public_key,
        observed_at_epoch,
        claim_nonce,
        claim_crash_nonce,
        expected_context,
    )


def _read_ingress(terminal):
    try:
        tty_state = terminal.tty_state()
    except Exception:
        tty_state = None
    if tty_state != (True, True, True):
        return TransactionProcessStatus.BLOCKED_TTY
    try:
        acknowledgement = terminal.read_acknowledgement()
    except Exception:
        acknowledgement = None
    if acknowledgement != TRANSACTION_ACKNOWLEDGEMENT:
        return TransactionProcessStatus.BLOCKED_ACKNOWLEDGEMENT
    try:
        envelope = terminal.read_hidden_envelope(65_536)
        if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
            return TransactionProcessStatus.BLOCKED_ENVELOPE
        return envelope
    except Exception:
        return TransactionProcessStatus.BLOCKED_ENVELOPE


def _verify_locked_authorization(
    verb,
    envelope,
    profile,
    operation_fingerprint,
    execution_public_key,
    recovery_public_key,
    observed_at_epoch,
    claim_nonce,
    claim_crash_nonce,
    expected_context,
):
    try:
        if None in (
            profile,
            operation_fingerprint,
            execution_public_key,
            recovery_public_key,
            observed_at_epoch,
            claim_nonce,
            claim_crash_nonce,
            expected_context,
        ):
            raise ValueError
        context = decode_authorization_envelope_context(envelope)
        exact_context = expected_context(verb, context)
        domain, kind, operation, key = _authorization_spec(
            verb, execution_public_key, recovery_public_key
        )
        verify_authorization_envelope(
            envelope,
            expected_domain=domain,
            verification_public_key=key,
            profile=profile,
            operation_fingerprint=operation_fingerprint,
            expected_phase=verb,
            observed_at_epoch=observed_at_epoch(),
            claim_nonce=claim_nonce,
            authorization_type=kind,
            expected_operation=operation,
            expected_context=exact_context,
        )
        if claim_crash_nonce(context["crash_nonce"]) is not True:
            raise AuthorizationEnvelopeReplay
    except AuthorizationEnvelopeReplay:
        return result(TransactionProcessStatus.BLOCKED_REPLAY)
    except Exception:
        return result(TransactionProcessStatus.BLOCKED_AUTHORIZATION)
    return result(TransactionProcessStatus.BLOCKED_NO_APPROVED_COMMAND)


def _authorization_spec(verb, execution_key, recovery_key):
    if verb == "rollback":
        return (
            AuthorizationEnvelopeDomain.RECOVERY,
            RecoveryAuthorizationV1,
            "recovery",
            recovery_key,
        )
    return (
        AuthorizationEnvelopeDomain.EXECUTION,
        CutoverExecutionAuthorizationV1,
        "cutover_execution",
        execution_key,
    )


def _write(value, exit_code: int) -> int:
    sys.stdout.write(
        f"{value.status.value} accepted={value.accepted} "
        f"rejected={value.rejected} mutations={value.mutations}\n"
    )
    sys.stdout.flush()
    return exit_code


def _exit_code(status) -> int:
    return {
        TransactionProcessStatus.BLOCKED_COMMAND: 2,
        TransactionProcessStatus.BLOCKED_TTY: 3,
        TransactionProcessStatus.BLOCKED_ACKNOWLEDGEMENT: 4,
    }.get(status, 0)
