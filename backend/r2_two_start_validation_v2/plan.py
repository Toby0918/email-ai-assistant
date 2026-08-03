"""Exact seven-transition two-start validation plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_managed_unit_publication_v2 import R2ManagedUnitPlanV2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    ProductionCommandV2,
    ProductionRoleV2,
    production_action_fingerprint_v2,
)
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .errors import TwoStartValidationError


class ValidationBoundaryV2(str, Enum):
    START_A = "start_a"
    RULE_FALLBACK_ANALYSIS = "rule_fallback_analysis"
    STOP_A = "stop_a"
    DATABASE_PROOF = "database_proof"
    STOPPED_LAYOUT_AUDIT = "stopped_layout_audit"
    START_B = "start_b"
    FINAL_RUNNING_AUDIT = "final_running_audit"


_DEFINITIONS = (
    (ValidationBoundaryV2.START_A, ProductionCommandV2.EXECUTE, ProductionRoleV2.MANAGED_SERVICE),
    (ValidationBoundaryV2.RULE_FALLBACK_ANALYSIS, ProductionCommandV2.EXECUTE, ProductionRoleV2.DATABASE),
    (ValidationBoundaryV2.STOP_A, ProductionCommandV2.EXECUTE, ProductionRoleV2.MANAGED_SERVICE),
    (ValidationBoundaryV2.DATABASE_PROOF, ProductionCommandV2.EVIDENCE_VERIFICATION, ProductionRoleV2.DATABASE),
    (ValidationBoundaryV2.STOPPED_LAYOUT_AUDIT, ProductionCommandV2.FINAL_AUDIT_READINESS, ProductionRoleV2.STOPPED_LAYOUT_AUDIT),
    (ValidationBoundaryV2.START_B, ProductionCommandV2.EXECUTE, ProductionRoleV2.MANAGED_SERVICE),
    (ValidationBoundaryV2.FINAL_RUNNING_AUDIT, ProductionCommandV2.FINAL_AUDIT_READINESS, ProductionRoleV2.FINAL_RUNNING_AUDIT),
)


@dataclass(frozen=True, slots=True, repr=False)
class R2ValidationTransitionV2:
    boundary: ValidationBoundaryV2
    command: ProductionCommandV2
    owner: ProductionRoleV2
    pre_state_fingerprint: str = field(repr=False)
    post_state_fingerprint: str = field(repr=False)
    predecessor_transition_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)

    def to_mapping(self):
        return {
            "boundary": self.boundary.value, "command": self.command.value,
            "owner": self.owner.value,
            "pre_state_fingerprint": self.pre_state_fingerprint,
            "post_state_fingerprint": self.post_state_fingerprint,
            "predecessor_transition_fingerprint": self.predecessor_transition_fingerprint,
            "transition_instance_fingerprint": self.transition_instance_fingerprint,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2TwoStartValidationPlanV2:
    plan_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    managed_plan_fingerprint: str = field(repr=False)
    approved_identities_fingerprint: str = field(repr=False)
    transition_count: int
    transitions: tuple[R2ValidationTransitionV2, ...] = field(repr=False)
    terminal_transition_instance_fingerprint: str = field(repr=False)
    plan_fingerprint: str = field(repr=False)
    _binding: ApprovedCutoverBindingV2 = field(repr=False)
    _managed_plan: R2ManagedUnitPlanV2 = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2TwoStartValidationPlanV2 requires create()")

    @classmethod
    def create(cls, *, binding, managed_plan, transition_states, approved_identities_fingerprint):
        try:
            if type(binding) is not ApprovedCutoverBindingV2 or type(managed_plan) is not R2ManagedUnitPlanV2 or managed_plan.binding_fingerprint != binding.binding_fingerprint or type(transition_states) is not tuple or len(transition_states) != 7 or any(not _pair(item) for item in transition_states) or not is_fingerprint(approved_identities_fingerprint):
                raise TwoStartValidationError()
            return _build(binding, managed_plan, transition_states, approved_identities_fingerprint)
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None

    @classmethod
    def from_json(cls, payload: object, *, binding: object, managed_plan: object):
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload or set(source) != {
                "plan_type", "binding_fingerprint", "final_master_binding_fingerprint",
                "managed_plan_fingerprint", "approved_identities_fingerprint",
                "transition_count", "transitions", "terminal_transition_instance_fingerprint",
                "plan_fingerprint",
            }:
                raise TwoStartValidationError()
            pairs = tuple((item["pre_state_fingerprint"], item["post_state_fingerprint"]) for item in source["transitions"])
            result = _build(binding, managed_plan, pairs, source["approved_identities_fingerprint"])
            if source != result.to_mapping():
                raise TwoStartValidationError()
            return result
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None

    def to_mapping(self):
        return {
            "plan_type": self.plan_type,
            "binding_fingerprint": self.binding_fingerprint,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "managed_plan_fingerprint": self.managed_plan_fingerprint,
            "approved_identities_fingerprint": self.approved_identities_fingerprint,
            "transition_count": self.transition_count,
            "transitions": [item.to_mapping() for item in self.transitions],
            "terminal_transition_instance_fingerprint": self.terminal_transition_instance_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
        }

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())

    def committed_prefix_count(self, journal):
        if type(journal) is not R2TransactionJournalV2 or self._managed_plan.committed_prefix_count(journal) != 8:
            raise TwoStartValidationError()
        known = {item.transition_instance_fingerprint for item in self.transitions}
        committed = tuple(record.transition_instance_fingerprint for record in journal.records if record.record_type is JournalRecordTypeV2.COMMIT and record.transition_instance_fingerprint in known)
        expected = tuple(item.transition_instance_fingerprint for item in self.transitions[:len(committed)])
        if committed != expected or len(committed) > 7:
            raise TwoStartValidationError()
        return len(committed)

    def next_transition(self, journal):
        count = self.committed_prefix_count(journal)
        return None if count == 7 else self.transitions[count]


def lifecycle_action_fingerprint_v2(*, binding, plan, command, journal_head_fingerprint, transition_instance_fingerprint):
    try:
        if type(binding) is not ApprovedCutoverBindingV2 or type(plan) is not R2TwoStartValidationPlanV2 or plan.binding_fingerprint != binding.binding_fingerprint or type(command) is not ProductionCommandV2 or not is_fingerprint(journal_head_fingerprint) or transition_instance_fingerprint not in {item.transition_instance_fingerprint for item in plan.transitions} | {plan.terminal_transition_instance_fingerprint}:
            raise TwoStartValidationError()
        subject = fingerprint("r2-lifecycle-action-subject-v2", {"plan_fingerprint": plan.plan_fingerprint, "journal_head_fingerprint": journal_head_fingerprint, "transition_instance_fingerprint": transition_instance_fingerprint})
        return production_action_fingerprint_v2(binding, command, subject_fingerprint=subject)
    except TwoStartValidationError:
        raise
    except Exception:
        raise TwoStartValidationError() from None


def _build(binding, managed, pairs, identities):
    if type(managed) is not R2ManagedUnitPlanV2 or len(pairs) != 7:
        raise TwoStartValidationError()
    predecessor, transitions = managed.transitions[-1].transition_instance_fingerprint, []
    for (boundary, command, owner), pair in zip(_DEFINITIONS, pairs):
        body = {"binding_fingerprint": binding.binding_fingerprint, "managed_plan_fingerprint": managed.plan_fingerprint, "boundary": boundary.value, "command": command.value, "owner": owner.value, "pre_state_fingerprint": pair[0], "post_state_fingerprint": pair[1], "predecessor_transition_fingerprint": predecessor}
        current = fingerprint("r2-validation-transition-v2", body)
        transitions.append(R2ValidationTransitionV2(boundary, command, owner, pair[0], pair[1], predecessor, current))
        predecessor = current
    core = {"binding_fingerprint": binding.binding_fingerprint, "managed_plan_fingerprint": managed.plan_fingerprint, "approved_identities_fingerprint": identities, "transitions": [item.to_mapping() for item in transitions]}
    terminal = fingerprint("r2-cutover-success-transition-v2", core)
    body = {"plan_type": "R2TwoStartValidationPlanV2", "binding_fingerprint": binding.binding_fingerprint, "final_master_binding_fingerprint": binding.final_master_binding_fingerprint, "managed_plan_fingerprint": managed.plan_fingerprint, "approved_identities_fingerprint": identities, "transition_count": 7, "transitions": core["transitions"], "terminal_transition_instance_fingerprint": terminal}
    value = object.__new__(R2TwoStartValidationPlanV2)
    for name, item in body.items():
        object.__setattr__(value, name, tuple(transitions) if name == "transitions" else item)
    object.__setattr__(value, "plan_fingerprint", fingerprint("r2-two-start-plan-v2", body))
    object.__setattr__(value, "_binding", binding)
    object.__setattr__(value, "_managed_plan", managed)
    return value


def _pair(value):
    return type(value) is tuple and len(value) == 2 and all(is_fingerprint(item) for item in value) and value[0] != value[1]
