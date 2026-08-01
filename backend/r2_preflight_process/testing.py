"""Synthetic-only binder for the public preflight process seam."""

from __future__ import annotations

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.cutover_composition_contracts.canonical import fingerprint
from backend.cutover_contracts import CutoverProfileV1
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

from .contracts import (
    PREFLIGHT_ACKNOWLEDGEMENT,
    PREFLIGHT_VERBS,
    PreflightProcessStatus,
    blocked,
)


_ENTRIES = {
    "current-topology": locked_current_topology_entry,
    "host-baseline": locked_host_baseline_entry,
    "evidence-review": locked_evidence_review_entry,
    "evidence-verification": locked_evidence_verification_entry,
    "final-audit-readiness": locked_final_audit_readiness_entry,
    "recovery-inspection": locked_recovery_inspection_entry,
}
_MAX_ENVELOPE_CHARS = 65_536


class SyntheticPreflightProcess:
    __slots__ = (
        "_binding",
        "_claimed",
        "_key",
        "_now",
        "_operation",
        "_profile",
        "reader_acquisitions",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticPreflightProcess requires create()")

    @classmethod
    def create(
        cls,
        *,
        profile: CutoverProfileV1,
        binding: ApprovedCutoverBindingV1,
        operation_fingerprint: str,
        verification_public_key: bytes,
        observed_at_epoch,
    ) -> SyntheticPreflightProcess:
        _require_context(
            profile,
            binding,
            operation_fingerprint,
            verification_public_key,
            observed_at_epoch,
        )
        value = object.__new__(cls)
        value._profile = profile
        value._binding = binding
        value._operation = operation_fingerprint
        value._key = verification_public_key
        value._now = observed_at_epoch
        value._claimed = set()
        value.reader_acquisitions = 0
        return value

    def run(self, *, argv: object, terminal: object):
        verb = _exact_verb(argv)
        if verb is None:
            return blocked(PreflightProcessStatus.BLOCKED_COMMAND)
        if _tty_state(terminal) != (True, True, True):
            return blocked(PreflightProcessStatus.BLOCKED_TTY)
        try:
            acknowledgement = terminal.read_acknowledgement()
        except Exception:
            return blocked(PreflightProcessStatus.BLOCKED_ACKNOWLEDGEMENT)
        if acknowledgement != PREFLIGHT_ACKNOWLEDGEMENT:
            return blocked(PreflightProcessStatus.BLOCKED_ACKNOWLEDGEMENT)
        return self._authorize(verb, terminal)

    def _authorize(self, verb, terminal):
        try:
            envelope = terminal.read_hidden_envelope(_MAX_ENVELOPE_CHARS)
            if type(envelope) is not str or not 1 <= len(envelope) <= _MAX_ENVELOPE_CHARS:
                return blocked(PreflightProcessStatus.BLOCKED_ENVELOPE)
            authorization = verify_authorization_envelope(
                envelope,
                expected_domain=AuthorizationEnvelopeDomain.PREFLIGHT,
                verification_public_key=self._key,
                profile=self._profile,
                operation_fingerprint=self._operation,
                expected_phase=PREFLIGHT_VERBS[verb],
                observed_at_epoch=self._now(),
                claim_nonce=self._claim_nonce,
            )
        except AuthorizationEnvelopeReplay:
            return blocked(PreflightProcessStatus.BLOCKED_REPLAY)
        except Exception:
            return blocked(PreflightProcessStatus.BLOCKED_AUTHORIZATION)
        entry = _ENTRIES[verb]
        result = entry(
            profile=self._profile,
            authorization=authorization,
            operation_fingerprint=self._operation,
            observed_at_epoch=self._now(),
        )
        if result.status.value != "BLOCKED_NO_APPROVED_COMMAND":
            return blocked(PreflightProcessStatus.BLOCKED_AUTHORIZATION)
        return blocked(PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND)

    def _claim_nonce(self, nonce: str) -> bool:
        if nonce in self._claimed:
            return False
        self._claimed.add(nonce)
        return True


def _exact_verb(argv: object) -> str | None:
    if (
        type(argv) is not tuple
        or len(argv) != 1
        or type(argv[0]) is not str
        or argv[0] not in PREFLIGHT_VERBS
    ):
        return None
    return argv[0]


def _tty_state(terminal: object) -> object:
    try:
        state = terminal.tty_state()
    except Exception:
        return None
    if type(state) is not tuple or len(state) != 3:
        return None
    return state


def _require_context(profile, binding, operation, key, now) -> None:
    master = fingerprint(
        "project-container-governing-master-v1",
        profile.governing_master_commit,
    )
    if (
        type(profile) is not CutoverProfileV1
        or type(binding) is not ApprovedCutoverBindingV1
        or binding.profile_fingerprint != profile.profile_fingerprint
        or binding.governing_master_fingerprint != master
        or binding.operator_fingerprint != profile.operator_fingerprint
        or binding.operation_fingerprint != operation
        or type(key) is not bytes
        or len(key) != 32
        or not callable(now)
    ):
        raise ValueError("R2_PREFLIGHT_SYNTHETIC_BINDING_INVALID")
