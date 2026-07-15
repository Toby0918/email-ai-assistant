"""Real-TTY-only ephemeral usefulness judge adapter tests."""

from __future__ import annotations

import importlib
import importlib.util
import io
import unittest
from dataclasses import replace

from backend.private_evaluation.errors import PrivateEvaluationError
from backend.private_evaluation.runner_values import UsefulnessJudgeView


class _Input(io.StringIO):
    def __init__(self, value: str, *, tty: bool = True) -> None:
        super().__init__(value)
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class _Output(io.StringIO):
    def __init__(self, *, tty: bool = True) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class _FailingOutput(_Output):
    def write(self, _value: str) -> int:
        raise OSError("SENSITIVE-TERMINAL-DETAIL")


class _CancelledInput(_Input):
    def readline(self, *_args: object, **_kwargs: object) -> str:
        raise KeyboardInterrupt


def _load_terminal(test: unittest.TestCase):
    name = "backend.private_evaluation.terminal_judge"
    test.assertIsNotNone(importlib.util.find_spec(name), "terminal judge module is missing")
    module = importlib.import_module(name)
    for attribute in (
        "make_interactive_judge", "require_terminal_readiness",
        "terminal_streams_available",
    ):
        test.assertTrue(hasattr(module, attribute), f"{attribute} is missing")
    return module


def view() -> UsefulnessJudgeView:
    return UsefulnessJudgeView(
        "Deidentified synthetic subject",
        "Deidentified synthetic thread",
        "Public synthetic summary",
        "Public synthetic reply subject",
        "Public synthetic reply body",
        "customer_inquiry",
        ("delivery_risk",),
        ("reply", "confirm"),
    )


class PrivateEvaluationTerminalJudgeTests(unittest.TestCase):
    def test_renders_only_judge_view_fields_and_accepts_exact_lowercase_y(self) -> None:
        terminal = _load_terminal(self)
        source = _Input("y\n")
        target = _Output()
        judge = terminal.make_interactive_judge(source, target)

        self.assertIs(judge(view()), True)

        rendered = target.getvalue()
        for marker in (
            "Deidentified synthetic subject",
            "Deidentified synthetic thread",
            "Public synthetic summary",
            "customer_inquiry",
            "delivery_risk",
            "reply",
            "confirm",
            "Public synthetic reply subject",
            "Public synthetic reply body",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, rendered)
        for forbidden in (
            "case_id", "actor_ref", "dataset_namespace", "raw_provider_json",
            "C:\\SyntheticPrivate", "mapping", "approval",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_accepts_exact_lowercase_n_as_false(self) -> None:
        terminal = _load_terminal(self)
        self.assertIs(
            terminal.make_interactive_judge(_Input("n\n"), _Output())(view()),
            False,
        )

    def test_invalid_eof_wrong_view_and_terminal_failure_are_fixed_failures(self) -> None:
        terminal = _load_terminal(self)
        cases = (
            (_Input("Y\n"), _Output(), view()),
            (_Input(" y\n"), _Output(), view()),
            (_Input("maybe\n"), _Output(), view()),
            (_Input(""), _Output(), view()),
            (_Input("y\n", tty=False), _Output(), view()),
            (_Input("y\n"), _Output(tty=False), view()),
            (_Input("y\n"), _FailingOutput(), view()),
            (_Input("y\n"), _Output(), object()),
            (
                _Input("y\n"), _Output(),
                replace(view(), risk_types=object()),  # type: ignore[arg-type]
            ),
        )
        for source, target, candidate in cases:
            with self.subTest(candidate_type=type(candidate).__name__), self.assertRaisesRegex(
                PrivateEvaluationError, "human_judge_failed"
            ) as caught:
                terminal.make_interactive_judge(source, target)(candidate)
            self.assertEqual(repr(caught.exception), "PrivateEvaluationError('human_judge_failed')")
            self.assertNotIn("SENSITIVE-TERMINAL-DETAIL", repr(caught.exception))

    def test_tty_preflight_rejects_closed_and_redirected_streams(self) -> None:
        terminal = _load_terminal(self)
        self.assertTrue(terminal.terminal_streams_available(_Input(""), _Output()))
        self.assertFalse(
            terminal.terminal_streams_available(_Input("", tty=False), _Output())
        )
        self.assertFalse(
            terminal.terminal_streams_available(_Input(""), _Output(tty=False))
        )
        source = _Input("")
        source.close()
        self.assertFalse(terminal.terminal_streams_available(source, _Output()))

    def test_readiness_requires_exact_y_and_maps_eof_cancel_and_output_failure(self) -> None:
        terminal = _load_terminal(self)
        target = _Output()
        self.assertIsNone(terminal.require_terminal_readiness(_Input("y\n"), target))
        self.assertIn("Enter exactly y", target.getvalue())

        for source, output in (
            (_Input(""), _Output()),
            (_Input("n\n"), _Output()),
            (_Input("Y\n"), _Output()),
            (_CancelledInput(""), _Output()),
            (_Input("y\n"), _FailingOutput()),
        ):
            with self.subTest(source=type(source).__name__), self.assertRaisesRegex(
                PrivateEvaluationError, "human_judge_failed"
            ):
                terminal.require_terminal_readiness(source, output)

    def test_terminal_controls_fail_before_any_untrusted_text_is_rendered(self) -> None:
        terminal = _load_terminal(self)
        malicious = (
            "Public synthetic summary\x1b]52;c;ZXZpbA==\x07"
        )
        for candidate in (
            replace(view(), input_thread_text="safe\x1b[2Jtext"),
            replace(view(), analysis_summary=malicious),
            replace(view(), reply_body="safe\u009b31mtext"),
            replace(view(), reply_subject="safe\u202etext"),
        ):
            target = _Output()
            with self.subTest(candidate=candidate), self.assertRaisesRegex(
                PrivateEvaluationError, "human_judge_failed"
            ):
                terminal.make_interactive_judge(_Input("y\n"), target)(candidate)
            self.assertEqual(target.getvalue(), "")
            self.assertNotIn("\x1b", target.getvalue())


if __name__ == "__main__":
    unittest.main()
