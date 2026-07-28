"""Canonical content-free values shared by Issue #55 contracts."""

from __future__ import annotations

import hashlib
import json

from .errors import CutoverHostMutationError


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def canonical_json(value: object, *, code: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        raise CutoverHostMutationError(code) from None


def fingerprint(domain: str, value: object, *, code: str) -> str:
    if type(domain) is not str or not domain:
        raise CutoverHostMutationError(code)
    return hashlib.sha256(
        canonical_json({"domain": domain, "value": value}, code=code)
    ).hexdigest()


def exact_mapping(
    value: object,
    expected_keys: tuple[str, ...],
    *,
    code: str,
) -> dict[str, object]:
    if (
        type(value) is not dict
        or any(type(key) is not str for key in value)
        or tuple(sorted(value)) != tuple(sorted(expected_keys))
    ):
        raise CutoverHostMutationError(code)
    return value
