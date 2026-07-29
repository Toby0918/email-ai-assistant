"""Closed canonical helpers for provider-disabled lifecycle evidence."""

from __future__ import annotations

import hashlib
import json
import re
import uuid

from .errors import ServiceLifecycleError

_FINGERPRINT = re.compile(r"[0-9a-f]{64}", re.ASCII)


def fail(code: str) -> None:
    raise ServiceLifecycleError(code) from None


def is_fingerprint(value: object) -> bool:
    return type(value) is str and _FINGERPRINT.fullmatch(value) is not None


def is_uuid4(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return (
        str(parsed) == value
        and parsed.version == 4
        and parsed.variant == uuid.RFC_4122
    )


def canonical_json(value: object, *, code: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        fail(code)


def fingerprint(domain: str, value: object, *, code: str) -> str:
    return hashlib.sha256(
        domain.encode("ascii")
        + b"\0"
        + canonical_json(value, code=code)
    ).hexdigest()

