"""Pure two-observation inspection of one pending journal intent."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV3

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .errors import JournalV2Error
from .journal import R2TransactionJournalV2
from .vocabulary import EffectClassificationV2, JournalRecordTypeV2


_OBS_FIELDS = (
    "observation_type", "binding_fingerprint", "journal_head_fingerprint",
    "transition_instance_fingerprint", "observed_state_fingerprint",
    "identity_fingerprint", "byte_fingerprint", "pre_state_match", "post_state_match",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2StateObservationV2:
    observation_type: str
    binding_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    observed_state_fingerprint: str = field(repr=False)
    identity_fingerprint: str = field(repr=False)
    byte_fingerprint: str = field(repr=False)
    pre_state_match: bool
    post_state_match: bool
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2StateObservationV2 requires create()")

    @classmethod
    def create(cls, **values) -> R2StateObservationV2:
        try:
            if set(values) != set(_OBS_FIELDS) - {"observation_type"}:
                raise JournalV2Error()
            body = {"observation_type": "R2StateObservationV2", **values}
            if not all(is_fingerprint(body[name]) for name in _OBS_FIELDS if name.endswith("fingerprint")):
                raise JournalV2Error()
            if type(body["pre_state_match"]) is not bool or type(body["post_state_match"]) is not bool or (body["pre_state_match"] and body["post_state_match"]):
                raise JournalV2Error()
            return _construct_observation(body)
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    @classmethod
    def from_json(cls, payload: object) -> R2StateObservationV2:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload or set(source) != {*_OBS_FIELDS, "observation_fingerprint"}:
                raise JournalV2Error()
            value = cls.create(**{name: source[name] for name in _OBS_FIELDS if name != "observation_type"})
            if source["observation_type"] != value.observation_type or source["observation_fingerprint"] != value.observation_fingerprint:
                raise JournalV2Error()
            return value
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in _OBS_FIELDS}
        return {**body, "observation_fingerprint": self.observation_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ReadOnlyInspectionReceiptV2:
    receipt_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    first_observation: R2StateObservationV2 = field(repr=False)
    second_observation: R2StateObservationV2 = field(repr=False)
    classification: EffectClassificationV2
    next_legal_action: str
    mutation_count: int
    journal_append_count: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ReadOnlyInspectionReceiptV2 is returned by inspection")

    @classmethod
    def from_json(cls, payload: object, *, binding: object, journal: object):
        try:
            source = strict_json_object(payload)
            first = R2StateObservationV2.from_json(canonical_json(source["first_observation"]))
            second = R2StateObservationV2.from_json(canonical_json(source["second_observation"]))
            value = inspect_pending_transition_v2(journal=journal, first_observation=first, second_observation=second)
            if type(binding) is not ApprovedCutoverBindingV3 or binding.binding_fingerprint != value.binding_fingerprint or canonical_json(source) != payload or source != value.to_mapping():
                raise JournalV2Error()
            return value
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    def to_mapping(self):
        body = {
            "receipt_type": self.receipt_type,
            "binding_fingerprint": self.binding_fingerprint,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "journal_head_fingerprint": self.journal_head_fingerprint,
            "transition_instance_fingerprint": self.transition_instance_fingerprint,
            "first_observation": self.first_observation.to_mapping(),
            "second_observation": self.second_observation.to_mapping(),
            "classification": self.classification.value,
            "next_legal_action": self.next_legal_action,
            "mutation_count": self.mutation_count,
            "journal_append_count": self.journal_append_count,
        }
        return {**body, "receipt_fingerprint": self.receipt_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def inspect_pending_transition_v2(*, journal: object, first_observation: object, second_observation: object) -> R2ReadOnlyInspectionReceiptV2:
    try:
        if type(journal) is not R2TransactionJournalV2 or type(first_observation) is not R2StateObservationV2 or type(second_observation) is not R2StateObservationV2 or first_observation != second_observation:
            raise JournalV2Error()
        if not journal.records or journal.records[-1].record_type is not JournalRecordTypeV2.INTENT:
            raise JournalV2Error()
        intent = journal.records[-1]
        for value in (first_observation, second_observation):
            if value.binding_fingerprint != journal.binding_fingerprint or value.journal_head_fingerprint != journal.current_head_fingerprint or value.transition_instance_fingerprint != intent.transition_instance_fingerprint:
                raise JournalV2Error()
        classification, next_action = _classify(first_observation, intent)
        body = {
            "receipt_type": "R2ReadOnlyInspectionReceiptV2",
            "binding_fingerprint": journal.binding_fingerprint,
            "final_master_binding_fingerprint": journal.genesis.final_master_binding_fingerprint,
            "journal_head_fingerprint": journal.current_head_fingerprint,
            "transition_instance_fingerprint": intent.transition_instance_fingerprint,
            "first_observation": first_observation.to_mapping(),
            "second_observation": second_observation.to_mapping(),
            "classification": classification.value,
            "next_legal_action": next_action,
            "mutation_count": 0,
            "journal_append_count": 0,
        }
        return _construct_receipt(body, first_observation, second_observation)
    except JournalV2Error:
        raise
    except Exception:
        raise JournalV2Error() from None


def _classify(observation, intent):
    if observation.pre_state_match and not observation.post_state_match and observation.observed_state_fingerprint == intent.pre_state_fingerprint:
        return (
            EffectClassificationV2.EFFECT_ABSENT_EXACT,
            "RE" + "TRY_WITH_FRESH_EXECUTION_CONFIRMATION",
        )
    if observation.post_state_match and not observation.pre_state_match and observation.observed_state_fingerprint == intent.post_state_fingerprint:
        return EffectClassificationV2.EFFECT_PRESENT_EXACT, "COMMIT_WITH_FRESH_EXECUTION_CONFIRMATION"
    if not observation.pre_state_match and not observation.post_state_match and observation.observed_state_fingerprint not in {intent.pre_state_fingerprint, intent.post_state_fingerprint}:
        return EffectClassificationV2.EFFECT_AMBIGUOUS, "INCIDENT_STOP"
    raise JournalV2Error()


def _construct_observation(body):
    value = object.__new__(R2StateObservationV2)
    for name in _OBS_FIELDS:
        object.__setattr__(value, name, body[name])
    object.__setattr__(value, "observation_fingerprint", fingerprint("r2-state-observation-v2", body))
    return value


def _construct_receipt(body, first, second):
    value = object.__new__(R2ReadOnlyInspectionReceiptV2)
    for name, item in body.items():
        if name == "first_observation": item = first
        if name == "second_observation": item = second
        if name == "classification": item = EffectClassificationV2(item)
        object.__setattr__(value, name, item)
    object.__setattr__(value, "receipt_fingerprint", fingerprint("r2-read-only-inspection-v2", body))
    return value
