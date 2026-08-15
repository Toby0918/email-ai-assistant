"""Test-owned synthetic binder for Issue #39 orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import (
    Issue39ReadinessV1,
    Issue39TransactionOutcomeV1,
    Issue39TransactionStatusV1,
)
from .execution import _allocate_execution_v1


@dataclass(slots=True)
class SyntheticIssue39ScenarioV1:
    closure_eligible: bool
    issue38_closed: bool
    incident_stage_absent: bool
    fail_preflight_at: str | None = None
    evidence_publication_succeeds: bool = True
    transaction_outcome: str | None = None
    rollback_succeeds: bool = True
    _evidence_retained: bool = field(default=False, repr=False)
    _calls: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        *,
        closure_eligible,
        issue38_closed,
        incident_stage_absent,
        fail_preflight_at=None,
        evidence_publication_succeeds=True,
        transaction_outcome=None,
        rollback_succeeds=True,
    ):
        readiness = Issue39ReadinessV1(
            closure_eligible,
            issue38_closed,
            incident_stage_absent,
        )
        if (
            type(evidence_publication_succeeds) is not bool
            or transaction_outcome
            not in {None, "success", "safe_abort", "rollback_required", "incident_stop"}
            or type(rollback_succeeds) is not bool
        ):
            raise TypeError("R2_ISSUE39_TEST_BINDING_INVALID")
        return cls(
            closure_eligible=readiness.closure_eligible,
            issue38_closed=readiness.issue38_closed,
            incident_stage_absent=readiness.incident_stage_absent,
            fail_preflight_at=fail_preflight_at,
            evidence_publication_succeeds=evidence_publication_succeeds,
            transaction_outcome=transaction_outcome,
            rollback_succeeds=rollback_succeeds,
        )

    @property
    def observed_calls(self) -> tuple[str, ...]:
        return tuple(self._calls)

    def read_readiness(self) -> Issue39ReadinessV1:
        self._calls.append("readiness")
        return Issue39ReadinessV1(
            self.closure_eligible,
            self.issue38_closed,
            self.incident_stage_absent,
        )

    def run_preflight(self, step: str) -> bool:
        self._calls.append(step)
        return step != self.fail_preflight_at

    @property
    def evidence_retained(self) -> bool:
        return self._evidence_retained

    def publish_evidence(self) -> bool:
        self._calls.append("evidence-publication")
        if not self.evidence_publication_succeeds:
            return False
        self._evidence_retained = True
        return True

    def execute_transaction(self):
        if self.transaction_outcome is None:
            return None
        self._calls.append("transaction-execute")
        values = {
            "success": (
                Issue39TransactionStatusV1.SUCCEEDED,
                1,
            ),
            "safe_abort": (
                Issue39TransactionStatusV1.SAFE_ABORT,
                0,
            ),
            "rollback_required": (
                Issue39TransactionStatusV1.ROLLBACK_REQUIRED,
                3,
            ),
            "incident_stop": (
                Issue39TransactionStatusV1.INCIDENT_STOP,
                0,
            ),
        }
        return Issue39TransactionOutcomeV1(*values[self.transaction_outcome])

    def rollback_transaction(self):
        self._calls.append("transaction-rollback")
        status = (
            Issue39TransactionStatusV1.LEGACY_RECOVERED
            if self.rollback_succeeds
            else Issue39TransactionStatusV1.INCIDENT_STOP
        )
        return Issue39TransactionOutcomeV1(status, 2 if self.rollback_succeeds else 0)


def bind_synthetic_issue39_execution_v1(*, scenario):
    if type(scenario) is not SyntheticIssue39ScenarioV1:
        raise TypeError("R2_ISSUE39_TEST_BINDING_INVALID")
    return _allocate_execution_v1(
        read_readiness=scenario.read_readiness,
        run_preflight=scenario.run_preflight,
        publish_evidence=scenario.publish_evidence,
        execute_transaction=scenario.execute_transaction,
        rollback_transaction=scenario.rollback_transaction,
        state="READY",
        synthetic=True,
    )
