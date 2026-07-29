"""The exact new and legacy service capabilities available to Issue #58."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Callable


@dataclass(frozen=True, slots=True, repr=False)
class NewServiceAdapter:
    start_provider_disabled: Callable[[object], object] = field(repr=False)
    read_health: Callable[[object], object] = field(repr=False)
    analyze_fixed_synthetic: Callable[[object], object] = field(repr=False)
    observe_synthetic_row: Callable[[object], object] = field(repr=False)
    stop_exact: Callable[[object], object] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class LegacyServiceAdapter:
    start_provider_disabled_recovery: Callable[[object], object] = field(
        repr=False
    )
    read_health: Callable[[object], object] = field(repr=False)
    stop_exact: Callable[[object], object] = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class ProviderDisabledServiceAdapters:
    new_service: NewServiceAdapter = field(repr=False)
    legacy_service: LegacyServiceAdapter = field(repr=False)


def has_exact_adapters(value: object) -> bool:
    return (
        type(value) is ProviderDisabledServiceAdapters
        and type(value.new_service) is NewServiceAdapter
        and type(value.legacy_service) is LegacyServiceAdapter
        and _all_callables(value.new_service)
        and _all_callables(value.legacy_service)
    )


def _all_callables(value: object) -> bool:
    return all(callable(getattr(value, item.name)) for item in fields(value))
