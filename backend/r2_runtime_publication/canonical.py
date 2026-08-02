"""Canonical content-free helpers for Issue #77."""

from __future__ import annotations

import hashlib
import json


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def fingerprint(domain: str, value: object) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical(value)).hexdigest()


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
