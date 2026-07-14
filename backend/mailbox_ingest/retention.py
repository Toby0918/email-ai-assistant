"""Calendar-month retention helpers for encrypted mailbox records."""

from __future__ import annotations

import calendar
from datetime import datetime, timezone

from .errors import VaultError
from .vault_index import MAX_BATCH_LIMIT


def max_expiry_utc(now_utc: int, *, months: int = 24) -> int:
    if type(now_utc) is not int or type(months) is not int or months <= 0:
        raise VaultError("invalid_expiry")
    try:
        current = datetime.fromtimestamp(now_utc, timezone.utc)
        month_index = current.month - 1 + months
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return int(current.replace(year=year, month=month, day=day).timestamp())
    except (OverflowError, OSError, ValueError):
        raise VaultError("invalid_expiry") from None


def validate_expiry(expires_at_utc: object, now_utc: int) -> None:
    if type(expires_at_utc) is not int:
        raise VaultError("invalid_expiry")
    if expires_at_utc > max_expiry_utc(now_utc, months=24):
        raise VaultError("expiry_exceeds_retention")


def validate_batch_limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_LIMIT:
        raise VaultError("invalid_limit")


__all__ = ["max_expiry_utc", "validate_batch_limit", "validate_expiry"]
