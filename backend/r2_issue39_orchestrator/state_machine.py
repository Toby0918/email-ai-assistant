"""Fail-closed orchestration independent of paths and host APIs."""

from __future__ import annotations

from .contracts import (
    Issue39OrchestratorResultV1,
    Issue39OrchestratorStatusV1,
    Issue39ReadinessV1,
    Issue39TransactionOutcomeV1,
    Issue39TransactionStatusV1,
)
from .execution import Issue39BoundExecutionV1


_REVIEW_STEPS = (
    "current-topology",
    "host-baseline",
    "evidence-review",
)
_VERIFICATION_STEPS = (
    "evidence-verification",
    "final-audit-readiness",
)


def run_issue39_orchestrator_v1(execution):
    """Run one reviewed, single-use Issue #39 execution shell."""

    try:
        if type(execution) is not Issue39BoundExecutionV1:
            raise TypeError
        if execution._state != "READY":
            raise TypeError
        object.__setattr__(execution, "_state", "RUNNING")
        readiness = execution._read_readiness()
        if type(readiness) is not Issue39ReadinessV1:
            raise TypeError
        status = _blocked_status(readiness)
        if status is not Issue39OrchestratorStatusV1.PREFLIGHT_COMPLETE:
            object.__setattr__(execution, "_state", "COMPLETE")
            return Issue39OrchestratorResultV1(status, 0, 1, 0)
        completed = _run_preflight(execution, _REVIEW_STEPS)
        if completed != len(_REVIEW_STEPS):
            return _safe_abort(execution, completed, 0)
        if not _publish_evidence(execution):
            return _safe_abort(execution, completed, 0)
        completed += 1
        verified = _run_preflight(execution, _VERIFICATION_STEPS)
        completed += verified
        if verified != len(_VERIFICATION_STEPS):
            return _terminal_result(
                execution,
                Issue39OrchestratorStatusV1.SAFE_ABORT,
                completed,
                1,
                1,
            )
        evidence_result = Issue39OrchestratorResultV1(
            Issue39OrchestratorStatusV1.EVIDENCE_COMPLETE,
            completed,
            0,
            1,
        )
        return _run_transaction(execution, evidence_result)
    except Exception:
        try:
            object.__setattr__(execution, "_state", "FAILED")
        except Exception:
            pass
        return Issue39OrchestratorResultV1(
            Issue39OrchestratorStatusV1.INCIDENT_STOP,
            0,
            1,
            0,
        )


def _blocked_status(readiness):
    if not readiness.closure_eligible:
        return Issue39OrchestratorStatusV1.BLOCKED_CLOSURE
    if not readiness.issue38_closed:
        return Issue39OrchestratorStatusV1.BLOCKED_ISSUE38
    if not readiness.incident_stage_absent:
        return Issue39OrchestratorStatusV1.BLOCKED_INCIDENT_STAGE
    return Issue39OrchestratorStatusV1.PREFLIGHT_COMPLETE


def _run_preflight(execution, steps):
    completed = 0
    for step in steps:
        try:
            if execution._run_preflight(step) is not True:
                return completed
        except Exception:
            return completed
        completed += 1
    return completed


def _publish_evidence(execution):
    try:
        return execution._publish_evidence() is True
    except Exception:
        return False


def _safe_abort(execution, completed, host_actions):
    object.__setattr__(execution, "_state", "COMPLETE")
    return Issue39OrchestratorResultV1(
        Issue39OrchestratorStatusV1.SAFE_ABORT,
        completed,
        1,
        host_actions,
    )


def _run_transaction(execution, evidence_result):
    try:
        outcome = execution._execute_transaction()
    except Exception:
        outcome = Issue39TransactionOutcomeV1(
            Issue39TransactionStatusV1.INCIDENT_STOP,
            0,
        )
    if outcome is None:
        object.__setattr__(execution, "_state", "COMPLETE")
        return evidence_result
    if type(outcome) is not Issue39TransactionOutcomeV1:
        return _incident_result(evidence_result.accepted, 1)
    accepted = evidence_result.accepted + 1
    actions = evidence_result.host_actions + outcome.host_actions
    if outcome.status is Issue39TransactionStatusV1.SUCCEEDED:
        return _terminal_result(
            execution,
            Issue39OrchestratorStatusV1.CUTOVER_SUCCEEDED,
            accepted,
            0,
            actions,
        )
    if outcome.status is Issue39TransactionStatusV1.SAFE_ABORT:
        return _terminal_result(
            execution,
            Issue39OrchestratorStatusV1.SAFE_ABORT,
            accepted,
            1,
            actions,
        )
    if outcome.status is not Issue39TransactionStatusV1.ROLLBACK_REQUIRED:
        return _terminal_result(
            execution,
            Issue39OrchestratorStatusV1.INCIDENT_STOP,
            accepted,
            1,
            actions,
        )
    return _run_rollback(execution, accepted, actions)


def _run_rollback(execution, accepted, actions):
    if _run_preflight(execution, ("recovery-inspection",)) != 1:
        return _terminal_result(
            execution,
            Issue39OrchestratorStatusV1.INCIDENT_STOP,
            accepted,
            1,
            actions,
        )
    accepted += 1
    try:
        outcome = execution._rollback_transaction()
    except Exception:
        outcome = None
    if (
        type(outcome) is not Issue39TransactionOutcomeV1
        or outcome.status is not Issue39TransactionStatusV1.LEGACY_RECOVERED
    ):
        return _terminal_result(
            execution,
            Issue39OrchestratorStatusV1.INCIDENT_STOP,
            accepted,
            1,
            actions,
        )
    return _terminal_result(
        execution,
        Issue39OrchestratorStatusV1.LEGACY_RECOVERED,
        accepted + 1,
        0,
        actions + outcome.host_actions,
    )


def _incident_result(accepted, actions):
    return Issue39OrchestratorResultV1(
        Issue39OrchestratorStatusV1.INCIDENT_STOP,
        accepted,
        1,
        actions,
    )


def _terminal_result(execution, status, accepted, rejected, actions):
    object.__setattr__(execution, "_state", "COMPLETE")
    return Issue39OrchestratorResultV1(
        status,
        accepted,
        rejected,
        actions,
    )
