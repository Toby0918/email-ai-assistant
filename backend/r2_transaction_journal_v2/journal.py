"""Immutable, length-framed, append-only R2 transaction journal."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    validate_new_authority_claim,
)

from .errors import JournalV2Error
from .genesis import R2JournalGenesisV2
from .record import R2JournalRecordV2, ZERO_FINGERPRINT
from .vocabulary import EffectClassificationV2, JournalRecordTypeV2


_MAX_FRAME = 128 * 1024


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2TransactionJournalV2:
    _binding: ApprovedCutoverBindingV2 = field(repr=False)
    genesis: R2JournalGenesisV2 = field(repr=False)
    records: tuple[R2JournalRecordV2, ...] = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2TransactionJournalV2 requires create()")

    @classmethod
    def create(cls, *, binding: object, genesis: object) -> R2TransactionJournalV2:
        try:
            if type(binding) is not ApprovedCutoverBindingV2 or type(genesis) is not R2JournalGenesisV2:
                raise JournalV2Error()
            if R2JournalGenesisV2.from_json(genesis.to_canonical_json(), binding=binding) != genesis:
                raise JournalV2Error()
            return _construct(binding, genesis, ())
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    @classmethod
    def from_framed_bytes(cls, payload: object, *, binding: object) -> R2TransactionJournalV2:
        try:
            frames = _decode_frames(payload)
            genesis = R2JournalGenesisV2.from_json(frames[0], binding=binding)
            journal = cls.create(binding=binding, genesis=genesis)
            for frame in frames[1:]:
                record = R2JournalRecordV2.from_json(frame, binding=binding)
                journal = journal._append_existing(record)
            return journal
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    @property
    def binding_fingerprint(self) -> str:
        return self.genesis.binding_fingerprint

    @property
    def journal_owner_fingerprint(self) -> str:
        return self.genesis.journal_owner_fingerprint

    @property
    def current_head_fingerprint(self) -> str:
        return self.genesis.head_fingerprint if not self.records else self.records[-1].head_fingerprint

    @property
    def record_count(self) -> int:
        return len(self.records) + 1

    @property
    def durable_authority_claims(self) -> tuple[DurableAuthorityClaimV2, ...]:
        return (self.genesis.authority_claim,) + tuple(
            record.authority_claim
            for record in self.records
            if record.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM
        )

    @property
    def next_legal_action(self) -> str:
        if not self.records:
            return "CLAIM_FRESH_AUTHORITY"
        last = self.records[-1]
        if last.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM:
            if len(self.records) >= 2 and self.records[-2].record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
                if self.records[-2].effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT:
                    return "APPEND_COMMIT"
            return "APPEND_INTENT"
        if last.record_type is JournalRecordTypeV2.INTENT:
            return "READ_ONLY_INSPECTION"
        if last.record_type is JournalRecordTypeV2.EFFECT_OBSERVATION:
            if last.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT:
                return "APPEND_COMMIT"
            if last.effect_classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
                return "INCIDENT_STOP"
            return "CLAIM_FRESH_AUTHORITY"
        if last.record_type is JournalRecordTypeV2.COMMIT:
            return "CLAIM_FRESH_AUTHORITY_OR_TERMINAL"
        if last.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
            if last.effect_classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
                return "INCIDENT_STOP"
            return "CLAIM_FRESH_AUTHORITY"
        if last.record_type is JournalRecordTypeV2.TERMINAL_STATE:
            return "NONE"
        return "CLAIM_FRESH_AUTHORITY"

    def to_framed_bytes(self) -> bytes:
        frames = (self.genesis.to_canonical_json(),) + tuple(
            record.to_canonical_json() for record in self.records
        )
        return b"".join(f"{len(frame):08x}:".encode("ascii") + frame + b"\n" for frame in frames)

    def append_authority_claim(self, *, claim: object, transition_instance_fingerprint: object) -> R2TransactionJournalV2:
        try:
            validate_new_authority_claim(
                binding=self._binding,
                candidate=claim,
                durable_claims=self.durable_authority_claims,
                observed_at_epoch=claim.claimed_at_epoch,
                expected_prior_journal_head_fingerprint=self.current_head_fingerprint,
            )
            record = self._new_record(
                JournalRecordTypeV2.AUTHORITY_CLAIM,
                transition_instance_fingerprint,
                authority_claim=claim,
            )
            return self._append_existing(record)
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    def append_intent(self, *, transition_instance_fingerprint: object, pre_state_fingerprint: object, post_state_fingerprint: object) -> R2TransactionJournalV2:
        record = self._new_record(
            JournalRecordTypeV2.INTENT,
            transition_instance_fingerprint,
            pre_state_fingerprint=pre_state_fingerprint,
            post_state_fingerprint=post_state_fingerprint,
        )
        return self._append_existing(record)

    def append_effect_observation(self, *, transition_instance_fingerprint: object, observed_state_fingerprint: object, classification: object) -> R2TransactionJournalV2:
        record = self._new_record(
            JournalRecordTypeV2.EFFECT_OBSERVATION,
            transition_instance_fingerprint,
            observed_state_fingerprint=observed_state_fingerprint,
            effect_classification=classification,
        )
        return self._append_existing(record)

    def append_commit(self, *, transition_instance_fingerprint: object, committed_state_fingerprint: object) -> R2TransactionJournalV2:
        record = self._new_record(
            JournalRecordTypeV2.COMMIT,
            transition_instance_fingerprint,
            observed_state_fingerprint=committed_state_fingerprint,
        )
        return self._append_existing(record)

    def append_recovery_classification(self, *, transition_instance_fingerprint: object, observed_state_fingerprint: object, classification: object, inspection_receipt_fingerprint: object) -> R2TransactionJournalV2:
        record = self._new_record(
            JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
            transition_instance_fingerprint,
            observed_state_fingerprint=observed_state_fingerprint,
            inspection_receipt_fingerprint=inspection_receipt_fingerprint,
            effect_classification=classification,
        )
        return self._append_existing(record)

    def append_terminal_state(self, *, transition_instance_fingerprint: object, final_state_fingerprint: object, terminal_state: object, terminal_evidence_fingerprint: object) -> R2TransactionJournalV2:
        record = self._new_record(
            JournalRecordTypeV2.TERMINAL_STATE,
            transition_instance_fingerprint,
            observed_state_fingerprint=final_state_fingerprint,
            terminal_evidence_fingerprint=terminal_evidence_fingerprint,
            terminal_state=terminal_state,
        )
        return self._append_existing(record)

    def _new_record(self, kind, transition, **overrides):
        values = {
            "binding": self._binding,
            "record_type": kind,
            "journal_owner_fingerprint": self.journal_owner_fingerprint,
            "record_sequence": len(self.records) + 1,
            "predecessor_head_fingerprint": self.current_head_fingerprint,
            "transition_instance_fingerprint": transition,
            "authority_claim": None,
            "pre_state_fingerprint": ZERO_FINGERPRINT,
            "post_state_fingerprint": ZERO_FINGERPRINT,
            "observed_state_fingerprint": ZERO_FINGERPRINT,
            "inspection_receipt_fingerprint": ZERO_FINGERPRINT,
            "terminal_evidence_fingerprint": ZERO_FINGERPRINT,
            "effect_classification": "",
            "terminal_state": "",
        }
        values.update(overrides)
        return R2JournalRecordV2.create(**values)

    def _append_existing(self, record):
        _validate_transition(self, record)
        return _construct(self._binding, self.genesis, self.records + (record,))


def _validate_transition(journal, record):
    if type(record) is not R2JournalRecordV2 or record.record_sequence != len(journal.records) + 1 or record.predecessor_head_fingerprint != journal.current_head_fingerprint or record.journal_owner_fingerprint != journal.journal_owner_fingerprint:
        raise JournalV2Error()
    previous = journal.records[-1] if journal.records else None
    _validate_record_kind(journal, record, previous)


def _validate_record_kind(journal, record, previous):
    if record.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM:
        if previous is not None and previous.record_type not in {
            JournalRecordTypeV2.COMMIT,
            JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
        }:
            raise JournalV2Error()
        if previous is not None and previous.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION and previous.effect_classification is EffectClassificationV2.EFFECT_AMBIGUOUS:
            raise JournalV2Error()
        validate_new_authority_claim(binding=journal._binding, candidate=record.authority_claim, durable_claims=journal.durable_authority_claims, observed_at_epoch=record.authority_claim.claimed_at_epoch, expected_prior_journal_head_fingerprint=journal.current_head_fingerprint)
    elif record.record_type is JournalRecordTypeV2.INTENT:
        if previous is None or previous.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM or record.transition_instance_fingerprint != previous.transition_instance_fingerprint:
            raise JournalV2Error()
        if len(journal.records) >= 2:
            classified = journal.records[-2]
            if classified.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION and (classified.effect_classification is not EffectClassificationV2.EFFECT_ABSENT_EXACT or record.transition_instance_fingerprint != classified.transition_instance_fingerprint):
                raise JournalV2Error()
    elif record.record_type is JournalRecordTypeV2.EFFECT_OBSERVATION:
        if previous is None or previous.record_type is not JournalRecordTypeV2.INTENT or record.transition_instance_fingerprint != previous.transition_instance_fingerprint:
            raise JournalV2Error()
        exact = record.observed_state_fingerprint
        if record.effect_classification is EffectClassificationV2.EFFECT_ABSENT_EXACT and exact != previous.pre_state_fingerprint:
            raise JournalV2Error()
        if record.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT and exact != previous.post_state_fingerprint:
            raise JournalV2Error()
        if record.effect_classification is EffectClassificationV2.EFFECT_AMBIGUOUS and exact in {previous.pre_state_fingerprint, previous.post_state_fingerprint}:
            raise JournalV2Error()
    elif record.record_type is JournalRecordTypeV2.COMMIT:
        direct = previous is not None and previous.record_type is JournalRecordTypeV2.EFFECT_OBSERVATION and previous.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT and record.transition_instance_fingerprint == previous.transition_instance_fingerprint and record.observed_state_fingerprint == previous.observed_state_fingerprint
        recovered = False
        if previous is not None and previous.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM and len(journal.records) >= 2:
            classified = journal.records[-2]
            recovered = classified.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION and classified.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT and record.transition_instance_fingerprint == classified.transition_instance_fingerprint and record.observed_state_fingerprint == classified.observed_state_fingerprint
        if not direct and not recovered:
            raise JournalV2Error()
    elif record.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
        if previous is None or previous.record_type is not JournalRecordTypeV2.INTENT or record.transition_instance_fingerprint != previous.transition_instance_fingerprint:
            raise JournalV2Error()
        exact = record.observed_state_fingerprint
        if record.effect_classification is EffectClassificationV2.EFFECT_ABSENT_EXACT and exact != previous.pre_state_fingerprint:
            raise JournalV2Error()
        if record.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT and exact != previous.post_state_fingerprint:
            raise JournalV2Error()
        if record.effect_classification is EffectClassificationV2.EFFECT_AMBIGUOUS and exact in {previous.pre_state_fingerprint, previous.post_state_fingerprint}:
            raise JournalV2Error()
    elif record.record_type is JournalRecordTypeV2.TERMINAL_STATE:
        if previous is None or previous.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM or record.transition_instance_fingerprint != previous.transition_instance_fingerprint:
            raise JournalV2Error()
    else:
        raise JournalV2Error()


def _decode_frames(payload):
    if type(payload) is not bytes or not payload:
        raise JournalV2Error()
    frames, cursor = [], 0
    while cursor < len(payload):
        if cursor + 9 > len(payload) or payload[cursor + 8:cursor + 9] != b":" or any(value not in b"0123456789abcdef" for value in payload[cursor:cursor + 8]):
            raise JournalV2Error()
        size = int(payload[cursor:cursor + 8], 16)
        start, end = cursor + 9, cursor + 9 + size
        if not 1 <= size <= _MAX_FRAME or end >= len(payload) or payload[end:end + 1] != b"\n":
            raise JournalV2Error()
        frames.append(payload[start:end])
        cursor = end + 1
    return tuple(frames)


def _construct(binding, genesis, records):
    value = object.__new__(R2TransactionJournalV2)
    object.__setattr__(value, "_binding", binding)
    object.__setattr__(value, "genesis", genesis)
    object.__setattr__(value, "records", records)
    return value
