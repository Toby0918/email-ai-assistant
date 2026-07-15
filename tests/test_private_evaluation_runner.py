"""Offline fake-client tests for the exact private evaluation gate sequence."""

from __future__ import annotations

import json
import re
import unittest
from unittest.mock import patch

from backend.email_agent.private_context_gate import (
    PrivateContextFallbackCode,
    PrivateModelRequest,
    build_private_model_context,
    provider_output_is_private_safe,
)
from backend.private_evaluation.runner import (
    FLASH_MODEL,
    PRO_MODEL,
    UsefulnessJudgeView,
    _attempt_case,
    run_private_evaluation,
)
from backend.private_evaluation.schema import EvaluationDatasetV1
from backend.private_evaluation.selection import derive_selection_key, select_private_cases
from tests.private_evaluation_fixtures import dataset_mapping, envelope_json_for


class ManualClock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value


class FakeClient:
    def __init__(self, outputs, *, clock: ManualClock | None = None, latency: float = 0.1):
        self.outputs = list(outputs)
        self.calls: list[dict[str, object]] = []
        self.clock = clock
        self.latency = latency
        self.active = 0
        self.max_active = 0

    def __call__(self, prompt: str, **options: object) -> str:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            self.calls.append({"prompt": prompt, **options})
            if self.clock is not None:
                self.clock.value += self.latency
            value = self.outputs[len(self.calls) - 1]
            if isinstance(value, BaseException):
                raise value
            return value
        finally:
            self.active -= 1


def selection():
    dataset = EvaluationDatasetV1.from_mapping(dataset_mapping())
    key = derive_selection_key(bytearray(b"R" * 32), dataset.dataset_namespace)
    return select_private_cases(dataset, key)


def outputs_for(cases) -> list[str]:
    return [envelope_json_for(case) for case in cases]


