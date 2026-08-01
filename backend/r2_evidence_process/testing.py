"""Synthetic-only binder for the evidence publication process."""

from __future__ import annotations

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.cutover_composition_contracts.canonical import (
    fingerprint,
    is_fingerprint,
)
from backend.cutover_contracts import (
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
)
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeReplay,
    verify_authorization_envelope,
)

from .contracts import (
    EVIDENCE_ACKNOWLEDGEMENT,
    EVIDENCE_VERBS,
    EvidenceProcessStatus,
    result,
)


_MAX_ENVELOPE_CHARS = 65_536


class SyntheticEvidenceProcess:
    __slots__ = (
        "_binding",
        "_claimed",
        "_confirmed_review",
        "_expected_review",
        "_key",
        "_locked",
        "_now",
        "_operation",
        "_profile",
        "_publish",
        "_publication_attempted",
        "_published",
        "publication_acquisitions",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticEvidenceProcess requires create()")

    @classmethod
    def create(cls, **values) -> SyntheticEvidenceProcess:
        _require_context(values)
        process = object.__new__(cls)
        process._profile = values["profile"]
        process._binding = values["binding"]
        process._operation = values["operation_fingerprint"]
        process._confirmed_review = values["confirmed_review_fingerprint"]
        process._expected_review = values["expected_review_fingerprint"]
        process._key = values["verification_public_key"]
        process._now = values["observed_at_epoch"]
        process._publish = values["publish_confirmed_review"]
        process._locked = values["real_locked"]
        process._claimed = set()
        process._publication_attempted = False
        process._published = False
        process.publication_acquisitions = 0
        return process

    def run(self, *, argv: object, terminal: object):
        if argv != ("publish",):
            return result(EvidenceProcessStatus.BLOCKED_COMMAND)
        if _tty_state(terminal) != (True, True, True):
            return result(EvidenceProcessStatus.BLOCKED_TTY)
        try:
            acknowledgement = terminal.read_acknowledgement()
        except Exception:
            return result(EvidenceProcessStatus.BLOCKED_ACKNOWLEDGEMENT)
        if acknowledgement != EVIDENCE_ACKNOWLEDGEMENT:
            return result(EvidenceProcessStatus.BLOCKED_ACKNOWLEDGEMENT)
        if self._confirmed_review != self._expected_review:
            return result(EvidenceProcessStatus.BLOCKED_AUTHORIZATION)
        return self._authorize_and_publish(terminal)

    def _authorize_and_publish(self, terminal):
        try:
            envelope = terminal.read_hidden_envelope(_MAX_ENVELOPE_CHARS)
            if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
                return result(EvidenceProcessStatus.BLOCKED_ENVELOPE)
            verify_authorization_envelope(
                envelope,
                expected_domain=AuthorizationEnvelopeDomain.EVIDENCE,
                verification_public_key=self._key,
                profile=self._profile,
                operation_fingerprint=self._operation,
                expected_phase=EVIDENCE_VERBS["publish"],
                observed_at_epoch=self._now(),
                claim_nonce=self._claim_nonce,
                authorization_type=EvidencePublicationAuthorizationV1,
                expected_operation="evidence_publication",
            )
        except AuthorizationEnvelopeReplay:
            return result(EvidenceProcessStatus.BLOCKED_REPLAY)
        except Exception:
            return result(EvidenceProcessStatus.BLOCKED_AUTHORIZATION)
        if self._locked:
            return result(EvidenceProcessStatus.BLOCKED_NO_APPROVED_COMMAND)
        return self._publish_once()

    def _publish_once(self):
        if self._publication_attempted:
            return result(EvidenceProcessStatus.BLOCKED_PUBLICATION)
        self._publication_attempted = True
        self.publication_acquisitions += 1
        try:
            published = self._publish()
        except Exception:
            return result(EvidenceProcessStatus.BLOCKED_PUBLICATION)
        if published != 1:
            return result(EvidenceProcessStatus.BLOCKED_PUBLICATION)
        self._published = True
        return result(EvidenceProcessStatus.PUBLISHED)

    def _claim_nonce(self, nonce: str) -> bool:
        if nonce in self._claimed:
            return False
        self._claimed.add(nonce)
        return True


def _tty_state(terminal: object) -> object:
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
        "confirmed_review_fingerprint",
        "expected_review_fingerprint",
        "verification_public_key",
        "observed_at_epoch",
        "publish_confirmed_review",
        "real_locked",
    }
    if type(values) is not dict or set(values) != expected:
        raise ValueError("R2_EVIDENCE_SYNTHETIC_BINDING_INVALID")
    profile = values["profile"]
    binding = values["binding"]
    if (
        type(profile) is not CutoverProfileV1
        or type(binding) is not ApprovedCutoverBindingV1
    ):
        raise ValueError("R2_EVIDENCE_SYNTHETIC_BINDING_INVALID")
    master = fingerprint(
        "project-container-governing-master-v1",
        profile.governing_master_commit,
    )
    if (
        binding.profile_fingerprint != profile.profile_fingerprint
        or binding.governing_master_fingerprint != master
        or binding.operation_fingerprint != values["operation_fingerprint"]
        or not is_fingerprint(values["confirmed_review_fingerprint"])
        or not is_fingerprint(values["expected_review_fingerprint"])
        or type(values["verification_public_key"]) is not bytes
        or len(values["verification_public_key"]) != 32
        or not callable(values["observed_at_epoch"])
        or not callable(values["publish_confirmed_review"])
        or type(values["real_locked"]) is not bool
    ):
        raise ValueError("R2_EVIDENCE_SYNTHETIC_BINDING_INVALID")
