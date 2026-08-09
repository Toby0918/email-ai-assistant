"""Exact binding-owned plan for the seventeen foundation transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import ApprovedCutoverBindingV3, ProductionRoleV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import (
    canonical_json,
    fingerprint,
    is_fingerprint,
    strict_json_object,
)
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .errors import FoundationPublicationError


class FoundationBoundaryV2(str, Enum):
    LEGACY_SERVICE_QUIESCENCE = "legacy_service_quiescence"
    LEGACY_ANCHOR_RENAME = "legacy_anchor_rename"
    CONTAINER_PUBLICATION = "container_publication"
    MAIN_PUBLICATION = "main_publication"
    ACL_WHOLE_TREE_CONFORMANCE = "acl_whole_tree_conformance"
    REPOSITORY_RELOCATION = "repository_relocation"
    WORKTREE_RECONSTRUCTION = "worktree_reconstruction"


_FOUNDATION = (
    (FoundationBoundaryV2.LEGACY_SERVICE_QUIESCENCE, ProductionRoleV2.LEGACY_SERVICE),
    (FoundationBoundaryV2.LEGACY_ANCHOR_RENAME, ProductionRoleV2.LEGACY_SOURCE_ANCHOR),
    (FoundationBoundaryV2.CONTAINER_PUBLICATION, ProductionRoleV2.PROJECT_CONTAINER),
    (FoundationBoundaryV2.MAIN_PUBLICATION, ProductionRoleV2.MANAGED_MAIN),
    (FoundationBoundaryV2.ACL_WHOLE_TREE_CONFORMANCE, ProductionRoleV2.MANAGED_MAIN),
    (FoundationBoundaryV2.REPOSITORY_RELOCATION, ProductionRoleV2.REPOSITORY_ROOT),
)


@dataclass(frozen=True, slots=True, repr=False)
class R2FoundationTransitionV2:
    boundary: FoundationBoundaryV2
    ordinal: int
    owner: ProductionRoleV2
    pre_state_fingerprint: str = field(repr=False)
    post_state_fingerprint: str = field(repr=False)
    predecessor_transition_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)

    def to_mapping(self):
        return {
            "boundary": self.boundary.value,
            "ordinal": self.ordinal,
            "owner": self.owner.value,
            "pre_state_fingerprint": self.pre_state_fingerprint,
            "post_state_fingerprint": self.post_state_fingerprint,
            "predecessor_transition_fingerprint": self.predecessor_transition_fingerprint,
            "transition_instance_fingerprint": self.transition_instance_fingerprint,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2FoundationPlanV2:
    plan_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    transition_count: int
    worktree_count: int
    transitions: tuple[R2FoundationTransitionV2, ...] = field(repr=False)
    plan_fingerprint: str = field(repr=False)
    _binding: ApprovedCutoverBindingV3 = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2FoundationPlanV2 requires create()")

    @classmethod
    def create(cls, **values):
        try:
            expected = {
                "binding", "quiescence_states", "legacy_anchor_states",
                "container_states", "main_states", "whole_tree_acl_states",
                "repository_states", "worktree_states",
            }
            if set(values) != expected or type(values["binding"]) is not ApprovedCutoverBindingV3:
                raise FoundationPublicationError()
            pairs = tuple(values[name] for name in (
                "quiescence_states", "legacy_anchor_states", "container_states",
                "main_states", "whole_tree_acl_states", "repository_states",
            ))
            worktrees = values["worktree_states"]
            if type(worktrees) is not tuple or len(worktrees) != 11:
                raise FoundationPublicationError()
            return _build_plan(values["binding"], pairs + worktrees)
        except FoundationPublicationError:
            raise
        except Exception:
            raise FoundationPublicationError() from None

    @classmethod
    def from_json(cls, payload: object, *, binding: object):
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload or set(source) != {
                "plan_type", "binding_fingerprint", "final_master_binding_fingerprint",
                "transition_count", "worktree_count", "transitions", "plan_fingerprint",
            }:
                raise FoundationPublicationError()
            items = source["transitions"]
            if type(items) is not list or len(items) != 17:
                raise FoundationPublicationError()
            pairs = tuple(
                (item["pre_state_fingerprint"], item["post_state_fingerprint"])
                for item in items
            )
            result = _build_plan(binding, pairs)
            if source != result.to_mapping():
                raise FoundationPublicationError()
            return result
        except FoundationPublicationError:
            raise
        except Exception:
            raise FoundationPublicationError() from None

    def to_mapping(self):
        return {
            "plan_type": self.plan_type,
            "binding_fingerprint": self.binding_fingerprint,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "transition_count": self.transition_count,
            "worktree_count": self.worktree_count,
            "transitions": [item.to_mapping() for item in self.transitions],
            "plan_fingerprint": self.plan_fingerprint,
        }

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())

    def remaining_plan_fingerprint(self, transition: object) -> str:
        _transition_index(self, transition)
        return "0" * 64

    def committed_prefix_count(self, journal: object) -> int:
        if type(journal) is not R2TransactionJournalV2 or journal.binding_fingerprint != self.binding_fingerprint:
            raise FoundationPublicationError()
        known = {item.transition_instance_fingerprint for item in self.transitions}
        committed = tuple(
            record.transition_instance_fingerprint
            for record in journal.records
            if record.record_type is JournalRecordTypeV2.COMMIT
            and record.transition_instance_fingerprint in known
        )
        expected = tuple(
            item.transition_instance_fingerprint
            for item in self.transitions[: len(committed)]
        )
        if committed != expected or len(committed) > 17:
            raise FoundationPublicationError()
        return len(committed)

    def next_transition(self, journal: object):
        count = self.committed_prefix_count(journal)
        return None if count == 17 else self.transitions[count]


def _build_plan(binding, pairs):
    if type(binding) is not ApprovedCutoverBindingV3 or len(pairs) != 17 or any(not _valid_pair(pair) for pair in pairs):
        raise FoundationPublicationError()
    definitions = _FOUNDATION + tuple(
        (FoundationBoundaryV2.WORKTREE_RECONSTRUCTION, ProductionRoleV2.WORKTREE_TOPOLOGY)
        for _ in range(11)
    )
    transitions, predecessor = [], binding.binding_fingerprint
    for index, ((boundary, owner), pair) in enumerate(zip(definitions, pairs)):
        ordinal = index - 6 if boundary is FoundationBoundaryV2.WORKTREE_RECONSTRUCTION else 0
        body = {
            "binding_fingerprint": binding.binding_fingerprint,
            "boundary": boundary.value,
            "ordinal": ordinal,
            "owner": owner.value,
            "pre_state_fingerprint": pair[0],
            "post_state_fingerprint": pair[1],
            "predecessor_transition_fingerprint": predecessor,
        }
        current = fingerprint("r2-foundation-transition-v2", body)
        transitions.append(R2FoundationTransitionV2(
            boundary, ordinal, owner, pair[0], pair[1], predecessor, current
        ))
        predecessor = current
    body = {
        "plan_type": "R2FoundationPlanV2",
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "transition_count": 17,
        "worktree_count": 11,
        "transitions": [item.to_mapping() for item in transitions],
    }
    return _construct_plan(binding, body, tuple(transitions))


def _construct_plan(binding, body, transitions):
    value = object.__new__(R2FoundationPlanV2)
    for name, item in body.items():
        object.__setattr__(value, name, transitions if name == "transitions" else item)
    object.__setattr__(value, "plan_fingerprint", fingerprint("r2-foundation-plan-v2", body))
    object.__setattr__(value, "_binding", binding)
    return value


def _valid_pair(pair):
    return type(pair) is tuple and len(pair) == 2 and all(is_fingerprint(item) for item in pair) and pair[0] != pair[1]


def _transition_index(plan, transition):
    if type(transition) is not R2FoundationTransitionV2:
        raise FoundationPublicationError()
    matches = [index for index, item in enumerate(plan.transitions) if item == transition]
    if len(matches) != 1:
        raise FoundationPublicationError()
    return matches[0]
