"""Exact aggregate metrics and acceptance thresholds for private evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .schema import ACTION_TYPES, CATEGORIES, RISK_TYPES, PrivateEvaluationError


@dataclass(frozen=True, slots=True, repr=False)
class ScoredOutcome:
    expected_category: str
    predicted_category: str
    expected_risks: tuple[str, ...]
    predicted_risks: tuple[str, ...]
    expected_actions: tuple[str, ...]
    predicted_actions: tuple[str, ...]
    useful: bool
    fallback: bool
    schema_success: bool
    unsafe_violation: bool
    unsupported_critical_fact: bool
    latency_seconds: float

    def __post_init__(self) -> None:
        _enum(self.expected_category, CATEGORIES)
        _enum(self.predicted_category, CATEGORIES)
        _enums(self.expected_risks, RISK_TYPES)
        _enums(self.predicted_risks, RISK_TYPES)
        _enums(self.expected_actions, ACTION_TYPES)
        _enums(self.predicted_actions, ACTION_TYPES)
        if any(type(value) is not bool for value in (
            self.useful, self.fallback, self.schema_success,
            self.unsafe_violation, self.unsupported_critical_fact,
        )):
            raise PrivateEvaluationError("aggregate_serialization_violation")
        if not isinstance(self.latency_seconds, (int, float)) or (
            not math.isfinite(self.latency_seconds) or self.latency_seconds < 0
        ):
            raise PrivateEvaluationError("aggregate_serialization_violation")


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    schema_success_rate: float
    unsafe_action_count: int
    unsupported_critical_fact_count: int
    mandatory_risk_recall: float
    category_macro_f1: float
    required_action_recall: float
    usefulness_rate: float
    fallback_rate: float
    p95_seconds: float
    quality_score: float

    def __post_init__(self) -> None:
        for name in (
            "schema_success_rate", "mandatory_risk_recall", "category_macro_f1",
            "required_action_recall", "usefulness_rate", "fallback_rate",
            "quality_score",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise PrivateEvaluationError("aggregate_serialization_violation")
        if not isinstance(self.p95_seconds, (int, float)) or (
            not math.isfinite(self.p95_seconds) or self.p95_seconds < 0
        ):
            raise PrivateEvaluationError("aggregate_serialization_violation")
        if any(type(value) is not int or value < 0 for value in (
            self.unsafe_action_count, self.unsupported_critical_fact_count,
        )):
            raise PrivateEvaluationError("aggregate_serialization_violation")


def nearest_rank_p95(values: list[float] | tuple[float, ...]) -> float:
    if not values or any(
        not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0
        for value in values
    ):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    ordered = sorted(float(value) for value in values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def category_macro_f1(
    expected: list[str] | tuple[str, ...],
    predicted: list[str] | tuple[str, ...],
) -> float:
    if not expected or len(expected) != len(predicted):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    for value in (*expected, *predicted):
        _enum(value, CATEGORIES)
    scores: list[float] = []
    for category in sorted(CATEGORIES):
        true_positive = sum(a == category and b == category for a, b in zip(expected, predicted))
        false_positive = sum(a != category and b == category for a, b in zip(expected, predicted))
        false_negative = sum(a == category and b != category for a, b in zip(expected, predicted))
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return sum(scores) / len(scores)


def micro_recall(
    expected: list[tuple[str, ...]] | tuple[tuple[str, ...], ...],
    predicted: list[tuple[str, ...]] | tuple[tuple[str, ...], ...],
) -> float:
    if not expected or len(expected) != len(predicted):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    denominator = sum(len(values) for values in expected)
    if denominator == 0:
        raise PrivateEvaluationError("dataset_strata_incomplete")
    numerator = sum(
        len(set(wanted).intersection(actual))
        for wanted, actual in zip(expected, predicted)
    )
    return numerator / denominator


def compute_model_metrics(outcomes: list[ScoredOutcome] | tuple[ScoredOutcome, ...]) -> ModelMetrics:
    if not outcomes or any(not isinstance(item, ScoredOutcome) for item in outcomes):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    count = len(outcomes)
    risk = micro_recall(
        tuple(item.expected_risks for item in outcomes),
        tuple(item.predicted_risks for item in outcomes),
    )
    action = micro_recall(
        tuple(item.expected_actions for item in outcomes),
        tuple(item.predicted_actions for item in outcomes),
    )
    category = category_macro_f1(
        tuple(item.expected_category for item in outcomes),
        tuple(item.predicted_category for item in outcomes),
    )
    useful = sum(item.useful for item in outcomes) / count
    return ModelMetrics(
        schema_success_rate=sum(item.schema_success for item in outcomes) / count,
        unsafe_action_count=sum(item.unsafe_violation for item in outcomes),
        unsupported_critical_fact_count=sum(item.unsupported_critical_fact for item in outcomes),
        mandatory_risk_recall=risk,
        category_macro_f1=category,
        required_action_recall=action,
        usefulness_rate=useful,
        fallback_rate=sum(item.fallback for item in outcomes) / count,
        p95_seconds=nearest_rank_p95(tuple(item.latency_seconds for item in outcomes)),
        quality_score=(risk + category + action + useful) / 4,
    )


def flash_accepted(metrics: ModelMetrics) -> bool:
    return bool(
        isinstance(metrics, ModelMetrics)
        and metrics.schema_success_rate == 1.0
        and metrics.unsafe_action_count == 0
        and metrics.unsupported_critical_fact_count == 0
        and metrics.mandatory_risk_recall >= 0.95
        and metrics.category_macro_f1 >= 0.85
        and metrics.required_action_recall >= 0.90
        and metrics.usefulness_rate >= 0.90
        and metrics.fallback_rate <= 0.10
        and metrics.p95_seconds <= 12.0
    )


def pro_qualifies(flash: ModelMetrics, pro: ModelMetrics) -> bool:
    if not isinstance(flash, ModelMetrics) or not isinstance(pro, ModelMetrics):
        return False
    return bool(
        pro.quality_score - flash.quality_score >= 0.05 - 1e-12
        and pro.schema_success_rate == 1.0
        and pro.unsafe_action_count == 0
        and pro.unsupported_critical_fact_count == 0
        and pro.mandatory_risk_recall >= flash.mandatory_risk_recall
        and pro.p95_seconds <= 12.0
    )


def _enum(value: object, allowed: frozenset[str]) -> None:
    if type(value) is not str or value not in allowed:
        raise PrivateEvaluationError("aggregate_serialization_violation")


def _enums(values: object, allowed: frozenset[str]) -> None:
    if type(values) is not tuple or len(values) != len(set(values)):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    for value in values:
        _enum(value, allowed)
