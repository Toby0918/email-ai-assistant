"""Deterministic selection and exact private evaluation metric tests."""

from __future__ import annotations

import math
import random
import unittest

from backend.private_evaluation.metrics import (
    ModelMetrics,
    ScoredOutcome,
    category_macro_f1,
    compute_model_metrics,
    flash_accepted,
    micro_recall,
    nearest_rank_p95,
    pro_qualifies,
)
from backend.private_evaluation.schema import EvaluationDatasetV1, PrivateEvaluationError
from backend.private_evaluation.selection import (
    derive_selection_key,
    select_private_cases,
)
from tests.private_evaluation_fixtures import CATEGORIES, dataset_mapping


def outcome(
    *,
    category: str = "customer_inquiry",
    predicted_category: str | None = None,
    expected_risks: tuple[str, ...] = ("delivery_risk",),
    predicted_risks: tuple[str, ...] | None = None,
    expected_actions: tuple[str, ...] = ("reply",),
    predicted_actions: tuple[str, ...] | None = None,
    useful: bool = True,
    fallback: bool = False,
    schema: bool = True,
    unsafe: bool = False,
    unsupported: bool = False,
    latency: float = 1.0,
) -> ScoredOutcome:
    return ScoredOutcome(
        expected_category=category,
        predicted_category=predicted_category or category,
        expected_risks=expected_risks,
        predicted_risks=predicted_risks if predicted_risks is not None else expected_risks,
        expected_actions=expected_actions,
        predicted_actions=predicted_actions if predicted_actions is not None else expected_actions,
        useful=useful,
        fallback=fallback,
        schema_success=schema,
        unsafe_violation=unsafe,
        unsupported_critical_fact=unsupported,
        latency_seconds=latency,
    )


def accepted_metrics(**changes: float | int) -> ModelMetrics:
    values: dict[str, float | int] = {
        "schema_success_rate": 1.0,
        "unsafe_action_count": 0,
        "unsupported_critical_fact_count": 0,
        "mandatory_risk_recall": 0.95,
        "category_macro_f1": 0.85,
        "required_action_recall": 0.90,
        "usefulness_rate": 0.90,
        "fallback_rate": 0.10,
        "p95_seconds": 12.0,
        "quality_score": 0.90,
    }
    values.update(changes)
    return ModelMetrics(**values)  # type: ignore[arg-type]


class PrivateEvaluationSelectionTests(unittest.TestCase):
    def test_selection_is_deterministic_exact_stratified_and_repr_hidden(self) -> None:
        dataset = EvaluationDatasetV1.from_mapping(dataset_mapping(240, pair_count=100))
        key = derive_selection_key(bytearray(b"K" * 32), dataset.dataset_namespace)

        first = select_private_cases(dataset, key)
        second = select_private_cases(dataset, key)

        self.assertEqual(first, second)
        self.assertEqual(len(first.selected), 200)
        self.assertEqual(first.gate, first.selected[:20])
        self.assertEqual(first.remaining_flash, first.selected[20:])
        self.assertEqual(len(first.paired), 40)
        self.assertTrue(set(first.paired).issubset(set(first.selected)))
        self.assertTrue(all(case.approvals.pro_pair is not None for case in first.paired))
        self.assertNotIn("Current request", repr(first))

    def test_selection_order_is_independent_of_dataset_input_order(self) -> None:
        original = dataset_mapping(240, pair_count=100)
        shuffled = dataset_mapping(240, pair_count=100)
        random.Random(604).shuffle(shuffled["cases"])  # type: ignore[arg-type]
        first_dataset = EvaluationDatasetV1.from_mapping(original)
        second_dataset = EvaluationDatasetV1.from_mapping(shuffled)
        key = derive_selection_key(bytearray(b"K" * 32), first_dataset.dataset_namespace)

        first = select_private_cases(first_dataset, key)
        second = select_private_cases(second_dataset, key)
        self.assertEqual(
            tuple(case.case_id for case in first.selected),
            tuple(case.case_id for case in second.selected),
        )
        self.assertEqual(
            tuple(case.case_id for case in first.paired),
            tuple(case.case_id for case in second.paired),
        )

    def test_selection_key_is_namespace_separated_and_pair_shortage_fails_before_calls(self) -> None:
        dataset = EvaluationDatasetV1.from_mapping(dataset_mapping(200, pair_count=39))
        key = derive_selection_key(bytearray(b"K" * 32), dataset.dataset_namespace)
        other = derive_selection_key(
            bytearray(b"K" * 32),
            "11111111-2222-4333-8444-555555555555",
        )
        self.assertNotEqual(key, other)
        with self.assertRaisesRegex(PrivateEvaluationError, "pair_approval_insufficient"):
            select_private_cases(dataset, key)
        with self.assertRaisesRegex(PrivateEvaluationError, "evaluation_key_unavailable"):
            derive_selection_key(bytearray(b"short"), dataset.dataset_namespace)


