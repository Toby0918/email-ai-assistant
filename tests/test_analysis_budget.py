import unittest

from backend.email_agent.analysis_budget import AnalysisBudget


class AnalysisBudgetTests(unittest.TestCase):
    def test_start_uses_one_32_second_monotonic_budget(self) -> None:
        now = [100.0]

        budget = AnalysisBudget.start(clock=lambda: now[0])

        self.assertEqual(budget.deadline, 132.0)
        self.assertEqual(budget.remaining_seconds(), 32.0)
        self.assertEqual(budget.remaining_seconds(reserve_seconds=2.0), 30.0)

    def test_expired_includes_exact_and_reserve_adjusted_deadlines(self) -> None:
        now = [129.999]
        budget = AnalysisBudget(deadline=132.0, _clock=lambda: now[0])

        self.assertFalse(budget.expired())
        self.assertFalse(budget.expired(reserve_seconds=2.0))

        now[0] = 130.0
        self.assertTrue(budget.expired(reserve_seconds=2.0))
        self.assertFalse(budget.expired())

        now[0] = 132.0
        self.assertTrue(budget.expired())

    def test_parser_stage_uses_one_shared_eight_second_deadline(self) -> None:
        budget = AnalysisBudget(deadline=132.0, _clock=lambda: 100.0)

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
        budget = AnalysisBudget(deadline=132.0, _clock=lambda: 100.0)

        self.assertEqual(budget.remaining_until(140.0), 32.0)
        self.assertEqual(budget.remaining_until(108.0), 8.0)
        self.assertEqual(budget.remaining_until(99.0), 0.0)

    def test_provider_timeout_reserves_response_margin_and_obeys_caps(self) -> None:
        now = [100.0]
        budget = AnalysisBudget.start(clock=lambda: now[0])

        self.assertEqual(budget.provider_timeout_seconds(90), 25.0)
        self.assertEqual(budget.provider_timeout_seconds(7), 7)

        now[0] = 125.0
        self.assertEqual(budget.provider_timeout_seconds(25), 5.0)

        now[0] = 126.5
        self.assertIsNone(budget.provider_timeout_seconds(25))


if __name__ == "__main__":
    unittest.main()
