"""Exact injected capabilities for the dormant validation composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class ValidationAdaptersV1:
    start_provider_disabled: Callable
    read_health: Callable
    analyze_public_rule_fallback: Callable
    confirm_public_result: Callable
    observe_persisted_row: Callable
    stop_exact: Callable
    final_database_proof: Callable
    run_independent_audit: Callable

    def exact(self) -> bool:
        return type(self) is ValidationAdaptersV1 and all(
            callable(getattr(self, name))
            for name in self.__dataclass_fields__
        )