class PrivateEvaluationMetricTests(unittest.TestCase):
    def test_nearest_rank_p95_and_finite_validation(self) -> None:
        self.assertEqual(nearest_rank_p95([float(value) for value in range(1, 21)]), 19.0)
        self.assertEqual(nearest_rank_p95([1.25]), 1.25)
        for values in ([], [-1.0], [math.inf], [math.nan]):
            with self.subTest(values=values), self.assertRaises(PrivateEvaluationError):
                nearest_rank_p95(values)

    def test_macro_f1_uses_all_fixed_categories_and_micro_recall_uses_items(self) -> None:
        self.assertAlmostEqual(
            category_macro_f1(
                ["customer_inquiry", "order_followup"],
                ["customer_inquiry", "unknown"],
            ),
            (1.0 + 0.0 + 0.0 + 0.0 + 0.0 + 0.0 + 0.0 + 0.0 + 0.0) / len(CATEGORIES),
        )
        self.assertEqual(
            micro_recall(
                [("reply", "confirm"), ("wait",)],
                [("reply",), ("wait", "ignore")],
            ),
            2 / 3,
        )
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_strata_incomplete"):
            micro_recall([()], [()])

    def test_compute_metrics_counts_fallbacks_in_usefulness_and_quality(self) -> None:
        outcomes = [outcome() for _ in range(8)] + [
            outcome(useful=False, fallback=True, schema=False),
            outcome(useful=False, fallback=True, schema=False),
        ]
        metrics = compute_model_metrics(outcomes)
        self.assertEqual(metrics.schema_success_rate, 0.8)
        self.assertEqual(metrics.usefulness_rate, 0.8)
        self.assertEqual(metrics.fallback_rate, 0.2)
        self.assertAlmostEqual(
            metrics.quality_score,
            sum((metrics.mandatory_risk_recall, metrics.category_macro_f1,
                 metrics.required_action_recall, metrics.usefulness_rate)) / 4,
        )

    def test_flash_thresholds_accept_exact_boundaries_and_reject_each_failure(self) -> None:
        self.assertTrue(flash_accepted(accepted_metrics()))
        failures = (
            {"schema_success_rate": 0.999}, {"unsafe_action_count": 1},
            {"unsupported_critical_fact_count": 1}, {"mandatory_risk_recall": 0.949},
            {"category_macro_f1": 0.849}, {"required_action_recall": 0.899},
            {"usefulness_rate": 0.899}, {"fallback_rate": 0.101},
            {"p95_seconds": 12.001},
        )
        for change in failures:
            with self.subTest(change=change):
                self.assertFalse(flash_accepted(accepted_metrics(**change)))

    def test_pro_requires_point_zero_five_quality_and_no_regression(self) -> None:
        flash = accepted_metrics(quality_score=0.80, mandatory_risk_recall=0.96)
        self.assertFalse(pro_qualifies(flash, accepted_metrics(
            quality_score=0.849, mandatory_risk_recall=0.96
        )))
        self.assertTrue(pro_qualifies(flash, accepted_metrics(
            quality_score=0.85, mandatory_risk_recall=0.96
        )))
        failures = (
            {"schema_success_rate": 0.99, "quality_score": 0.90},
            {"unsafe_action_count": 1, "quality_score": 0.90},
            {"unsupported_critical_fact_count": 1, "quality_score": 0.90},
            {"mandatory_risk_recall": 0.959, "quality_score": 0.90},
            {"p95_seconds": 12.001, "quality_score": 0.90},
        )
        for change in failures:
            with self.subTest(change=change):
                self.assertFalse(pro_qualifies(flash, accepted_metrics(**change)))

    def test_pro_quality_delta_uses_the_exact_point_zero_five_boundary(self) -> None:
        flash = accepted_metrics(quality_score=0.0)
        below = math.nextafter(0.05, 0.0)
        exact = 0.05
        above = math.nextafter(0.05, math.inf)
        self.assertFalse(pro_qualifies(flash, accepted_metrics(quality_score=below)))
        self.assertTrue(pro_qualifies(flash, accepted_metrics(quality_score=exact)))
        self.assertTrue(pro_qualifies(flash, accepted_metrics(quality_score=above)))


if __name__ == "__main__":
    unittest.main()
