"""Closed Issue #39 orchestration behavior without real host access."""

from __future__ import annotations

import unittest

from backend.r2_issue39_orchestrator import (
    Issue39OrchestratorStatusV1,
)
from backend.r2_issue39_orchestrator.state_machine import (
    run_issue39_orchestrator_v1,
)
from backend.r2_issue39_orchestrator.testing import (
    SyntheticIssue39ScenarioV1,
    bind_synthetic_issue39_execution_v1,
)


class Issue39OrchestratorTests(unittest.TestCase):
    def test_missing_closure_stops_before_any_host_action(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=False,
            issue38_closed=True,
            incident_stage_absent=True,
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(
            result.status,
            Issue39OrchestratorStatusV1.BLOCKED_CLOSURE,
        )
        self.assertEqual(result.counts(), (0, 1, 0))
        self.assertEqual(scenario.observed_calls, ("readiness",))

    def test_open_issue38_stops_before_any_host_action(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=False,
            incident_stage_absent=True,
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(
            result.status,
            Issue39OrchestratorStatusV1.BLOCKED_ISSUE38,
        )
        self.assertEqual(result.counts(), (0, 1, 0))
        self.assertEqual(scenario.observed_calls, ("readiness",))

    def test_unresolved_incident_stage_stops_before_any_host_action(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=False,
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(
            result.status,
            Issue39OrchestratorStatusV1.BLOCKED_INCIDENT_STAGE,
        )
        self.assertEqual(result.counts(), (0, 1, 0))
        self.assertEqual(scenario.observed_calls, ("readiness",))

    def test_ready_execution_interleaves_evidence_in_fixed_order(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(
            result.status,
            Issue39OrchestratorStatusV1.EVIDENCE_COMPLETE,
        )
        self.assertEqual(result.counts(), (6, 0, 1))
        self.assertEqual(
            scenario.observed_calls,
            (
                "readiness",
                "current-topology",
                "host-baseline",
                "evidence-review",
                "evidence-publication",
                "evidence-verification",
                "final-audit-readiness",
            ),
        )

    def test_preflight_failure_is_safe_abort_without_later_calls(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
            fail_preflight_at="evidence-review",
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(result.status, Issue39OrchestratorStatusV1.SAFE_ABORT)
        self.assertEqual(result.counts(), (2, 1, 0))
        self.assertEqual(
            scenario.observed_calls,
            (
                "readiness",
                "current-topology",
                "host-baseline",
                "evidence-review",
            ),
        )

    def test_evidence_publication_failure_is_safe_abort(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
            evidence_publication_succeeds=False,
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(result.status, Issue39OrchestratorStatusV1.SAFE_ABORT)
        self.assertEqual(result.counts(), (3, 1, 0))
        self.assertEqual(
            scenario.observed_calls,
            (
                "readiness",
                "current-topology",
                "host-baseline",
                "evidence-review",
                "evidence-publication",
            ),
        )

    def test_verification_failure_retains_published_evidence(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
            fail_preflight_at="evidence-verification",
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(result.status, Issue39OrchestratorStatusV1.SAFE_ABORT)
        self.assertEqual(result.counts(), (4, 1, 1))
        self.assertTrue(scenario.evidence_retained)

    def test_success_runs_one_forward_transaction_after_fresh_evidence(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
            transaction_outcome="success",
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(
            result.status,
            Issue39OrchestratorStatusV1.CUTOVER_SUCCEEDED,
        )
        self.assertEqual(result.counts(), (7, 0, 2))
        self.assertEqual(scenario.observed_calls[-1], "transaction-execute")

    def test_rollback_required_uses_recovery_inspection_then_rollback(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
            transaction_outcome="rollback_required",
            rollback_succeeds=True,
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(
            result.status,
            Issue39OrchestratorStatusV1.LEGACY_RECOVERED,
        )
        self.assertEqual(result.counts(), (9, 0, 6))
        self.assertEqual(
            scenario.observed_calls[-3:],
            (
                "transaction-execute",
                "recovery-inspection",
                "transaction-rollback",
            ),
        )

    def test_incident_stop_never_attempts_rollback(self) -> None:
        scenario = SyntheticIssue39ScenarioV1.create(
            closure_eligible=True,
            issue38_closed=True,
            incident_stage_absent=True,
            transaction_outcome="incident_stop",
        )
        execution = bind_synthetic_issue39_execution_v1(scenario=scenario)

        result = run_issue39_orchestrator_v1(execution)

        self.assertIs(result.status, Issue39OrchestratorStatusV1.INCIDENT_STOP)
        self.assertEqual(scenario.observed_calls[-1], "transaction-execute")
        self.assertNotIn("transaction-rollback", scenario.observed_calls)


if __name__ == "__main__":
    unittest.main()
