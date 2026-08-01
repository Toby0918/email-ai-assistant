"""Canonical content-free R2 journal receipt vocabulary."""

from __future__ import annotations

from dataclasses import dataclass, field

from .approved_binding import ApprovedCutoverBindingV1
from .canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .errors import CompositionContractError
from .r2_types import (
    FinalCutoverOutcome,
    JournalFactKind,
    PendingEffectState,
    R2JournalBoundary,
)


_ERROR = "R2_CUTOVER_RECEIPT_INVALID"
_TYPE = "R2CutoverReceiptV1"
_NONE = "not_applicable"
_BODY_KEYS = (
    "receipt_type",
    "binding_fingerprint",
    "boundary",
    "fact_kind",
    "prior_receipt_fingerprint",
    "observation_fingerprint",
    "journal_owner_fingerprint",
    "prior_journal_head_fingerprint",
    "journal_head_fingerprint",
    "pending_effect_state",
    "final_outcome",
    "accepted",
    "rejected",
    "worktrees",
    "provider_attempts",
)
_CREATE_KEYS = (
    "binding",
    "boundary",
    "fact_kind",
    "prior_receipt_fingerprint",
    "observation_fingerprint",
    "journal_owner_fingerprint",
    "prior_journal_head_fingerprint",
    "journal_head_fingerprint",
    "pending_effect_state",
    "final_outcome",
    "accepted",
    "rejected",
    "worktrees",
    "provider_attempts",
)
_WORKTREE_BOUNDARIES = {
    R2JournalBoundary.WORKTREE_RECONSTRUCTION,
    R2JournalBoundary.WORKTREE_ROLLBACK,
}
_TERMINAL_OUTCOMES = {
    R2JournalBoundary.CUTOVER_SUCCESS: FinalCutoverOutcome.CUTOVER_SUCCESS,
    R2JournalBoundary.LEGACY_FLAT_LAYOUT_RESTORED: (
        FinalCutoverOutcome.LEGACY_FLAT_LAYOUT_RESTORED
    ),
    R2JournalBoundary.INCIDENT_STOP: FinalCutoverOutcome.INCIDENT_STOP,
}


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2CutoverReceiptV1:
    receipt_type: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    boundary: R2JournalBoundary = field(repr=False)
    fact_kind: JournalFactKind = field(repr=False)
    prior_receipt_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    pending_effect_state: PendingEffectState | None = field(repr=False)
    final_outcome: FinalCutoverOutcome | None = field(repr=False)
    accepted: int
    rejected: int
    worktrees: int
    provider_attempts: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2CutoverReceiptV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> R2CutoverReceiptV1:
        body = _validated_body(values)
        return _construct(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        binding: ApprovedCutoverBindingV1,
    ) -> R2CutoverReceiptV1:
        try:
            source = strict_json_object(payload, code=_ERROR)
            if canonical_json(source) != payload:
                raise CompositionContractError(_ERROR)
            _exact_mapping(source, (*_BODY_KEYS, "receipt_fingerprint"))
            values = {
                "binding": binding,
                "boundary": R2JournalBoundary(source["boundary"]),
                "fact_kind": JournalFactKind(source["fact_kind"]),
                "prior_receipt_fingerprint": source["prior_receipt_fingerprint"],
                "observation_fingerprint": source["observation_fingerprint"],
                "journal_owner_fingerprint": source["journal_owner_fingerprint"],
                "prior_journal_head_fingerprint": source[
                    "prior_journal_head_fingerprint"
                ],
                "journal_head_fingerprint": source["journal_head_fingerprint"],
                "pending_effect_state": _optional_pending(
                    source["pending_effect_state"]
                ),
                "final_outcome": _optional_outcome(source["final_outcome"]),
                "accepted": source["accepted"],
                "rejected": source["rejected"],
                "worktrees": source["worktrees"],
                "provider_attempts": source["provider_attempts"],
            }
            body = _validated_body(values)
            if (
                source["receipt_type"] != _TYPE
                or source["binding_fingerprint"] != binding.binding_fingerprint
                or source["receipt_fingerprint"]
                != fingerprint("r2-cutover-receipt-v1", body)
            ):
                raise CompositionContractError(_ERROR)
            return _construct(body)
        except CompositionContractError:
            raise
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def to_mapping(self) -> dict[str, object]:
        return {
            "receipt_type": self.receipt_type,
            "binding_fingerprint": self.binding_fingerprint,
            "boundary": self.boundary.value,
            "fact_kind": self.fact_kind.value,
            "prior_receipt_fingerprint": self.prior_receipt_fingerprint,
            "observation_fingerprint": self.observation_fingerprint,
            "journal_owner_fingerprint": self.journal_owner_fingerprint,
            "prior_journal_head_fingerprint": self.prior_journal_head_fingerprint,
            "journal_head_fingerprint": self.journal_head_fingerprint,
            "pending_effect_state": (
                self.pending_effect_state.value
                if self.pending_effect_state is not None
                else _NONE
            ),
            "final_outcome": (
                self.final_outcome.value
                if self.final_outcome is not None
                else _NONE
            ),
            "accepted": self.accepted,
            "rejected": self.rejected,
            "worktrees": self.worktrees,
            "provider_attempts": self.provider_attempts,
            "receipt_fingerprint": self.receipt_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _validated_body(values: dict[str, object]) -> dict[str, object]:
    try:
        parts = _validated_components(values)
        return _receipt_body(values, *parts)
    except Exception:
        raise CompositionContractError(_ERROR) from None


def _validated_components(values):
    if set(values) != set(_CREATE_KEYS):
        raise ValueError
    binding = values["binding"]
    boundary = values["boundary"]
    fact_kind = values["fact_kind"]
    pending = values["pending_effect_state"]
    outcome = values["final_outcome"]
    if (
        type(binding) is not ApprovedCutoverBindingV1
        or type(boundary) is not R2JournalBoundary
        or type(fact_kind) is not JournalFactKind
    ):
        raise ValueError
    fingerprints = tuple(
        values[name]
        for name in (
            "prior_receipt_fingerprint",
            "observation_fingerprint",
            "journal_owner_fingerprint",
            "prior_journal_head_fingerprint",
            "journal_head_fingerprint",
        )
    )
    counts = tuple(
        values[name]
        for name in ("accepted", "rejected", "worktrees", "provider_attempts")
    )
    if (
        not all(is_fingerprint(item) for item in fingerprints)
        or any(type(item) is not int or item < 0 for item in counts)
        or values["accepted"] + values["rejected"] != 1
        or values["provider_attempts"] != 0
        or values["worktrees"]
        != (11 if boundary in _WORKTREE_BOUNDARIES else 0)
    ):
        raise ValueError
    _require_classification(boundary, fact_kind, pending)
    _require_outcome(boundary, fact_kind, outcome)
    return binding, boundary, fact_kind, pending, outcome


def _receipt_body(values, binding, boundary, fact_kind, pending, outcome):
    return {
        "receipt_type": _TYPE,
        "binding_fingerprint": binding.binding_fingerprint,
        "boundary": boundary.value,
        "fact_kind": fact_kind.value,
        "prior_receipt_fingerprint": values["prior_receipt_fingerprint"],
        "observation_fingerprint": values["observation_fingerprint"],
        "journal_owner_fingerprint": values["journal_owner_fingerprint"],
        "prior_journal_head_fingerprint": values[
            "prior_journal_head_fingerprint"
        ],
        "journal_head_fingerprint": values["journal_head_fingerprint"],
        "pending_effect_state": pending.value if pending is not None else _NONE,
        "final_outcome": outcome.value if outcome is not None else _NONE,
        "accepted": values["accepted"],
        "rejected": values["rejected"],
        "worktrees": values["worktrees"],
        "provider_attempts": values["provider_attempts"],
    }


def _require_classification(boundary, fact_kind, pending) -> None:
    required = (
        boundary is R2JournalBoundary.PENDING_EFFECT_CLASSIFICATION
        and fact_kind is JournalFactKind.PENDING_CLASSIFIED
    )
    if required != (type(pending) is PendingEffectState):
        raise ValueError


def _require_outcome(boundary, fact_kind, outcome) -> None:
    expected = _TERMINAL_OUTCOMES.get(boundary)
    if expected is None:
        if outcome is not None or fact_kind is JournalFactKind.FINAL_OUTCOME:
            raise ValueError
        return
    if fact_kind is not JournalFactKind.FINAL_OUTCOME or outcome is not expected:
        raise ValueError


def _construct(body: dict[str, object]) -> R2CutoverReceiptV1:
    value = object.__new__(R2CutoverReceiptV1)
    for name in _BODY_KEYS:
        item = body[name]
        if name == "boundary":
            item = R2JournalBoundary(item)
        elif name == "fact_kind":
            item = JournalFactKind(item)
        elif name == "pending_effect_state":
            item = _optional_pending(item)
        elif name == "final_outcome":
            item = _optional_outcome(item)
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "receipt_fingerprint",
        fingerprint("r2-cutover-receipt-v1", body),
    )
    return value


def _optional_pending(value: object) -> PendingEffectState | None:
    return None if value == _NONE else PendingEffectState(value)


def _optional_outcome(value: object) -> FinalCutoverOutcome | None:
    return None if value == _NONE else FinalCutoverOutcome(value)


def _exact_mapping(value, expected_keys) -> None:
    if (
        type(value) is not dict
        or any(type(key) is not str for key in value)
        or set(value) != set(expected_keys)
    ):
        raise CompositionContractError(_ERROR)
