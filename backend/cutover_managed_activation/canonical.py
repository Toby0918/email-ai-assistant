"""Strict canonical helpers for content-free managed-publication values."""

from __future__ import annotations

import hashlib
import json
import re

from .errors import ManagedActivationError

_FINGERPRINT = re.compile(r"[0-9a-f]{64}", re.ASCII)
_COMMIT = re.compile(r"[0-9a-f]{40}", re.ASCII)


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
        raise ManagedActivationError(code) from None


def fingerprint(domain: str, value: object, *, code: str) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + canonical_json(value, code=code)
    ).hexdigest()


def is_fingerprint(value: object) -> bool:
    return type(value) is str and _FINGERPRINT.fullmatch(value) is not None


def is_commit(value: object) -> bool:
    return type(value) is str and _COMMIT.fullmatch(value) is not None


def fail(code: str) -> None:
    raise ManagedActivationError(code) from None