class PrivateEvaluationRunnerTests(unittest.TestCase):
    def test_private_evaluation_client_receives_generic_semantics_without_internal_tokens(self) -> None:
        chosen = selection()
        case = chosen.selected[0]
        flash = FakeClient([envelope_json_for(case)])

        _attempt_case(case, FLASH_MODEL, flash, ())

        self.assertEqual(len(flash.calls), 1)
        prompt = flash.calls[0]["prompt"]
        self.assertIs(type(prompt), str)
        assert isinstance(prompt, str)
        self.assertIsNone(
            re.search(r"<[A-Z_]+_[1-9][0-9]*>", prompt, re.IGNORECASE)
        )
        self.assertIn("an organization", prompt)
        self.assertIn("a contact address", prompt)
        self.assertIn("a stated date", prompt)

    def test_passing_run_calls_flash_200_then_pro_40_sequentially_and_reuses_flash(self) -> None:
        chosen = selection()
        flash = FakeClient(outputs_for(chosen.selected))
        pro = FakeClient(outputs_for(chosen.paired))
        judged: list[UsefulnessJudgeView] = []

        report = run_private_evaluation(
            chosen,
            flash_client=flash,
            pro_client=pro,
            usefulness_judge=lambda view: judged.append(view) is None,
        )

        self.assertEqual(len(flash.calls), 200)
        self.assertEqual(len(pro.calls), 40)
        self.assertEqual((flash.max_active, pro.max_active), (1, 1))
        self.assertEqual(len(judged), 240)
        self.assertTrue(all(isinstance(view, UsefulnessJudgeView) for view in judged))
        self.assertTrue(all("Current request" not in repr(view) for view in judged))
        self.assertEqual({call["model"] for call in flash.calls}, {FLASH_MODEL})
        self.assertEqual({call["model"] for call in pro.calls}, {PRO_MODEL})
        for call in (*flash.calls, *pro.calls):
            self.assertIs(call["stream"], False)
            self.assertEqual(call["max_retries"], 0)
            self.assertEqual(call["timeout_seconds"], 10.0)
        self.assertEqual(report.status_code, "comparison_complete")
        self.assertEqual(report.decision_code, "retain_flash")
        self.assertEqual(report.counts["flash_attempted"], 200)
        self.assertEqual(report.counts["pro_attempted"], 40)

    def test_every_attempt_uses_exact_task5_gate_and_runtime_cards_tuple(self) -> None:
        chosen = selection()
        flash = FakeClient(outputs_for(chosen.selected))
        pro = FakeClient(outputs_for(chosen.paired))
        cards = ()

        with patch(
            "backend.private_evaluation.runner.build_private_model_context",
            wraps=build_private_model_context,
        ) as build_gate, patch(
            "backend.private_evaluation.runner.provider_output_is_private_safe",
            wraps=provider_output_is_private_safe,
        ) as output_gate:
            run_private_evaluation(
                chosen, flash_client=flash, pro_client=pro,
                usefulness_judge=lambda _view: True, runtime_cards=cards,
            )

        self.assertEqual(build_gate.call_count, 240)
        self.assertEqual(output_gate.call_count, 240)
        request = build_gate.call_args_list[0].args[0]
        self.assertIsInstance(request, PrivateModelRequest)
        self.assertNotIn("Current request", repr(request))
        self.assertIs(build_gate.call_args_list[0].args[2], cards)

    def test_missing_clients_judge_or_invalid_cards_block_before_calls(self) -> None:
        chosen = selection()
        flash = FakeClient(outputs_for(chosen.selected))
        pro = FakeClient(outputs_for(chosen.paired))
        cases = (
            (None, pro, lambda _view: True, (), "provider_configuration_unavailable"),
            (flash, None, lambda _view: True, (), "provider_configuration_unavailable"),
            (flash, pro, None, (), "human_judge_unavailable"),
            (flash, pro, lambda _view: True, [], "privacy_violation"),
        )
        for flash_client, pro_client, judge, cards, code in cases:
            flash.calls.clear()
            pro.calls.clear()
            with self.subTest(code=code):
                report = run_private_evaluation(
                    chosen, flash_client=flash_client, pro_client=pro_client,
                    usefulness_judge=judge, runtime_cards=cards,  # type: ignore[arg-type]
                )
                self.assertEqual(report.status_code, "blocked")
                self.assertEqual(report.error_code_counts, {code: 1})
                self.assertEqual((len(flash.calls), len(pro.calls)), (0, 0))

    def test_task5_input_refusal_blocks_before_provider_with_fixed_code(self) -> None:
        chosen = selection()
        flash = FakeClient(outputs_for(chosen.selected))
        pro = FakeClient(outputs_for(chosen.paired))
        for refusal, internal_code, internal_stage, public_code in (
            (
                PrivateContextFallbackCode.SAFETY,
                "safety_rejected_all", "safety", "privacy_violation",
            ),
            (
                PrivateContextFallbackCode.BUDGET,
                "budget_exhausted", "budget", "latency_gate_failed",
            ),
        ):
            with self.subTest(refusal=refusal):
                with patch(
                    "backend.private_evaluation.runner.build_private_model_context",
                    return_value=refusal,
                ):
                    attempt = _attempt_case(chosen.selected[0], FLASH_MODEL, flash, ())
                    report = run_private_evaluation(
                        chosen, flash_client=flash, pro_client=pro,
                        usefulness_judge=lambda _view: True,
                    )
                self.assertEqual(attempt.error_code, public_code)
                self.assertEqual(getattr(attempt, "fallback_code", None), internal_code)
                self.assertEqual(getattr(attempt, "fallback_stage", None), internal_stage)
                self.assertNotIn(internal_code, repr(attempt))
                self.assertNotIn(internal_stage, repr(attempt))
                self.assertEqual(report.status_code, "gate_stopped")
                self.assertEqual(report.error_code_counts, {public_code: 1})
                serialized = json.dumps(report.to_mapping(), sort_keys=True)
                self.assertNotIn(internal_code, serialized)
                self.assertNotIn(internal_stage, serialized)
        self.assertEqual((len(flash.calls), len(pro.calls)), (0, 0))

    def test_gate_stops_immediately_for_privacy_schema_safety_grounding_and_judge(self) -> None:
        chosen = selection()
        safe = outputs_for(chosen.selected)
        privacy = json.loads(safe[0])
        privacy["analysis"]["summary"] = "Review <PERSON_1>"
        unsafe = json.loads(safe[0])
        unsafe["analysis"]["summary"] = "请自动发送当前邮件。"
        grounded = json.loads(safe[0])
        grounded["analysis"]["summary"] = "请核查 PO 12345。"
        cases = (
            ([json.dumps(privacy, ensure_ascii=False)], lambda _view: True, "privacy_violation"),
            (["{}"], lambda _view: True, "schema_violation"),
            ([json.dumps(unsafe, ensure_ascii=False)], lambda _view: True, "safety_violation"),
            ([json.dumps(grounded, ensure_ascii=False)], lambda _view: True, "grounding_violation"),
            ([safe[0]], lambda _view: 1, "human_judge_failed"),
        )
        for outputs, judge, code in cases:
            flash = FakeClient(outputs)
            pro = FakeClient(outputs_for(chosen.paired))
            with self.subTest(code=code):
                report = run_private_evaluation(
                    chosen, flash_client=flash, pro_client=pro, usefulness_judge=judge,
                )
                self.assertEqual(report.status_code, "gate_stopped")
                self.assertEqual(report.decision_code, "gate_failed")
                self.assertEqual(report.error_code_counts, {code: 1})
                self.assertEqual((len(flash.calls), len(pro.calls)), (1, 0))

    def test_provider_exception_has_zero_retry_no_replacement_and_content_free_report(self) -> None:
        chosen = selection()
        secret = "provider-secret-current-request"
        flash = FakeClient([RuntimeError(secret)])
        pro = FakeClient(outputs_for(chosen.paired))
        report = run_private_evaluation(
            chosen, flash_client=flash, pro_client=pro,
            usefulness_judge=lambda _view: True,
        )
        self.assertEqual((len(flash.calls), len(pro.calls)), (1, 0))
        self.assertEqual(report.error_code_counts, {"provider_error": 1})
        self.assertNotIn(secret, repr(report))
        self.assertNotIn(secret, json.dumps(report.to_mapping(), sort_keys=True))

    def test_latency_gate_runs_after_twenty_and_exact_twelve_continues(self) -> None:
        chosen = selection()
        for latency, expected_calls, expected_status in (
            (12.0, 200, "comparison_complete"),
            (12.000001, 20, "gate_stopped"),
        ):
            clock = ManualClock()
            flash = FakeClient(outputs_for(chosen.selected), clock=clock, latency=latency)
            pro = FakeClient(outputs_for(chosen.paired), clock=clock, latency=latency)
            with self.subTest(latency=latency), patch(
                "backend.private_evaluation.runner._clock", clock
            ):
                report = run_private_evaluation(
                    chosen, flash_client=flash, pro_client=pro,
                    usefulness_judge=lambda _view: True,
                )
                self.assertEqual(len(flash.calls), expected_calls)
                self.assertEqual(report.status_code, expected_status)
                if expected_status == "gate_stopped":
                    self.assertEqual(report.error_code_counts, {"latency_gate_failed": 1})

    def test_post_gate_invalid_output_completes_flash_with_fallback_and_no_pro(self) -> None:
        chosen = selection()
        outputs = outputs_for(chosen.selected)
        outputs[20] = "{}"
        flash = FakeClient(outputs)
        pro = FakeClient(outputs_for(chosen.paired))

        report = run_private_evaluation(
            chosen, flash_client=flash, pro_client=pro,
            usefulness_judge=lambda _view: True,
        )

        self.assertEqual((len(flash.calls), len(pro.calls)), (200, 0))
        self.assertEqual((report.status_code, report.decision_code), (
            "flash_complete", "flash_rejected"
        ))
        self.assertEqual(report.error_code_counts["schema_violation"], 1)
        self.assertEqual(report.error_code_counts["fallback_observed"], 1)

    def test_judge_time_is_excluded_from_latency(self) -> None:
        chosen = selection()
        clock = ManualClock()
        flash = FakeClient(outputs_for(chosen.selected), clock=clock, latency=0.25)
        pro = FakeClient(outputs_for(chosen.paired), clock=clock, latency=0.25)

        def judge(_view: UsefulnessJudgeView) -> bool:
            clock.value += 100.0
            return True

        with patch("backend.private_evaluation.runner._clock", clock):
            report = run_private_evaluation(
                chosen, flash_client=flash, pro_client=pro, usefulness_judge=judge,
            )
        self.assertEqual(report.metrics["flash"]["p95_seconds"], 0.25)


if __name__ == "__main__":
    unittest.main()
