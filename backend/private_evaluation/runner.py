"""Sequential zero-retry private evaluation through the production Task 5 gates."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from backend.email_agent.analysis_budget import AnalysisBudget
from backend.email_agent.analysis_schema import validate_analysis_result
from backend.email_agent.deepseek_analysis_schema import (
    parse_deepseek_analysis_v1,
    validate_envelope_evidence,
)
from backend.email_agent.model_grounding import find_grounding_violations
from backend.email_agent.model_result_safety import merge_deepseek_analysis_v1
from backend.email_agent.model_text_safety import validate_public_language
from backend.email_agent.private_context_gate import (
    PrivateContextFallbackCode,
    PrivateModelContext,
    PrivateModelRequest,
    build_private_model_context,
    provider_output_is_private_safe,
)
from backend.email_agent.prompt_context import DEEPSEEK_SYSTEM_PROMPT

from .case_context import build_case_context, provider_prose_is_safe
from .metrics import ScoredOutcome, compute_model_metrics, flash_accepted, nearest_rank_p95, pro_qualifies
from .reporting import FLASH_MODEL, PRO_MODEL, AggregateReport, make_report
from .schema import DeidentifiedEmailV1, EvaluationCaseV1, PrivateEvaluationError
from .selection import EvaluationSelection


_clock = time.monotonic


@dataclass(frozen=True, slots=True, repr=False)
class UsefulnessJudgeView:
    input_subject: str = field(repr=False)
    input_thread_text: str = field(repr=False)
    analysis_summary: str = field(repr=False)
    reply_subject: str = field(repr=False)
    reply_body: str = field(repr=False)
    category: str
    risk_types: tuple[str, ...]
    action_types: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _Attempt:
    public: dict[str, object] = field(repr=False)
    latency: float
    provider_called: bool
    schema_success: bool
    error_code: str | None
    unsafe: bool = False
    unsupported: bool = False


@dataclass(slots=True, repr=False)
class _RunState:
    errors: Counter[str] = field(default_factory=Counter, repr=False)
    flash_results: dict[EvaluationCaseV1, ScoredOutcome] = field(default_factory=dict, repr=False)
    pro_results: list[ScoredOutcome] = field(default_factory=list, repr=False)
    flash_attempted: int = 0
    pro_attempted: int = 0


def run_private_evaluation(
    selection: EvaluationSelection,
    *,
    flash_client: Callable[..., str] | None,
    pro_client: Callable[..., str] | None,
    usefulness_judge: Callable[[UsefulnessJudgeView], bool] | None,
    runtime_cards: tuple[object, ...] = (),
) -> AggregateReport:
    preflight = _preflight(selection, flash_client, pro_client, usefulness_judge, runtime_cards)
    if preflight is not None:
        return preflight
    assert flash_client is not None and pro_client is not None and usefulness_judge is not None
    state = _RunState()
    stopped = _run_flash_gate(state, selection, flash_client, usefulness_judge, runtime_cards)
    if stopped is not None:
        return stopped
    stopped = _run_flash_remaining(state, selection, flash_client, usefulness_judge, runtime_cards)
    if stopped is not None:
        return stopped
    flash_metrics = compute_model_metrics(tuple(state.flash_results.values()))
    if not flash_accepted(flash_metrics):
        return make_report(
            status="flash_complete", decision="flash_rejected",
            flash_attempted=state.flash_attempted,
            flash_completed=len(state.flash_results),
            flash_metrics=flash_metrics, errors=state.errors,
        )
    pair_flash_metrics = compute_model_metrics(
        tuple(state.flash_results[case] for case in selection.paired)
    )
    stopped = _run_pro(state, selection, pro_client, usefulness_judge, runtime_cards)
    if stopped is not None:
        return stopped
    pro_metrics = compute_model_metrics(tuple(state.pro_results))
    decision = (
        "pro_candidate_qualified"
        if pro_qualifies(pair_flash_metrics, pro_metrics)
        else "retain_flash"
    )
    return make_report(
        status="comparison_complete", decision=decision,
        flash_attempted=state.flash_attempted, flash_completed=len(state.flash_results),
        pro_attempted=state.pro_attempted, pro_completed=len(state.pro_results),
        flash_metrics=flash_metrics, pair_flash_metrics=pair_flash_metrics,
        pro_metrics=pro_metrics, errors=state.errors,
    )


def _run_flash_gate(state, selection, client, judge, cards):
    for case in selection.gate:
        attempt = _attempt_case(case, FLASH_MODEL, client, cards)
        state.flash_attempted += int(attempt.provider_called)
        if attempt.error_code is not None:
            state.errors[attempt.error_code] += 1
            return _state_stopped(state)
        outcome = _judge_and_score(case, attempt, judge)
        if isinstance(outcome, str):
            state.errors[outcome] += 1
            return _state_stopped(state)
        state.flash_results[case] = outcome
    if nearest_rank_p95(tuple(
        item.latency_seconds for item in state.flash_results.values()
    )) > 12.0:
        state.errors["latency_gate_failed"] += 1
        return _state_stopped(state)
    return None


def _run_flash_remaining(state, selection, client, judge, cards):
    for case in selection.remaining_flash:
        attempt = _attempt_case(case, FLASH_MODEL, client, cards)
        state.flash_attempted += int(attempt.provider_called)
        stopped = _record_non_gate(state, case, attempt, judge, state.flash_results)
        if stopped is not None:
            return stopped
    return None


def _run_pro(state, selection, client, judge, cards):
    for case in selection.paired:
        attempt = _attempt_case(case, PRO_MODEL, client, cards)
        state.pro_attempted += int(attempt.provider_called)
        stopped = _record_non_gate(state, case, attempt, judge, state.pro_results)
        if stopped is not None:
            return stopped
    return None


def _record_non_gate(state, case, attempt, judge, target):
    if attempt.error_code is not None and not attempt.provider_called:
        state.errors[attempt.error_code] += 1
        return _state_stopped(state)
    if attempt.error_code is not None:
        state.errors[attempt.error_code] += 1
        state.errors["fallback_observed"] += 1
    outcome = _judge_and_score(case, attempt, judge)
    if isinstance(outcome, str):
        state.errors[outcome] += 1
        return _state_stopped(state)
    if isinstance(target, dict):
        target[case] = outcome
    else:
        target.append(outcome)
    return None


def _preflight(selection, flash_client, pro_client, judge, runtime_cards):
    if not isinstance(selection, EvaluationSelection):
        return make_report(status="blocked", decision="not_evaluated", errors={"dataset_schema_invalid": 1})
    if type(runtime_cards) is not tuple:
        return make_report(status="blocked", decision="not_evaluated", errors={"privacy_violation": 1})
    if not callable(flash_client) or not callable(pro_client):
        return make_report(
            status="blocked", decision="not_evaluated",
            errors={"provider_configuration_unavailable": 1},
        )
    if not callable(judge):
        return make_report(
            status="blocked", decision="not_evaluated",
            errors={"human_judge_unavailable": 1},
        )
    return None


def _attempt_case(case, model, client, runtime_cards) -> _Attempt:
    context = build_case_context(case)
    started = _clock()
    budget = AnalysisBudget(deadline=started + 13.0, _clock=_clock)
    private = build_private_model_context(
        PrivateModelRequest(context.prompt, ()), context.fallback, runtime_cards, budget
    )
    if private is PrivateContextFallbackCode.SAFETY:
        return _failed(context.fallback, started, False, False, "privacy_violation")
    if not isinstance(private, PrivateModelContext):
        return _failed(context.fallback, started, False, False, "provider_error")
    try:
        raw = client(
            private.text, system_prompt=DEEPSEEK_SYSTEM_PROMPT, model=model,
            response_format="json_object", temperature=0, stream=False,
            max_tokens=2400, thinking=False, max_retries=0, timeout_seconds=10.0,
        )
    except Exception:
        return _failed(context.fallback, started, True, False, "provider_error")
    if not provider_output_is_private_safe(raw):
        return _failed(context.fallback, started, True, False, "privacy_violation")
    try:
        envelope = parse_deepseek_analysis_v1(raw)
    except Exception:
        return _failed(context.fallback, started, True, False, "schema_violation")
    try:
        evidence = validate_envelope_evidence(envelope, context.sources)
        violations = find_grounding_violations(envelope, evidence, context.sources)
    except Exception:
        return _failed(context.fallback, started, True, True, "grounding_violation", unsupported=True)
    if violations:
        return _failed(context.fallback, started, True, True, "grounding_violation", unsupported=True)
    if not provider_prose_is_safe(envelope):
        return _failed(context.fallback, started, True, True, "safety_violation", unsafe=True)
    merged = merge_deepseek_analysis_v1(
        envelope, fallback=context.fallback, sources=context.sources,
        timeline=context.timeline, evidence=evidence,
    )
    if not merged.used_model:
        return _failed(context.fallback, started, True, True, "safety_violation", unsafe=True)
    try:
        validate_analysis_result(merged.analysis)
        validate_public_language(merged.analysis)
    except Exception:
        return _failed(context.fallback, started, True, True, "safety_violation", unsafe=True)
    return _Attempt(merged.analysis, _latency(started), True, True, None)


def _failed(fallback, started, called, schema, code, *, unsafe=False, unsupported=False):
    return _Attempt(
        fallback, _latency(started), called, schema, code,
        unsafe=unsafe, unsupported=unsupported,
    )


def _latency(started: float) -> float:
    elapsed = _clock() - started
    if not isinstance(elapsed, (int, float)) or elapsed < 0:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    return float(elapsed)


def _judge_and_score(case, attempt, judge):
    view = _judge_view(case.deidentified_email, attempt.public)
    try:
        useful = judge(view)
    except Exception:
        return "human_judge_failed"
    if type(useful) is not bool:
        return "human_judge_failed"
    expected = case.expected
    public = attempt.public
    try:
        return ScoredOutcome(
            expected.category, public["category"], expected.mandatory_risk_types,
            tuple(item["type"] for item in public["risk_flags"]),
            expected.required_action_types,
            tuple(item["type"] for item in public["suggested_actions"]),
            useful, attempt.error_code is not None, attempt.schema_success,
            attempt.unsafe, attempt.unsupported, attempt.latency,
        )
    except Exception:
        return "aggregate_serialization_violation"


def _judge_view(email: DeidentifiedEmailV1, public: dict[str, object]) -> UsefulnessJudgeView:
    draft = public["reply_draft"]
    return UsefulnessJudgeView(
        email.subject, email.thread_text, public["summary"],
        draft["subject"], draft["body"], public["category"],
        tuple(item["type"] for item in public["risk_flags"]),
        tuple(item["type"] for item in public["suggested_actions"]),
    )


def _state_stopped(state):
    return make_report(
        status="gate_stopped", decision="gate_failed",
        flash_attempted=state.flash_attempted,
        flash_completed=len(state.flash_results),
        pro_attempted=state.pro_attempted,
        pro_completed=len(state.pro_results), errors=state.errors,
    )
