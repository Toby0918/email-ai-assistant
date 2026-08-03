"""Exact prepare/publish plan for four managed units."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_foundation_publication_v2 import R2FoundationPlanV2
from backend.r2_production_binding import ApprovedCutoverBindingV2, ProductionRoleV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import (
    canonical_json,
    fingerprint,
    is_fingerprint,
    strict_json_object,
)
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .errors import ManagedUnitPublicationError


class ManagedUnitV2(str, Enum):
    RUNTIME = "runtime"
    DATABASE = "database"
    CRX = "crx"
    CONFIG = "config"


class ManagedUnitPhaseV2(str, Enum):
    PREPARE = "prepare"
    PUBLISH = "publish"


_OWNERS = {
    ManagedUnitV2.RUNTIME: ProductionRoleV2.RUNTIME,
    ManagedUnitV2.DATABASE: ProductionRoleV2.DATABASE,
    ManagedUnitV2.CRX: ProductionRoleV2.CRX,
    ManagedUnitV2.CONFIG: ProductionRoleV2.CONFIG,
}


@dataclass(frozen=True, slots=True, repr=False)
class R2ManagedUnitTransitionV2:
    unit: ManagedUnitV2
    phase: ManagedUnitPhaseV2
    owner: ProductionRoleV2
    pre_state_fingerprint: str = field(repr=False)
    post_state_fingerprint: str = field(repr=False)
    predecessor_transition_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)

    def to_mapping(self):
        return {
            "unit": self.unit.value,
            "phase": self.phase.value,
            "owner": self.owner.value,
            "pre_state_fingerprint": self.pre_state_fingerprint,
            "post_state_fingerprint": self.post_state_fingerprint,
            "predecessor_transition_fingerprint": self.predecessor_transition_fingerprint,
            "transition_instance_fingerprint": self.transition_instance_fingerprint,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ManagedUnitPlanV2:
    plan_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    foundation_plan_fingerprint: str = field(repr=False)
    transition_count: int
    unit_count: int
    transitions: tuple[R2ManagedUnitTransitionV2, ...] = field(repr=False)
    plan_fingerprint: str = field(repr=False)
    _binding: ApprovedCutoverBindingV2 = field(repr=False)
    _foundation_plan: R2FoundationPlanV2 = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ManagedUnitPlanV2 requires create()")

    @classmethod
    def create(cls, **values):
        try:
            expected = {
                "binding", "foundation_plan", "runtime_states",
                "database_states", "crx_states", "config_states",
            }
            binding, foundation = values.get("binding"), values.get("foundation_plan")
            if set(values) != expected or type(binding) is not ApprovedCutoverBindingV2 or type(foundation) is not R2FoundationPlanV2 or foundation.binding_fingerprint != binding.binding_fingerprint:
                raise ManagedUnitPublicationError()
            pairs = tuple(
                pair
                for name in ("runtime_states", "database_states", "crx_states", "config_states")
                for pair in _two_pairs(values[name])
            )
            return _build_plan(binding, foundation, pairs)
        except ManagedUnitPublicationError:
            raise
        except Exception:
            raise ManagedUnitPublicationError() from None

    @classmethod
    def from_json(cls, payload: object, *, binding: object, foundation_plan: object):
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload or set(source) != {
                "plan_type", "binding_fingerprint", "final_master_binding_fingerprint",
                "foundation_plan_fingerprint", "transition_count", "unit_count",
                "transitions", "plan_fingerprint",
            }:
                raise ManagedUnitPublicationError()
            items = source["transitions"]
            if type(items) is not list or len(items) != 8:
                raise ManagedUnitPublicationError()
            pairs = tuple((item["pre_state_fingerprint"], item["post_state_fingerprint"]) for item in items)
            result = _build_plan(binding, foundation_plan, pairs)
            if source != result.to_mapping():
                raise ManagedUnitPublicationError()
            return result
        except ManagedUnitPublicationError:
            raise
        except Exception:
            raise ManagedUnitPublicationError() from None

    def to_mapping(self):
        return {
            "plan_type": self.plan_type,
            "binding_fingerprint": self.binding_fingerprint,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "foundation_plan_fingerprint": self.foundation_plan_fingerprint,
            "transition_count": self.transition_count,
            "unit_count": self.unit_count,
            "transitions": [item.to_mapping() for item in self.transitions],
            "plan_fingerprint": self.plan_fingerprint,
        }

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())

    def remaining_plan_fingerprint(self, transition: object) -> str:
        _index(self, transition)
        return "0" * 64

    def committed_prefix_count(self, journal: object) -> int:
        if type(journal) is not R2TransactionJournalV2 or journal.binding_fingerprint != self.binding_fingerprint:
            raise ManagedUnitPublicationError()
        known = {item.transition_instance_fingerprint for item in self.transitions}
        committed = tuple(record.transition_instance_fingerprint for record in journal.records if record.record_type is JournalRecordTypeV2.COMMIT and record.transition_instance_fingerprint in known)
        expected = tuple(item.transition_instance_fingerprint for item in self.transitions[:len(committed)])
        if committed != expected or len(committed) > 8:
            raise ManagedUnitPublicationError()
        return len(committed)

    def next_transition(self, journal: object):
        if self._foundation_plan.committed_prefix_count(journal) != 17:
            raise ManagedUnitPublicationError()
        count = self.committed_prefix_count(journal)
        return None if count == 8 else self.transitions[count]


def _build_plan(binding, foundation, pairs):
    if type(binding) is not ApprovedCutoverBindingV2 or type(foundation) is not R2FoundationPlanV2 or len(pairs) != 8 or any(not _valid_pair(pair) for pair in pairs):
        raise ManagedUnitPublicationError()
    definitions = tuple((unit, phase, _OWNERS[unit]) for unit in ManagedUnitV2 for phase in ManagedUnitPhaseV2)
    predecessor = foundation.transitions[-1].transition_instance_fingerprint
    transitions = []
    for (unit, phase, owner), pair in zip(definitions, pairs):
        body = {
            "binding_fingerprint": binding.binding_fingerprint,
            "foundation_plan_fingerprint": foundation.plan_fingerprint,
            "unit": unit.value, "phase": phase.value, "owner": owner.value,
            "pre_state_fingerprint": pair[0], "post_state_fingerprint": pair[1],
            "predecessor_transition_fingerprint": predecessor,
        }
        current = fingerprint("r2-managed-unit-transition-v2", body)
        transitions.append(R2ManagedUnitTransitionV2(unit, phase, owner, pair[0], pair[1], predecessor, current))
        predecessor = current
    body = {
        "plan_type": "R2ManagedUnitPlanV2",
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "foundation_plan_fingerprint": foundation.plan_fingerprint,
        "transition_count": 8, "unit_count": 4,
        "transitions": [item.to_mapping() for item in transitions],
    }
    value = object.__new__(R2ManagedUnitPlanV2)
    for name, item in body.items():
        object.__setattr__(value, name, tuple(transitions) if name == "transitions" else item)
    object.__setattr__(value, "plan_fingerprint", fingerprint("r2-managed-unit-plan-v2", body))
    object.__setattr__(value, "_binding", binding)
    object.__setattr__(value, "_foundation_plan", foundation)
    return value


def _two_pairs(value):
    if type(value) is not tuple or len(value) != 2:
        raise ManagedUnitPublicationError()
    return value


def _valid_pair(pair):
    return type(pair) is tuple and len(pair) == 2 and all(is_fingerprint(item) for item in pair) and pair[0] != pair[1]


def _index(plan, transition):
    if type(transition) is not R2ManagedUnitTransitionV2:
        raise ManagedUnitPublicationError()
    matches = [index for index, item in enumerate(plan.transitions) if item == transition]
    if len(matches) != 1:
        raise ManagedUnitPublicationError()
    return matches[0]
