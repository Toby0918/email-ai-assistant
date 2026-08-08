"""One canonical content-free record in the unified journal."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ExecutionConfirmationClaimV1,
)

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .errors import JournalV2Error
from .vocabulary import EffectClassificationV2, JournalRecordTypeV2, TerminalStateV2


ZERO_FINGERPRINT = "0" * 64
_FIELDS = (
    "record_type",
    "binding_fingerprint",
    "final_master_binding_fingerprint",
    "journal_owner_fingerprint",
    "record_sequence",
    "predecessor_head_fingerprint",
    "transition_instance_fingerprint",
    "execution_confirmation_claim",
    "pre_state_fingerprint",
    "post_state_fingerprint",
    "observed_state_fingerprint",
    "inspection_receipt_fingerprint",
    "terminal_evidence_fingerprint",
    "effect_classification",
    "terminal_state",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2JournalRecordV2:
    record_type: JournalRecordTypeV2
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    record_sequence: int
    predecessor_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    execution_confirmation_claim: ExecutionConfirmationClaimV1 | None = field(
        repr=False
    )
    pre_state_fingerprint: str = field(repr=False)
    post_state_fingerprint: str = field(repr=False)
    observed_state_fingerprint: str = field(repr=False)
    inspection_receipt_fingerprint: str = field(repr=False)
    terminal_evidence_fingerprint: str = field(repr=False)
    effect_classification: EffectClassificationV2 | None
    terminal_state: TerminalStateV2 | None
    head_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2JournalRecordV2 requires create()")

    @classmethod
    def create(cls, *, binding: object, **values: object) -> R2JournalRecordV2:
        try:
            body, claim = _build_body(binding=binding, **values)
            return _construct(body, claim)
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    @classmethod
    def from_json(cls, payload: object, *, binding: object) -> R2JournalRecordV2:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload or set(source) != {*_FIELDS, "head_fingerprint"}:
                raise JournalV2Error()
            raw_claim = source["execution_confirmation_claim"]
            claim = None
            if raw_claim is not None:
                claim = ExecutionConfirmationClaimV1.from_json(
                    canonical_json(raw_claim), binding=binding
                )
            body, parsed_claim = _build_body(
                binding=binding,
                record_type=JournalRecordTypeV2(source["record_type"]),
                journal_owner_fingerprint=source["journal_owner_fingerprint"],
                record_sequence=source["record_sequence"],
                predecessor_head_fingerprint=source["predecessor_head_fingerprint"],
                transition_instance_fingerprint=source["transition_instance_fingerprint"],
                execution_confirmation_claim=claim,
                pre_state_fingerprint=source["pre_state_fingerprint"],
                post_state_fingerprint=source["post_state_fingerprint"],
                observed_state_fingerprint=source["observed_state_fingerprint"],
                inspection_receipt_fingerprint=source["inspection_receipt_fingerprint"],
                terminal_evidence_fingerprint=source["terminal_evidence_fingerprint"],
                effect_classification=source["effect_classification"],
                terminal_state=source["terminal_state"],
            )
            if any(source[name] != body[name] for name in _FIELDS):
                raise JournalV2Error()
            if source["head_fingerprint"] != fingerprint("r2-journal-record-v2", body):
                raise JournalV2Error()
            return _construct(body, parsed_claim)
        except JournalV2Error:
            raise
        except Exception:
            raise JournalV2Error() from None

    def to_mapping(self) -> dict[str, object]:
        body = {name: getattr(self, name) for name in _FIELDS}
        body["record_type"] = self.record_type.value
        body["execution_confirmation_claim"] = (
            None
            if self.execution_confirmation_claim is None
            else self.execution_confirmation_claim.to_mapping()
        )
        body["effect_classification"] = (
            "" if self.effect_classification is None else self.effect_classification.value
        )
        body["terminal_state"] = (
            "" if self.terminal_state is None else self.terminal_state.value
        )
        return {**body, "head_fingerprint": self.head_fingerprint}

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _build_body(*, binding, record_type, execution_confirmation_claim=None, **values):
    if type(binding) is not ApprovedCutoverBindingV3:
        raise JournalV2Error()
    record_type = JournalRecordTypeV2(record_type)
    required = {
        "journal_owner_fingerprint",
        "record_sequence",
        "predecessor_head_fingerprint",
        "transition_instance_fingerprint",
        "pre_state_fingerprint",
        "post_state_fingerprint",
        "observed_state_fingerprint",
        "inspection_receipt_fingerprint",
        "terminal_evidence_fingerprint",
        "effect_classification",
        "terminal_state",
    }
    if set(values) != required or type(values["record_sequence"]) is not int:
        raise JournalV2Error()
    if values["record_sequence"] < 1 or not all(
        is_fingerprint(values[name]) for name in required if name.endswith("fingerprint")
    ):
        raise JournalV2Error()
    classification = values["effect_classification"]
    terminal = values["terminal_state"]
    classification = None if classification == "" else EffectClassificationV2(classification)
    terminal = None if terminal == "" else TerminalStateV2(terminal)
    _require_shape(
        record_type, execution_confirmation_claim, classification, terminal, values
    )
    return {
        "record_type": record_type.value,
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        **values,
        "execution_confirmation_claim": (
            None
            if execution_confirmation_claim is None
            else execution_confirmation_claim.to_mapping()
        ),
        "effect_classification": "" if classification is None else classification.value,
        "terminal_state": "" if terminal is None else terminal.value,
    }, execution_confirmation_claim


def _require_shape(kind, claim, classification, terminal, values):
    zeros = {name: values[name] == ZERO_FINGERPRINT for name in (
        "pre_state_fingerprint", "post_state_fingerprint", "observed_state_fingerprint",
        "inspection_receipt_fingerprint",
        "terminal_evidence_fingerprint",
    )}
    valid = False
    if kind is JournalRecordTypeV2.AUTHORITY_CLAIM:
        valid = type(claim) is ExecutionConfirmationClaimV1 and all(zeros.values()) and classification is None and terminal is None
    elif kind is JournalRecordTypeV2.INTENT:
        valid = claim is None and not zeros["pre_state_fingerprint"] and not zeros["post_state_fingerprint"] and zeros["observed_state_fingerprint"] and zeros["inspection_receipt_fingerprint"] and zeros["terminal_evidence_fingerprint"] and values["pre_state_fingerprint"] != values["post_state_fingerprint"] and classification is None and terminal is None
    elif kind is JournalRecordTypeV2.EFFECT_OBSERVATION:
        valid = claim is None and zeros["pre_state_fingerprint"] and zeros["post_state_fingerprint"] and not zeros["observed_state_fingerprint"] and zeros["inspection_receipt_fingerprint"] and zeros["terminal_evidence_fingerprint"] and classification is not None and terminal is None
    elif kind is JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
        valid = claim is None and zeros["pre_state_fingerprint"] and zeros["post_state_fingerprint"] and not zeros["observed_state_fingerprint"] and not zeros["inspection_receipt_fingerprint"] and zeros["terminal_evidence_fingerprint"] and classification is not None and terminal is None
    elif kind is JournalRecordTypeV2.COMMIT:
        valid = claim is None and zeros["pre_state_fingerprint"] and zeros["post_state_fingerprint"] and not zeros["observed_state_fingerprint"] and zeros["inspection_receipt_fingerprint"] and zeros["terminal_evidence_fingerprint"] and classification is None and terminal is None
    elif kind is JournalRecordTypeV2.TERMINAL_STATE:
        valid = claim is None and zeros["pre_state_fingerprint"] and zeros["post_state_fingerprint"] and not zeros["observed_state_fingerprint"] and zeros["inspection_receipt_fingerprint"] and not zeros["terminal_evidence_fingerprint"] and classification is None and terminal is not None
    if not valid:
        raise JournalV2Error()


def _construct(body, claim):
    value = object.__new__(R2JournalRecordV2)
    enums = {
        "record_type": JournalRecordTypeV2,
        "effect_classification": EffectClassificationV2,
        "terminal_state": TerminalStateV2,
    }
    for name in _FIELDS:
        item = body[name]
        if name == "execution_confirmation_claim":
            item = claim
        elif name in enums:
            item = None if item == "" else enums[name](item)
        object.__setattr__(value, name, item)
    object.__setattr__(value, "head_fingerprint", fingerprint("r2-journal-record-v2", body))
    return value
