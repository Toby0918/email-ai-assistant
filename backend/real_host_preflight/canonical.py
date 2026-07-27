"""Small canonical fingerprint helpers for content-free preflight values."""

from __future__ import annotations

import hashlib
import json


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def fingerprint(domain: str, value: object) -> str:
    payload = json.dumps(
        {"domain": domain, "value": value},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()
