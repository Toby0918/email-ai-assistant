"""Production evidence executable stays unavailable before Issue #39."""

from __future__ import annotations

import sys

from backend.cutover_contracts import EvidencePublicationAuthorizationV1
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeReplay,
    verify_authorization_envelope,
)
from backend.r2_operator_process.dormant_context import (
    DORMANT_PROFILE,
    EVIDENCE_OPERATION,
    EVIDENCE_PUBLIC_KEY,
    claim_envelope_nonce,
    observed_at_epoch,
)

from .contracts import (
    EVIDENCE_ACKNOWLEDGEMENT,
    EvidenceProcessStatus,
    result,
)
from .terminal import SystemTerminal


def main() -> int:
    value = run_authorization_gate(
        argv=tuple(sys.argv[1:]),
        terminal=SystemTerminal(),
        profile=DORMANT_PROFILE,
        operation_fingerprint=EVIDENCE_OPERATION,
        verification_public_key=EVIDENCE_PUBLIC_KEY,
        observed_at_epoch=observed_at_epoch,
        claim_nonce=claim_envelope_nonce,
    )
    return _write(value, _exit_code(value.status))


def run_authorization_gate(
    *,
    argv,
    terminal,
    profile=None,
    operation_fingerprint=None,
    verification_public_key=None,
    observed_at_epoch=None,
    claim_nonce=None,
):
    if argv != ("publish",):
        return result(EvidenceProcessStatus.BLOCKED_COMMAND)
    ingress = _read_ingress(terminal)
    if type(ingress) is EvidenceProcessStatus:
        return result(ingress)
    return _verify_locked_authorization(
        ingress,
        profile,
        operation_fingerprint,
        verification_public_key,
        observed_at_epoch,
        claim_nonce,
    )


def _read_ingress(terminal):
    try:
        tty_state = terminal.tty_state()
    except Exception:
        tty_state = None
    if tty_state != (True, True, True):
        return EvidenceProcessStatus.BLOCKED_TTY
    try:
        acknowledgement = terminal.read_acknowledgement()
    except Exception:
        acknowledgement = None
    if acknowledgement != EVIDENCE_ACKNOWLEDGEMENT:
        return EvidenceProcessStatus.BLOCKED_ACKNOWLEDGEMENT
    try:
        envelope = terminal.read_hidden_envelope(65_536)
        if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
            return EvidenceProcessStatus.BLOCKED_ENVELOPE
        return envelope
    except Exception:
        return EvidenceProcessStatus.BLOCKED_ENVELOPE


def _verify_locked_authorization(
    envelope, profile, operation, public_key, observed_at, claim_nonce
):
    try:
        if None in (
            profile,
            operation,
            public_key,
            observed_at,
            claim_nonce,
        ):
            raise ValueError
        verify_authorization_envelope(
            envelope,
            expected_domain=AuthorizationEnvelopeDomain.EVIDENCE,
            verification_public_key=public_key,
            profile=profile,
            operation_fingerprint=operation,
            expected_phase="evidence_publication",
            observed_at_epoch=observed_at(),
            claim_nonce=claim_nonce,
            authorization_type=EvidencePublicationAuthorizationV1,
            expected_operation="evidence_publication",
        )
    except AuthorizationEnvelopeReplay:
        return result(EvidenceProcessStatus.BLOCKED_REPLAY)
    except Exception:
        return result(EvidenceProcessStatus.BLOCKED_AUTHORIZATION)
    return result(EvidenceProcessStatus.BLOCKED_NO_APPROVED_COMMAND)


def _write(value, exit_code: int) -> int:
    sys.stdout.write(
        f"{value.status.value} accepted={value.accepted} "
        f"rejected={value.rejected} published={value.published}\n"
    )
    sys.stdout.flush()
    return exit_code


def _exit_code(status) -> int:
    return {
        EvidenceProcessStatus.BLOCKED_COMMAND: 2,
        EvidenceProcessStatus.BLOCKED_TTY: 3,
        EvidenceProcessStatus.BLOCKED_ACKNOWLEDGEMENT: 4,
    }.get(status, 0)
