"""Repr-hidden transient value objects for private evaluation runs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .metrics import ScoredOutcome
from .schema import EvaluationCaseV1


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
    fallback_code: str | None = field(default=None, repr=False)
    fallback_stage: str | None = field(default=None, repr=False)


@dataclass(slots=True, repr=False)
class _RunState:
    errors: Counter[str] = field(default_factory=Counter, repr=False)
    flash_results: dict[EvaluationCaseV1, ScoredOutcome] = field(
        default_factory=dict, repr=False
    )
    pro_results: list[ScoredOutcome] = field(default_factory=list, repr=False)
    flash_attempted: int = 0
    pro_attempted: int = 0
