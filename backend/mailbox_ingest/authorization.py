"""Strict one-account authorization and calendar-window primitives."""

from __future__ import annotations

import calendar
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


_AUTHORIZATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ACCOUNT = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_SCOPE_PURPOSE = b"mailbox-ingest/authorization-scope/v1\0"


class AuthorizationError(ValueError):
    def __init__(self, code: str = "authorization_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"AuthorizationError(code={self.code!r})"


@dataclass(frozen=True)
class AuthorizationScope:
    authorization_id: str = field(repr=False)
    account: str = field(repr=False)
    opaque_scope_id: str

    @classmethod
    def create(
        cls,
        authorization_id: str,
        account: str,
        *,
        hmac_key: bytes,
    ) -> "AuthorizationScope":
        if not isinstance(authorization_id, str) or not _AUTHORIZATION_ID.fullmatch(
            authorization_id
        ):
            raise AuthorizationError()
        if not isinstance(account, str):
            raise AuthorizationError("account_invalid")
        normalized = account.strip().lower()
        if not normalized.isascii() or not _ACCOUNT.fullmatch(normalized):
            raise AuthorizationError("account_invalid")
        if type(hmac_key) is not bytes or len(hmac_key) < 32:
            raise AuthorizationError("scope_key_invalid")
        payload = _SCOPE_PURPOSE + authorization_id.encode("ascii") + b"\0" + normalized.encode("ascii")
        opaque = hmac.new(hmac_key, payload, hashlib.sha256).hexdigest()
        return cls(authorization_id, normalized, opaque)

    def __repr__(self) -> str:
        return f"AuthorizationScope(opaque_scope_id={self.opaque_scope_id!r})"


@dataclass(frozen=True)
class DateWindow:
    window_start: datetime
    window_end: datetime


def add_calendar_months(value: datetime, months: int) -> datetime:
    _require_utc(value)
    if type(months) is not int:
        raise AuthorizationError("window_invalid")
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    try:
        day = min(value.day, calendar.monthrange(year, month)[1])
        return value.replace(year=year, month=month, day=day)
    except (ValueError, OverflowError):
        raise AuthorizationError("window_invalid") from None


def freeze_window(window_end: datetime) -> DateWindow:
    _require_utc(window_end)
    return DateWindow(add_calendar_months(window_end, -24), window_end)


def _require_utc(value: datetime) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
        or value.astimezone(timezone.utc).utcoffset() != value.utcoffset()
    ):
        raise AuthorizationError("window_invalid")


__all__ = [
    "AuthorizationError",
    "AuthorizationScope",
    "DateWindow",
    "add_calendar_months",
    "freeze_window",
]
