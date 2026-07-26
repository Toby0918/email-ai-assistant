"""Strict canonical JSON helpers for synthetic journal values."""

from __future__ import annotations

import json

from .errors import JournalContractError


MAX_JSON_BYTES = 128 * 1024
ZERO_FINGERPRINT = "0" * 64


def is_commit(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def is_opaque_fingerprint(value: object) -> bool:
    return is_fingerprint(value) and value != ZERO_FINGERPRINT


def canonical_json(value: object, *, code: str) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise JournalContractError(code) from None


def strict_json_object(payload: object, *, code: str) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= MAX_JSON_BYTES:
        raise JournalContractError(code)

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise JournalContractError(code)
            value[key] = item
        return value

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: _raise_invalid(code),
        )
    except JournalContractError:
        raise
    except (
        TypeError,
        ValueError,
        UnicodeDecodeError,
        OverflowError,
        RecursionError,
    ):
        raise JournalContractError(code) from None
    if type(value) is not dict:
        raise JournalContractError(code)
    return value


def _raise_invalid(code: str) -> None:
    raise JournalContractError(code)
