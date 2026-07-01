"""Export helpers for local debug reports."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def rows_for_export(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    # Export is a shallow local projection; it must not reach into live mailboxes.
    return [dict(record) for record in records]
