"""Production preflight executable remains unavailable before Issue #39."""

from __future__ import annotations

import sys

from backend.real_host_preflight_composition import (
    locked_current_topology_entry,
    locked_evidence_review_entry,
    locked_evidence_verification_entry,
    locked_final_audit_readiness_entry,
    locked_host_baseline_entry,
    locked_recovery_inspection_entry,
)
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeReplay,
    verify_authorization_envelope,
)
from backend.r2_operator_process.dormant_context import (
    DORMANT_PROFILE,
    PREFLIGHT_OPERATION,
    PREFLIGHT_PUBLIC_KEY,
    claim_envelope_nonce,
    observed_at_epoch,
)

from .contracts import (
    PREFLIGHT_ACKNOWLEDGEMENT,
    PREFLIGHT_VERBS,
    PreflightProcessStatus,
    blocked,
)
from .terminal import SystemTerminal


_ENTRIES = {
    "current-topology": locked_current_topology_entry,
    "host-baseline": locked_host_baseline_entry,
    "evidence-review": locked_evidence_review_entry,
    "evidence-verification": locked_evidence_verification_entry,
    "final-audit-readiness": locked_final_audit_readiness_entry,
    "recovery-inspection": locked_recovery_inspection_entry,
}


def main() -> int:
    value = run_authorization_gate(
        argv=tuple(sys.argv[1:]),
        terminal=SystemTerminal(),
        profile=DORMANT_PROFILE,
        operation_fingerprint=PREFLIGHT_OPERATION,
        verification_public_key=PREFLIGHT_PUBLIC_KEY,
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
    if not _valid_argv(argv):
        return blocked(PreflightProcessStatus.BLOCKED_COMMAND)
    ingress = _read_ingress(terminal)
    if type(ingress) is PreflightProcessStatus:
        return blocked(ingress)
    return _verify_locked_authorization(
        argv[0],
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
        return PreflightProcessStatus.BLOCKED_TTY
    try:
        acknowledgement = terminal.read_acknowledgement()
    except Exception:
        acknowledgement = None
    if acknowledgement != PREFLIGHT_ACKNOWLEDGEMENT:
        return PreflightProcessStatus.BLOCKED_ACKNOWLEDGEMENT
    try:
        envelope = terminal.read_hidden_envelope(65_536)
        if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
            return PreflightProcessStatus.BLOCKED_ENVELOPE
        return envelope
    except Exception:
        return PreflightProcessStatus.BLOCKED_ENVELOPE


def _verify_locked_authorization(
    verb, envelope, profile, operation, public_key, observed_at, claim_nonce
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
        authorization = verify_authorization_envelope(
            envelope,
            expected_domain=AuthorizationEnvelopeDomain.PREFLIGHT,
            verification_public_key=public_key,
            profile=profile,
            operation_fingerprint=operation,
            expected_phase=PREFLIGHT_VERBS[verb],
            observed_at_epoch=observed_at(),
            claim_nonce=claim_nonce,
        )
    except AuthorizationEnvelopeReplay:
        return blocked(PreflightProcessStatus.BLOCKED_REPLAY)
    except Exception:
        return blocked(PreflightProcessStatus.BLOCKED_AUTHORIZATION)
    if profile is DORMANT_PROFILE:
        return blocked(PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND)
    locked = _ENTRIES[verb](
        profile=profile,
        authorization=authorization,
        operation_fingerprint=operation,
        observed_at_epoch=observed_at(),
    )
    if locked.status.value != "BLOCKED_NO_APPROVED_COMMAND":
        return blocked(PreflightProcessStatus.BLOCKED_AUTHORIZATION)
    return blocked(PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND)


def _valid_argv(argv: object) -> bool:
    return (
        type(argv) is tuple
        and len(argv) == 1
        and type(argv[0]) is str
        and argv[0] in PREFLIGHT_VERBS
    )


def _write(result, exit_code: int) -> int:
    sys.stdout.write(
        f"{result.status.value} "
        f"accepted={result.accepted} "
        f"rejected={result.rejected} "
        f"host_operations={result.host_operations}\n"
    )
    sys.stdout.flush()
    return exit_code


def _exit_code(status) -> int:
    return {
        PreflightProcessStatus.BLOCKED_COMMAND: 2,
        PreflightProcessStatus.BLOCKED_TTY: 3,
        PreflightProcessStatus.BLOCKED_ACKNOWLEDGEMENT: 4,
    }.get(status, 0)
