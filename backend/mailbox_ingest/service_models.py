"""Small CLI/service handoff contracts without runtime side effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable, Protocol

from .inventory import InventoryV1


_AGGREGATE_FIELDS = {
    "scan_complete": frozenset(
        {
            "processed", "unique_messages", "duplicate_messages",
            "customer_requests", "sales_replies", "pairs",
            "duplicate_quotations", "excluded_automated",
            "excluded_non_sales", "excluded_forwards", "sensitive",
            "ambiguous", "supported_attachments", "unsupported_attachments",
        }
    ),
    "attachments_complete": frozenset(
        {
            "selected", "supported", "unsupported", "fetched",
            "acquisition_failed", "parsed", "parse_failed", "new_blobs",
            "duplicate_blobs", "semantic_unreviewed",
        }
    ),
}


@dataclass(frozen=True)
class CliResult:
    code: str
    count: int | None = None
    fingerprint: str | None = None
    opaque_ids: tuple[str, ...] = ()
    inventory: InventoryV1 | None = None
    aggregate_counts: dict[str, int] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"ok": True, "code": self.code}
        if self.count is not None:
            payload["count"] = self.count
        if self.fingerprint is not None:
            payload["fingerprint"] = self.fingerprint
        if self.opaque_ids:
            payload["opaque_ids"] = list(self.opaque_ids)
        if self.inventory is not None:
            payload["inventory"] = self.inventory.to_dict()
        if self.aggregate_counts is not None:
            _validate_aggregate_counts(self.code, self.aggregate_counts)
            payload["counts"] = dict(self.aggregate_counts)
        return payload


def _validate_aggregate_counts(code: str, values: object) -> None:
    expected = _AGGREGATE_FIELDS.get(code)
    if (
        expected is None
        or not isinstance(values, dict)
        or set(values) != expected
        or any(type(value) is not int or value < 0 for value in values.values())
    ):
        raise ValueError("aggregate_counts_invalid")


class PreparedOperation(Protocol):
    def execute(self, session: object | None) -> CliResult: ...


@dataclass(frozen=True)
class CliDependencies:
    preflight: Callable[[argparse.Namespace], object]
    prepare: Callable[[argparse.Namespace, object], PreparedOperation]
    getpass: Callable[[str], str]
    session_factory: Callable[[str, str], object]
    emit: Callable[[dict[str, object]], None]


__all__ = ["CliDependencies", "CliResult", "PreparedOperation"]
