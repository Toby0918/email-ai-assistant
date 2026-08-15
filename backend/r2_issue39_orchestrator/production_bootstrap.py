"""Journal-first create-only evidence bootstrap for the fixed production run."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from backend.r2_transaction_journal_v2 import (
    EffectClassificationV2,
    R2JournalGenesisV2,
    R2TransactionJournalV2,
)
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .closure_binding import _Issue39ClosureBindingV1
from .bootstrap_confirmation import (
    confirm_evidence as _confirm_evidence,
    confirm_genesis as _confirm_genesis,
    confirm_resume as _confirm_resume,
)
from .durable_io import guard_directory
from .durable_ledger import (
    Issue39LedgerStatusV1,
    _Issue39LedgerLocationV1,
    _append_issue39_journal_v1,
    _create_issue39_ledger_v1,
    _reopen_issue39_ledger_v1,
)
from .production_evidence import (
    Issue39EvidencePackageV1,
    fixed_issue39_evidence_location_v1,
    publish_fixed_issue39_evidence_v1,
    verify_fixed_issue39_evidence_v1,
)


_LEDGER_PARENT = Path(r"D:\IncidentArchives\email_ai_assistant\issue38")


def bootstrap_fixed_issue39_journal_v1(*, closure, package):
    if (
        type(closure) is not _Issue39ClosureBindingV1
        or type(package) is not Issue39EvidencePackageV1
    ):
        raise TypeError("R2_ISSUE39_BOOTSTRAP_INVALID")
    binding = closure.production
    evidence_location = fixed_issue39_evidence_location_v1(package)
    ledger = _Issue39LedgerLocationV1(
        _LEDGER_PARENT / f".issue39-ledger-{binding.binding_fingerprint}"
    )
    if os.path.lexists(ledger.directory):
        reopened = _reopen_issue39_ledger_v1(
            location=ledger, binding=binding
        )
        if reopened.status is not Issue39LedgerStatusV1.VERIFIED:
            raise TypeError("R2_ISSUE39_BOOTSTRAP_LEDGER_INVALID")
        journal = reopened.journal
        _require_genesis(journal, closure, package)
        return ledger, _resume_evidence(
            ledger, closure, package, journal
        )
    claim, clock, owner, nonce = _confirm_genesis(closure, package)
    genesis = R2JournalGenesisV2.create(
        binding=binding,
        reviewed_evidence_fingerprint=package.reviewed_evidence_fingerprint,
        evidence_identity_fingerprint=package.evidence_identity_fingerprint,
        package_fingerprint=package.package_fingerprint,
        manifest_fingerprint=closure.manifest.manifest_fingerprint,
        journal_owner_fingerprint=owner,
        genesis_nonce=nonce,
        pre_genesis_head_fingerprint="0" * 64,
        execution_confirmation_claim=claim,
    )
    journal = R2TransactionJournalV2.create(
        binding=binding, genesis=genesis, **clock
    )
    created = _create_issue39_ledger_v1(
        location=ledger, binding=binding, journal=journal
    )
    if created.status is not Issue39LedgerStatusV1.CREATED:
        raise TypeError("R2_ISSUE39_BOOTSTRAP_LEDGER_INVALID")
    return ledger, _start_evidence(ledger, closure, package, journal)


def _start_evidence(ledger, closure, package, journal):
    claim, clock = _confirm_evidence(closure, package, journal)
    claimed = journal.append_execution_confirmation_claim(
        claim=claim,
        transition_instance_fingerprint=package.reviewed_evidence_fingerprint,
        **clock,
    )
    _persist(ledger, closure, journal, claimed)
    return _publish_evidence(ledger, closure, package, claimed)


def _publish_evidence(ledger, closure, package, journal):
    transition = package.reviewed_evidence_fingerprint
    pre, post = _evidence_states(package)
    pending = journal.append_intent(
        transition_instance_fingerprint=transition,
        pre_state_fingerprint=pre,
        post_state_fingerprint=post,
    )
    _persist(ledger, closure, journal, pending)
    _ensure_parent(fixed_issue39_evidence_location_v1(package).parent)
    publish_fixed_issue39_evidence_v1(package)
    if verify_fixed_issue39_evidence_v1(package) is not True:
        raise TypeError("R2_ISSUE39_EVIDENCE_VERIFY_INVALID")
    complete = pending.append_effect_observation(
        transition_instance_fingerprint=transition,
        observed_state_fingerprint=post,
        classification=EffectClassificationV2.EFFECT_PRESENT_EXACT,
    ).append_commit(
        transition_instance_fingerprint=transition,
        committed_state_fingerprint=post,
    )
    _persist(ledger, closure, pending, complete)
    return complete


def _resume_evidence(ledger, closure, package, journal):
    pre, post = _evidence_states(package)
    present = _evidence_observation(package, pre, post)
    if (
        journal.records
        and journal.records[-1].record_type is JournalRecordTypeV2.COMMIT
        and present == post
    ):
        return journal
    if not journal.records:
        return _start_evidence(ledger, closure, package, journal)
    if journal.next_legal_action == "READ_ONLY_INSPECTION":
        return _classify_evidence(
            ledger, closure, package, journal, present, pre, post
        )
    if (
        journal.next_legal_action == "CLAIM_FRESH_EXECUTION_CONFIRMATION"
        and journal.records[-1].record_type
        in {
            JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
            JournalRecordTypeV2.EFFECT_OBSERVATION,
        }
    ):
        return _resume_classified(ledger, closure, package, journal, post)
    if journal.next_legal_action == "APPEND_INTENT":
        return _publish_evidence(ledger, closure, package, journal)
    if journal.next_legal_action == "APPEND_COMMIT":
        return _commit_evidence(ledger, closure, package, journal, post)
    raise TypeError("R2_ISSUE39_EVIDENCE_RECOVERY_INVALID")


def _classify_evidence(ledger, closure, package, journal, present, pre, post):
    classification = (
        EffectClassificationV2.EFFECT_PRESENT_EXACT
        if present == post
        else (
            EffectClassificationV2.EFFECT_ABSENT_EXACT
            if present == pre
            else EffectClassificationV2.EFFECT_AMBIGUOUS
        )
    )
    classified = journal.append_recovery_classification(
        transition_instance_fingerprint=(
            package.reviewed_evidence_fingerprint
        ),
        observed_state_fingerprint=present,
        classification=classification,
        inspection_receipt_fingerprint=_hash(
            b"r2-issue39-evidence-inspection-v1\0"
            + bytes.fromhex(present)
        ),
    )
    _persist(ledger, closure, journal, classified)
    if classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
        raise TypeError("R2_ISSUE39_EVIDENCE_RECOVERY_INVALID")
    return _resume_classified(ledger, closure, package, classified, post)


def _resume_classified(ledger, closure, package, classified, post):
    claim, clock = _confirm_resume(closure, package, classified)
    claimed = classified.append_execution_confirmation_claim(
        claim=claim,
        transition_instance_fingerprint=package.reviewed_evidence_fingerprint,
        **clock,
    )
    _persist(ledger, closure, classified, claimed)
    if classified.records[-1].effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT:
        return _commit_evidence(ledger, closure, package, claimed, post)
    return _publish_evidence(ledger, closure, package, claimed)


def _commit_evidence(ledger, closure, package, journal, post):
    observed = journal.records[-2]
    complete = journal.append_commit(
        transition_instance_fingerprint=package.reviewed_evidence_fingerprint,
        committed_state_fingerprint=post,
        evidence_receipt_fingerprint=observed.inspection_receipt_fingerprint,
    )
    _persist(ledger, closure, journal, complete)
    return complete


def _persist(location, closure, previous, current):
    result = _append_issue39_journal_v1(
        location=location, binding=closure.production,
        previous=previous, journal=current,
    )
    if result.status is not Issue39LedgerStatusV1.APPENDED:
        raise TypeError("R2_ISSUE39_BOOTSTRAP_LEDGER_INVALID")


def _ensure_parent(parent):
    if os.path.lexists(parent):
        with guard_directory(parent, flush=True):
            return
    with guard_directory(parent.parent, flush=True):
        parent.mkdir(mode=0o700)
    with guard_directory(parent, flush=True):
        return


def _evidence_states(package):
    pre = _hash(
        b"r2-issue39-evidence-absent-v1\0"
        + bytes.fromhex(package.package_fingerprint)
    )
    post = _hash(
        b"r2-issue39-evidence-present-v1\0"
        + bytes.fromhex(package.package_fingerprint)
    )
    return pre, post


def _evidence_observation(package, pre, post):
    location = fixed_issue39_evidence_location_v1(package)
    if not os.path.lexists(location):
        return pre
    return post if verify_fixed_issue39_evidence_v1(package) else "f" * 64


def _require_genesis(journal, closure, package):
    genesis = journal.genesis
    if (
        genesis.manifest_fingerprint != closure.manifest.manifest_fingerprint
        or genesis.reviewed_evidence_fingerprint
        != package.reviewed_evidence_fingerprint
        or genesis.evidence_identity_fingerprint
        != package.evidence_identity_fingerprint
        or genesis.package_fingerprint != package.package_fingerprint
    ):
        raise TypeError("R2_ISSUE39_BOOTSTRAP_LEDGER_INVALID")


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()
