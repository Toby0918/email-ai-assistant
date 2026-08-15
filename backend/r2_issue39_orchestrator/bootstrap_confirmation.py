"""Fresh real-console claims owned by the evidence bootstrap."""

from __future__ import annotations

import hashlib
import secrets
import time

from backend.r2_production_binding import (
    ProductionCommandV2,
    confirm_execution_confirmation_v1,
    prepare_execution_confirmation_v1,
    production_action_fingerprint_v2,
)


def confirm_genesis(closure, package):
    binding = closure.production
    owner = hashlib.sha256(
        b"r2-issue39-journal-owner-v1\0"
        + bytes.fromhex(binding.binding_fingerprint)
    ).hexdigest()
    claim = _confirm(
        closure, package, ProductionCommandV2.EVIDENCE_PUBLICATION,
        owner, "0" * 64, 1,
    )
    return claim, _clock(), owner, secrets.token_hex(32)


def confirm_evidence(closure, package, journal):
    action = hashlib.sha256(
        b"r2-issue39-evidence-attempt-action-v1\0"
        + bytes.fromhex(package.reviewed_evidence_fingerprint)
        + bytes.fromhex(journal.current_head_fingerprint)
    ).hexdigest()
    return _confirm(
        closure, package, ProductionCommandV2.EVIDENCE_PUBLICATION,
        journal.journal_owner_fingerprint,
        journal.current_head_fingerprint,
        len(journal.execution_confirmation_claims) + 1,
        action,
    ), _clock()


def confirm_resume(closure, package, journal):
    return _confirm(
        closure, package, ProductionCommandV2.RESUME,
        journal.journal_owner_fingerprint,
        journal.current_head_fingerprint,
        len(journal.execution_confirmation_claims) + 1,
    ), _clock()


def _confirm(closure, package, command, owner, head, sequence, action=None):
    binding = closure.production
    candidate = prepare_execution_confirmation_v1(
        binding=binding,
        closure_manifest_fingerprint=closure.manifest.manifest_fingerprint,
        solo_maintainer_attestation_receipt_fingerprint=(
            closure.receipt.receipt_fingerprint
        ),
        command=command,
        action_fingerprint=action or production_action_fingerprint_v2(
            binding, command,
            subject_fingerprint=package.reviewed_evidence_fingerprint,
        ),
        journal_owner_fingerprint=owner,
        prior_journal_head_fingerprint=head,
        transition_instance_fingerprint=package.reviewed_evidence_fingerprint,
        remaining_reverse_plan_fingerprint="0" * 64,
        claim_sequence=sequence,
    )
    return confirm_execution_confirmation_v1(candidate=candidate)


def _clock():
    return {
        "observed_at_epoch": int(time.time()),
        "observed_monotonic_ns": time.monotonic_ns(),
    }
