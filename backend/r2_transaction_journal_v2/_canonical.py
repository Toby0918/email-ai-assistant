"""Strict canonical JSON helpers for the unified journal V2."""

from __future__ import annotations

import hashlib
import json

from .errors import JournalGenesisError


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def fingerprint(domain: str, value: object) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + canonical_json(value)
    ).hexdigest()


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def strict_json_object(payload: object) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= 128 * 1024:
        raise JournalGenesisError()

    def pairs_hook(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise JournalGenesisError()
            value[key] = item
        return value

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda _value: _invalid(),
        )
    except JournalGenesisError:
        raise
    except Exception:
        raise JournalGenesisError() from None
    if type(value) is not dict:
        raise JournalGenesisError()
    return value


def _invalid():
    raise JournalGenesisError()
