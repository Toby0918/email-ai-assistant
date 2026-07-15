"""Ephemeral real-TTY usefulness decisions with no transcript surface."""

from __future__ import annotations

from typing import Callable, TextIO

from .errors import PrivateEvaluationError
from .runner_values import UsefulnessJudgeView
from .terminal_text_safety import terminal_text_is_safe


def terminal_streams_available(source: TextIO, target: TextIO) -> bool:
    try:
        return bool(
            not source.closed
            and not target.closed
            and source.isatty() is True
            and target.isatty() is True
        )
    except Exception:
        return False


def make_interactive_judge(
    source: TextIO,
    target: TextIO,
) -> Callable[[UsefulnessJudgeView], bool]:
    def judge(view: UsefulnessJudgeView) -> bool:
        if type(view) is not UsefulnessJudgeView or not terminal_streams_available(
            source, target
        ) or not _view_text_is_safe(view):
            _failed()
        try:
            target.write(_render(view))
            target.flush()
            decision = source.readline()
        except (Exception, KeyboardInterrupt):
            _failed()
        if decision not in {"y\n", "n\n", "y\r\n", "n\r\n"}:
            _failed()
        return decision.startswith("y")

    return judge


def require_terminal_readiness(source: TextIO, target: TextIO) -> None:
    if not terminal_streams_available(source, target):
        _failed()
    try:
        target.write(
            "Private evaluation uses an ephemeral real-TTY judge. "
            "Enter exactly y to continue: "
        )
        target.flush()
        decision = source.readline()
    except (Exception, KeyboardInterrupt):
        _failed()
    if decision not in {"y\n", "y\r\n"}:
        _failed()


def _view_text_is_safe(view: UsefulnessJudgeView) -> bool:
    try:
        values = (
            view.input_subject, view.input_thread_text, view.analysis_summary,
            view.reply_subject, view.reply_body, view.category,
            *view.risk_types, *view.action_types,
        )
        return all(terminal_text_is_safe(value) for value in values)
    except Exception:
        return False


def _render(view: UsefulnessJudgeView) -> str:
    risks = ", ".join(view.risk_types) or "none"
    actions = ", ".join(view.action_types) or "none"
    return (
        "\n=== Private evaluation usefulness judge ===\n"
        f"Deidentified subject:\n{view.input_subject}\n"
        f"Deidentified thread:\n{view.input_thread_text}\n"
        f"Public summary:\n{view.analysis_summary}\n"
        f"Public category: {view.category}\n"
        f"Public risk types: {risks}\n"
        f"Public action types: {actions}\n"
        f"Public reply subject:\n{view.reply_subject}\n"
        f"Public reply body:\n{view.reply_body}\n"
        "Useful? Enter exactly y or n: "
    )


def _failed() -> None:
    raise PrivateEvaluationError("human_judge_failed")
