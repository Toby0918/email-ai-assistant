"""Fresh-process action evidence and aggregate two-start receipt."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV3
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from backend.r2_transaction_journal_v2._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2

from .errors import TwoStartValidationError
from .plan import R2TwoStartValidationPlanV2, R2ValidationTransitionV2, ValidationBoundaryV2


_ACTION_FIELDS = (
    "binding_fingerprint", "transition_instance_fingerprint", "claim_fingerprint",
    "prior_journal_head_fingerprint", "observed_state_fingerprint",
    "run_identity_fingerprint", "actor_identity_fingerprint",
    "service_nonce_fingerprint", "evidence_fingerprint", "host_mutations",
    "analysis_count", "database_row_count", "provider_attempts",
    "read_only_checks", "observed_at_epoch", "expires_at_epoch",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ValidationActionEvidenceV2:
    binding_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    claim_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    observed_state_fingerprint: str = field(repr=False)
    run_identity_fingerprint: str = field(repr=False)
    actor_identity_fingerprint: str = field(repr=False)
    service_nonce_fingerprint: str = field(repr=False)
    evidence_fingerprint: str = field(repr=False)
    host_mutations: int
    analysis_count: int
    database_row_count: int
    provider_attempts: int
    read_only_checks: int
    observed_at_epoch: int
    expires_at_epoch: int
    action_evidence_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ValidationActionEvidenceV2 requires create()")

    @classmethod
    def create(cls, *, binding, transition, **values):
        try:
            if type(binding) is not ApprovedCutoverBindingV3 or type(transition) is not R2ValidationTransitionV2 or set(values) != set(_ACTION_FIELDS) - {"binding_fingerprint", "transition_instance_fingerprint"}:
                raise TwoStartValidationError()
            body = {"binding_fingerprint": binding.binding_fingerprint, "transition_instance_fingerprint": transition.transition_instance_fingerprint, **values}
            if not all(is_fingerprint(body[name]) for name in _ACTION_FIELDS if name.endswith("fingerprint")) or any(type(body[name]) is not int or body[name] < 0 for name in ("host_mutations", "analysis_count", "database_row_count", "provider_attempts", "read_only_checks", "observed_at_epoch", "expires_at_epoch")) or body["observed_state_fingerprint"] != transition.post_state_fingerprint:
                raise TwoStartValidationError()
            return _action(body)
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None

    @classmethod
    def from_mapping(cls, value, *, binding, transition):
        try:
            if type(value) is not dict or set(value) != {*_ACTION_FIELDS, "action_evidence_fingerprint"}:
                raise TwoStartValidationError()
            result = cls.create(binding=binding, transition=transition, **{name: value[name] for name in _ACTION_FIELDS if name not in {"binding_fingerprint", "transition_instance_fingerprint"}})
            if value != result.to_mapping():
                raise TwoStartValidationError()
            return result
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None

    def to_mapping(self):
        return {**{name: getattr(self, name) for name in _ACTION_FIELDS}, "action_evidence_fingerprint": self.action_evidence_fingerprint}


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2TwoStartValidationReceiptV2:
    receipt_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    plan_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    analysis_count: int
    database_write_count: int
    provider_attempts: int
    start_a_run_fingerprint: str = field(repr=False)
    start_b_run_fingerprint: str = field(repr=False)
    start_b_nonce_fingerprint: str = field(repr=False)
    stopped_audit_actor_fingerprint: str = field(repr=False)
    final_audit_actor_fingerprint: str = field(repr=False)
    stopped_audit_observed_at_epoch: int
    stopped_audit_expires_at_epoch: int
    final_audit_observed_at_epoch: int
    final_audit_expires_at_epoch: int
    action_evidence: tuple[R2ValidationActionEvidenceV2, ...] = field(repr=False)
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2TwoStartValidationReceiptV2 requires create()")

    @classmethod
    def create(cls, *, binding, plan, journal, action_evidence):
        try:
            evidence = tuple(action_evidence)
            _validate(binding, plan, journal, evidence)
            stopped, final = evidence[4], evidence[6]
            body = {
                "receipt_type": "R2TwoStartValidationReceiptV2",
                "binding_fingerprint": binding.binding_fingerprint,
                "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
                "plan_fingerprint": plan.plan_fingerprint,
                "journal_head_fingerprint": journal.current_head_fingerprint,
                "analysis_count": 1, "database_write_count": 1, "provider_attempts": 0,
                "start_a_run_fingerprint": evidence[0].run_identity_fingerprint,
                "start_b_run_fingerprint": evidence[5].run_identity_fingerprint,
                "start_b_nonce_fingerprint": evidence[5].service_nonce_fingerprint,
                "stopped_audit_actor_fingerprint": stopped.actor_identity_fingerprint,
                "final_audit_actor_fingerprint": final.actor_identity_fingerprint,
                "stopped_audit_observed_at_epoch": stopped.observed_at_epoch,
                "stopped_audit_expires_at_epoch": stopped.expires_at_epoch,
                "final_audit_observed_at_epoch": final.observed_at_epoch,
                "final_audit_expires_at_epoch": final.expires_at_epoch,
                "action_evidence": [item.to_mapping() for item in evidence],
            }
            return _receipt(body, evidence)
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None

    @classmethod
    def from_json(cls, payload, *, binding, plan, journal):
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload or type(source.get("action_evidence")) is not list or len(source["action_evidence"]) != 7:
                raise TwoStartValidationError()
            evidence = tuple(R2ValidationActionEvidenceV2.from_mapping(item, binding=binding, transition=transition) for item, transition in zip(source["action_evidence"], plan.transitions))
            result = cls.create(binding=binding, plan=plan, journal=journal, action_evidence=evidence)
            if source != result.to_mapping():
                raise TwoStartValidationError()
            return result
        except TwoStartValidationError:
            raise
        except Exception:
            raise TwoStartValidationError() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in self.__dataclass_fields__ if name not in {"receipt_fingerprint", "action_evidence"}}
        body["action_evidence"] = [item.to_mapping() for item in self.action_evidence]
        return {**body, "receipt_fingerprint": self.receipt_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _validate(binding, plan, journal, evidence):
    if type(binding) is not ApprovedCutoverBindingV3 or type(plan) is not R2TwoStartValidationPlanV2 or type(journal) is not R2TransactionJournalV2 or len(evidence) != 7 or plan.committed_prefix_count(journal) != 7:
        raise TwoStartValidationError()
    expected_metrics = ((1,0,0,0,0),(1,1,1,0,0),(1,0,0,0,0),(0,0,1,0,1),(0,0,0,0,1),(1,0,0,0,0),(0,0,0,0,1))
    claims = tuple(record for record in journal.records if record.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM and record.transition_instance_fingerprint in {item.transition_instance_fingerprint for item in plan.transitions})
    if len(claims) != 7:
        raise TwoStartValidationError()
    for item, transition, record, metrics in zip(evidence, plan.transitions, claims, expected_metrics):
        observed = (item.host_mutations, item.analysis_count, item.database_row_count, item.provider_attempts, item.read_only_checks)
        if type(item) is not R2ValidationActionEvidenceV2 or item.binding_fingerprint != binding.binding_fingerprint or item.transition_instance_fingerprint != transition.transition_instance_fingerprint or item.claim_fingerprint != record.execution_confirmation_claim.claim_fingerprint or item.prior_journal_head_fingerprint != record.execution_confirmation_claim.prior_journal_head_fingerprint or observed != metrics:
            raise TwoStartValidationError()
    start_a, start_b = evidence[0].run_identity_fingerprint, evidence[5].run_identity_fingerprint
    if start_a == start_b or any(item.run_identity_fingerprint != start_a for item in evidence[:5]) or any(item.run_identity_fingerprint != start_b for item in evidence[5:]) or len({evidence[0].service_nonce_fingerprint, evidence[5].service_nonce_fingerprint}) != 2:
        raise TwoStartValidationError()
    if evidence[4].actor_identity_fingerprint in {evidence[0].actor_identity_fingerprint, evidence[5].actor_identity_fingerprint, evidence[6].actor_identity_fingerprint} or evidence[6].actor_identity_fingerprint in {evidence[0].actor_identity_fingerprint, evidence[5].actor_identity_fingerprint}:
        raise TwoStartValidationError()
    for index in (4, 6):
        item, claim = evidence[index], claims[index].execution_confirmation_claim
        if item.expires_at_epoch - item.observed_at_epoch != 300 or not item.observed_at_epoch <= claim.confirmed_at_epoch < item.expires_at_epoch:
            raise TwoStartValidationError()


def _action(body):
    value = object.__new__(R2ValidationActionEvidenceV2)
    for name, item in body.items(): object.__setattr__(value, name, item)
    object.__setattr__(value, "action_evidence_fingerprint", fingerprint("r2-validation-action-evidence-v2", body))
    return value


def _receipt(body, evidence):
    value = object.__new__(R2TwoStartValidationReceiptV2)
    for name, item in body.items(): object.__setattr__(value, name, evidence if name == "action_evidence" else item)
    object.__setattr__(value, "receipt_fingerprint", fingerprint("r2-two-start-validation-receipt-v2", body))
    return value
