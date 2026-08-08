"""Journal-derived LIFO reverse plan for R2 rollback."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_foundation_publication_v2 import R2FoundationPlanV2
from backend.r2_managed_unit_publication_v2 import R2ManagedUnitPlanV2
from backend.r2_production_binding import ApprovedCutoverBindingV3, ProductionRoleV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import (
    canonical_json,
    fingerprint,
    strict_json_object,
)
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2
from backend.r2_two_start_validation_v2 import R2TwoStartValidationPlanV2

from .errors import RollbackRecoveryError


class RollbackBoundaryV2(str, Enum):
    PRESERVE_FAILED_CONTAINER = "preserve_failed_container"
    REVERSE_COMMITTED_FORWARD = "reverse_committed_forward"


@dataclass(frozen=True, slots=True, repr=False)
class R2RollbackTransitionV2:
    boundary: RollbackBoundaryV2
    ordinal: int
    owner: ProductionRoleV2
    source_boundary: str
    source_transition_fingerprint: str = field(repr=False)
    source_commit_head_fingerprint: str = field(repr=False)
    pre_state_fingerprint: str = field(repr=False)
    post_state_fingerprint: str = field(repr=False)
    remaining_plan_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)

    def to_mapping(self):
        return {
            "boundary": self.boundary.value,
            "ordinal": self.ordinal,
            "owner": self.owner.value,
            "source_boundary": self.source_boundary,
            "source_transition_fingerprint": self.source_transition_fingerprint,
            "source_commit_head_fingerprint": self.source_commit_head_fingerprint,
            "pre_state_fingerprint": self.pre_state_fingerprint,
            "post_state_fingerprint": self.post_state_fingerprint,
            "remaining_plan_fingerprint": self.remaining_plan_fingerprint,
            "transition_instance_fingerprint": self.transition_instance_fingerprint,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2RollbackPlanV2:
    plan_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    forward_journal_head_fingerprint: str = field(repr=False)
    forward_record_count: int
    forward_commit_count: int
    transition_count: int
    transitions: tuple[R2RollbackTransitionV2, ...] = field(repr=False)
    remaining_plan_fingerprints: tuple[str, ...] = field(repr=False)
    terminal_plan_fingerprint: str = field(repr=False)
    terminal_transition_instance_fingerprint: str = field(repr=False)
    plan_fingerprint: str = field(repr=False)
    _binding: ApprovedCutoverBindingV3 = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2RollbackPlanV2 requires derive()")

    @classmethod
    def derive(cls, **values):
        try:
            required = {
                "binding", "foundation_plan", "managed_plan",
                "validation_plan", "journal",
            }
            if set(values) != required:
                raise RollbackRecoveryError()
            return _derive(**values)
        except RollbackRecoveryError:
            raise
        except Exception:
            raise RollbackRecoveryError() from None

    @classmethod
    def from_json(cls, payload, **values):
        try:
            source = strict_json_object(payload)
            result = cls.derive(**values)
            if canonical_json(source) != payload or source != result.to_mapping():
                raise RollbackRecoveryError()
            return result
        except RollbackRecoveryError:
            raise
        except Exception:
            raise RollbackRecoveryError() from None

    def to_mapping(self):
        return {
            "plan_type": self.plan_type,
            "binding_fingerprint": self.binding_fingerprint,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "forward_journal_head_fingerprint": self.forward_journal_head_fingerprint,
            "forward_record_count": self.forward_record_count,
            "forward_commit_count": self.forward_commit_count,
            "transition_count": self.transition_count,
            "transitions": [item.to_mapping() for item in self.transitions],
            "remaining_plan_fingerprints": list(self.remaining_plan_fingerprints),
            "terminal_plan_fingerprint": self.terminal_plan_fingerprint,
            "terminal_transition_instance_fingerprint": self.terminal_transition_instance_fingerprint,
            "plan_fingerprint": self.plan_fingerprint,
        }

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())

    def completed_prefix_count(self, journal):
        _require_extension(self, journal)
        known = {item.transition_instance_fingerprint for item in self.transitions}
        commits = tuple(
            record.transition_instance_fingerprint
            for record in journal.records[self.forward_record_count:]
            if record.record_type is JournalRecordTypeV2.COMMIT
        )
        expected = tuple(item.transition_instance_fingerprint for item in self.transitions[:len(commits)])
        if any(item not in known for item in commits) or commits != expected:
            raise RollbackRecoveryError()
        return len(commits)

    def next_transition(self, journal):
        count = self.completed_prefix_count(journal)
        return None if count == self.transition_count else self.transitions[count]


def _derive(binding, foundation_plan, managed_plan, validation_plan, journal):
    _require_inputs(binding, foundation_plan, managed_plan, validation_plan, journal)
    forward = foundation_plan.transitions + managed_plan.transitions + validation_plan.transitions
    by_fingerprint = {item.transition_instance_fingerprint: item for item in forward}
    commits = tuple(
        record for record in journal.records
        if record.record_type is JournalRecordTypeV2.COMMIT
        and record.transition_instance_fingerprint in by_fingerprint
    )
    all_commits = tuple(
        record for record in journal.records
        if record.record_type is JournalRecordTypeV2.COMMIT
    )
    expected = tuple(item.transition_instance_fingerprint for item in forward[:len(commits)])
    actual = tuple(item.transition_instance_fingerprint for item in commits)
    if not commits or commits != all_commits or actual != expected or len(commits) > len(forward):
        raise RollbackRecoveryError()
    definitions = [_preservation_definition(binding, journal)]
    definitions.extend(_reverse_definition(by_fingerprint[record.transition_instance_fingerprint], record) for record in reversed(commits))
    return _build(binding, journal, commits, tuple(definitions))


def _require_inputs(binding, foundation, managed, validation, journal):
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(foundation) is not R2FoundationPlanV2
        or type(managed) is not R2ManagedUnitPlanV2
        or type(validation) is not R2TwoStartValidationPlanV2
        or type(journal) is not R2TransactionJournalV2
        or any(item.binding_fingerprint != binding.binding_fingerprint for item in (foundation, managed, validation, journal))
        or managed.foundation_plan_fingerprint != foundation.plan_fingerprint
        or validation.managed_plan_fingerprint != managed.plan_fingerprint
        or any(record.record_type is JournalRecordTypeV2.TERMINAL_STATE for record in journal.records)
    ):
        raise RollbackRecoveryError()


def _preservation_definition(binding, journal):
    source = fingerprint("r2-failed-container-source-v2", {"binding": binding.binding_fingerprint})
    before = fingerprint("r2-failed-container-unsealed-v2", {"journal": journal.current_head_fingerprint})
    after = fingerprint("r2-failed-container-preserved-v2", {"before": before})
    return RollbackBoundaryV2.PRESERVE_FAILED_CONTAINER, ProductionRoleV2.FAILED_CONTAINER, "failed_container", source, journal.current_head_fingerprint, before, after


def _reverse_definition(transition, commit):
    boundary = getattr(transition, "boundary", getattr(transition, "unit", None))
    phase = getattr(transition, "phase", None)
    name = boundary.value + ("_" + phase.value if phase is not None else "")
    return RollbackBoundaryV2.REVERSE_COMMITTED_FORWARD, transition.owner, name, transition.transition_instance_fingerprint, commit.head_fingerprint, transition.post_state_fingerprint, transition.pre_state_fingerprint


def _build(binding, journal, commits, definitions):
    source_chain = tuple(item[3] for item in definitions)
    transitions = []
    for index, definition in enumerate(definitions):
        remaining = fingerprint("r2-remaining-reverse-plan-v2", {"binding": binding.binding_fingerprint, "forward_head": journal.current_head_fingerprint, "remaining_sources": source_chain[index:]})
        body = {"binding_fingerprint": binding.binding_fingerprint, "ordinal": index, "boundary": definition[0].value, "owner": definition[1].value, "source_boundary": definition[2], "source_transition_fingerprint": definition[3], "source_commit_head_fingerprint": definition[4], "pre_state_fingerprint": definition[5], "post_state_fingerprint": definition[6], "remaining_plan_fingerprint": remaining}
        current = fingerprint("r2-rollback-transition-v2", body)
        transitions.append(R2RollbackTransitionV2(definition[0], index, definition[1], definition[2], definition[3], definition[4], definition[5], definition[6], remaining, current))
    return _construct_plan(binding, journal, commits, tuple(transitions))


def _construct_plan(binding, journal, commits, transitions):
    remaining = tuple(item.remaining_plan_fingerprint for item in transitions)
    terminal_plan = fingerprint("r2-terminal-reverse-plan-v2", {"binding": binding.binding_fingerprint, "forward_head": journal.current_head_fingerprint, "completed_sources": tuple(item.source_transition_fingerprint for item in transitions)})
    terminal = fingerprint("r2-legacy-restored-transition-v2", {"terminal_plan": terminal_plan})
    body = {"plan_type": "R2RollbackPlanV2", "binding_fingerprint": binding.binding_fingerprint, "final_master_binding_fingerprint": binding.final_master_binding_fingerprint, "forward_journal_head_fingerprint": journal.current_head_fingerprint, "forward_record_count": len(journal.records), "forward_commit_count": len(commits), "transition_count": len(transitions), "transitions": [item.to_mapping() for item in transitions], "remaining_plan_fingerprints": list(remaining), "terminal_plan_fingerprint": terminal_plan, "terminal_transition_instance_fingerprint": terminal}
    value = object.__new__(R2RollbackPlanV2)
    for name, item in body.items():
        object.__setattr__(value, name, transitions if name == "transitions" else remaining if name == "remaining_plan_fingerprints" else item)
    object.__setattr__(value, "plan_fingerprint", fingerprint("r2-rollback-plan-v2", body))
    object.__setattr__(value, "_binding", binding)
    return value


def _require_extension(plan, journal):
    if type(journal) is not R2TransactionJournalV2 or journal.binding_fingerprint != plan.binding_fingerprint or len(journal.records) < plan.forward_record_count:
        raise RollbackRecoveryError()
    base = journal.records[plan.forward_record_count - 1].head_fingerprint
    if base != plan.forward_journal_head_fingerprint:
        raise RollbackRecoveryError()
    allowed = {item.transition_instance_fingerprint for item in plan.transitions} | {plan.terminal_transition_instance_fingerprint}
    if any(record.transition_instance_fingerprint not in allowed for record in journal.records[plan.forward_record_count:]):
        raise RollbackRecoveryError()
