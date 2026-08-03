"""Content-free reverse-effect and legacy-restoration evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV2, ProductionCommandV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import fingerprint, is_fingerprint
from backend.r2_transaction_process.production_v2 import TransactionActionCompletionV2

from .errors import RollbackRecoveryError
from .plan import R2RollbackPlanV2, R2RollbackTransitionV2


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2RollbackEffectEvidenceV2:
    binding_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    action_completion_fingerprint: str = field(repr=False)
    claim_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    remaining_plan_fingerprint: str = field(repr=False)
    observed_state_fingerprint: str = field(repr=False)
    retained_objects_fingerprint: str = field(repr=False)
    failed_container_retained: bool
    partial_objects_retained: bool
    destructive_operations: int
    host_mutations: int
    evidence_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2RollbackEffectEvidenceV2 requires create()")

    @classmethod
    def create(cls, *, binding, transition, action_completion, **values):
        try:
            _require_effect(binding, transition, action_completion, values)
            body = {"binding_fingerprint": binding.binding_fingerprint, "transition_instance_fingerprint": transition.transition_instance_fingerprint, "action_completion_fingerprint": action_completion.completion_fingerprint, "claim_fingerprint": action_completion.claim_fingerprint, "prior_journal_head_fingerprint": action_completion.prior_journal_head_fingerprint, "remaining_plan_fingerprint": action_completion.remaining_reverse_plan_fingerprint, "observed_state_fingerprint": values["observed_state_fingerprint"], "retained_objects_fingerprint": values["retained_objects_fingerprint"], "failed_container_retained": True, "partial_objects_retained": True, "destructive_operations": 0, "host_mutations": 1}
            return _allocate(cls, body, "evidence_fingerprint", "r2-rollback-effect-evidence-v2")
        except RollbackRecoveryError:
            raise
        except Exception:
            raise RollbackRecoveryError() from None


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2LegacyRestorationEvidenceV2:
    binding_fingerprint: str = field(repr=False)
    plan_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    legacy_topology_fingerprint: str = field(repr=False)
    legacy_service_health_fingerprint: str = field(repr=False)
    legacy_acl_audit_fingerprint: str = field(repr=False)
    git_worktree_audit_fingerprint: str = field(repr=False)
    original_identity_count: int
    git_relationship_count: int
    retained_failed_container_count: int
    destructive_operations: int
    provider_attempts: int
    legacy_analysis_writes: int
    independent_read_count: int
    evidence_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2LegacyRestorationEvidenceV2 requires create()")

    @classmethod
    def create(cls, *, binding, plan, journal, **values):
        try:
            _require_legacy(binding, plan, journal, values)
            body = {"binding_fingerprint": binding.binding_fingerprint, "plan_fingerprint": plan.plan_fingerprint, "journal_head_fingerprint": journal.current_head_fingerprint, **values}
            return _allocate(cls, body, "evidence_fingerprint", "r2-legacy-restoration-evidence-v2")
        except RollbackRecoveryError:
            raise
        except Exception:
            raise RollbackRecoveryError() from None


def _require_effect(binding, transition, completion, values):
    required = {"observed_state_fingerprint", "retained_objects_fingerprint", "failed_container_retained", "partial_objects_retained", "destructive_operations"}
    if type(binding) is not ApprovedCutoverBindingV2 or type(transition) is not R2RollbackTransitionV2 or type(completion) is not TransactionActionCompletionV2 or set(values) != required:
        raise RollbackRecoveryError()
    if completion.binding_fingerprint != binding.binding_fingerprint or completion.command is not ProductionCommandV2.ROLLBACK or completion.transition_instance_fingerprint != transition.transition_instance_fingerprint or completion.remaining_reverse_plan_fingerprint != transition.remaining_plan_fingerprint or completion.mutations != 1:
        raise RollbackRecoveryError()
    if values["observed_state_fingerprint"] != transition.post_state_fingerprint or not is_fingerprint(values["retained_objects_fingerprint"]) or values["failed_container_retained"] is not True or values["partial_objects_retained"] is not True or values["destructive_operations"] != 0:
        raise RollbackRecoveryError()


def _require_legacy(binding, plan, journal, values):
    required = {"legacy_topology_fingerprint", "legacy_service_health_fingerprint", "legacy_acl_audit_fingerprint", "git_worktree_audit_fingerprint", "original_identity_count", "git_relationship_count", "retained_failed_container_count", "destructive_operations", "provider_attempts", "legacy_analysis_writes", "independent_read_count"}
    if type(binding) is not ApprovedCutoverBindingV2 or type(plan) is not R2RollbackPlanV2 or type(journal) is not R2TransactionJournalV2 or set(values) != required or plan.binding_fingerprint != binding.binding_fingerprint or plan.completed_prefix_count(journal) != plan.transition_count:
        raise RollbackRecoveryError()
    if not all(is_fingerprint(values[name]) for name in required if name.endswith("fingerprint")):
        raise RollbackRecoveryError()
    counts = tuple(values[name] for name in required if not name.endswith("fingerprint"))
    if any(type(item) is not int for item in counts) or (values["original_identity_count"], values["git_relationship_count"], values["retained_failed_container_count"], values["destructive_operations"], values["provider_attempts"], values["legacy_analysis_writes"], values["independent_read_count"]) != (22, 12, 1, 0, 0, 0, 2):
        raise RollbackRecoveryError()


def _allocate(cls, body, name, domain):
    value = object.__new__(cls)
    for key, item in body.items():
        object.__setattr__(value, key, item)
    object.__setattr__(value, name, fingerprint(domain, body))
    return value
