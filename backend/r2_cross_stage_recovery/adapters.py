"""Exact injected seams for observation, reverse effects, and final append."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class CrossStageAdaptersV1:
    observe_intent: Callable
    current_journal_head: Callable
    reverse_boundary: Callable
    minimal_final_freshness: Callable
    append_cutover_success: Callable

    def exact(self) -> bool:
        return type(self) is CrossStageAdaptersV1 and all(
            callable(getattr(self, name)) for name in self.__dataclass_fields__
        )
