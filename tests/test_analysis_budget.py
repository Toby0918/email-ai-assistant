import unittest

from backend.email_agent import analysis_budget
from backend.email_agent.analysis_budget import AnalysisBudget


class AnalysisBudgetTests(unittest.TestCase):
    def test_multimodal_budget_constants_are_exact(self) -> None:
        self.assertEqual(analysis_budget.BACKEND_TARGET_SECONDS, 55.0)
        self.assertEqual(analysis_budget.PROVIDER_MAX_SECONDS, 35.0)
        self.assertEqual(analysis_budget.DEEPSEEK_PROVIDER_MAX_SECONDS, 10.0)
        self.assertEqual(
            getattr(analysis_budget, "TEXT_FALLBACK_MIN_REMAINING_SECONDS", None),
            12.0,
        )
        self.assertEqual(analysis_budget.RESPONSE_MARGIN_SECONDS, 5.0)

    def test_start_uses_one_55_second_monotonic_budget(self) -> None:
        now = [100.0]

        budget = AnalysisBudget.start(clock=lambda: now[0])

        self.assertEqual(budget.deadline, 155.0)
        self.assertEqual(budget.remaining_seconds(), 55.0)
        self.assertEqual(budget.remaining_seconds(reserve_seconds=5.0), 50.0)

    def test_expired_includes_exact_and_reserve_adjusted_deadlines(self) -> None:
        now = [110.999]
        budget = AnalysisBudget(deadline=113.0, _clock=lambda: now[0])

        self.assertFalse(budget.expired())
        self.assertFalse(budget.expired(reserve_seconds=2.0))

        now[0] = 111.0
        self.assertTrue(budget.expired(reserve_seconds=2.0))
        self.assertFalse(budget.expired())

        now[0] = 113.0
        self.assertTrue(budget.expired())

    def test_parser_stage_uses_one_shared_eight_second_deadline(self) -> None:
        budget = AnalysisBudget(deadline=113.0, _clock=lambda: 100.0)

        self.assertEqual(
            budget.stage_deadline(8.0, reserve_seconds=2.0),
            108.0,
        )

    def test_stage_deadline_clamps_to_budget_reserve_and_current_time(self) -> None:
        now = [100.0]
        budget = AnalysisBudget(deadline=105.0, _clock=lambda: now[0])

        self.assertEqual(
            budget.stage_deadline(8.0, reserve_seconds=2.0),
            103.0,
        )

        now[0] = 104.0
        self.assertEqual(
            budget.stage_deadline(8.0, reserve_seconds=2.0),
            104.0,
        )

    def test_stage_deadline_treats_negative_inputs_as_zero(self) -> None:
        budget = AnalysisBudget(deadline=105.0, _clock=lambda: 100.0)

        self.assertEqual(budget.stage_deadline(-8.0), 100.0)
        self.assertEqual(
            budget.stage_deadline(8.0, reserve_seconds=-2.0),
            105.0,
        )

    def test_remaining_until_clamps_to_global_and_past_deadlines(self) -> None:
        budget = AnalysisBudget(deadline=113.0, _clock=lambda: 100.0)

        self.assertEqual(budget.remaining_until(140.0), 13.0)
        self.assertEqual(budget.remaining_until(108.0), 8.0)
        self.assertEqual(budget.remaining_until(99.0), 0.0)

    def test_provider_timeout_reserves_response_margin_and_obeys_caps(self) -> None:
        now = [100.0]
        budget = AnalysisBudget.start(clock=lambda: now[0])

        self.assertEqual(budget.provider_timeout_seconds(90), 35.0)
        self.assertEqual(budget.provider_timeout_seconds(7), 7)

        now[0] = 145.0
        self.assertEqual(budget.provider_timeout_seconds(25), 5.0)

        now[0] = 145.5
        self.assertIsNone(budget.provider_timeout_seconds(25))

    def test_text_fallback_timeout_uses_one_final_sample_and_exact_boundary(self) -> None:
        calls: list[float] = []
        now = [88.0]

        def clock() -> float:
            calls.append(now[0])
            return now[0]

        budget = AnalysisBudget(deadline=100.0, _clock=clock)

        self.assertEqual(budget.text_fallback_timeout_seconds(20.0), 7.0)
        self.assertEqual(calls, [88.0])

        now[0] = 88.001
        calls.clear()
        self.assertIsNone(budget.text_fallback_timeout_seconds(20.0))
        self.assertEqual(calls, [88.001])


if __name__ == "__main__":
    unittest.main()
