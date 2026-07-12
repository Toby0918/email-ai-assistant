import time
from collections.abc import Callable
from dataclasses import dataclass, field


BACKEND_TARGET_SECONDS = 32.0
RESPONSE_MARGIN_SECONDS = 2.0
PARSER_MAX_SECONDS = 8.0
PROVIDER_MAX_SECONDS = 25.0
PROVIDER_MIN_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class AnalysisBudget:
    deadline: float
    _clock: Callable[[], float] = field(repr=False, compare=False)

    @classmethod
    def start(
        cls,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> "AnalysisBudget":
        return cls(deadline=clock() + BACKEND_TARGET_SECONDS, _clock=clock)

    def remaining_seconds(self, *, reserve_seconds: float = 0.0) -> float:
        return max(0.0, self.deadline - self._clock() - reserve_seconds)

    def expired(self, *, reserve_seconds: float = 0.0) -> bool:
        return self.remaining_seconds(reserve_seconds=reserve_seconds) <= 0.0

    def stage_deadline(
        self,
        maximum_seconds: float,
        *,
        reserve_seconds: float = 0.0,
    ) -> float:
        now = self._clock()
        maximum = max(0.0, maximum_seconds)
        reserve = max(0.0, reserve_seconds)
        return max(now, min(now + maximum, self.deadline - reserve))

    def remaining_until(self, deadline: float) -> float:
        return max(0.0, min(float(deadline), self.deadline) - self._clock())

    def provider_timeout_seconds(
        self,
        configured_timeout_seconds: float,
    ) -> float | None:
        timeout = min(
            configured_timeout_seconds,
            PROVIDER_MAX_SECONDS,
            self.remaining_seconds(reserve_seconds=RESPONSE_MARGIN_SECONDS),
        )
        return timeout if timeout >= PROVIDER_MIN_SECONDS else None
