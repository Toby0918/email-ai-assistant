"""Strict canonical JSON primitives shared by Issue #51 value contracts."""

from __future__ import annotations

import json

from .errors import CutoverContractError


_MAX_JSON_BYTES = 128 * 1024


def is_exact_str(value: object, expected: str) -> bool:
    return type(value) is str and value == expected


def is_exact_str_list(value: object, expected: list[str]) -> bool:
    return (
        type(value) is list
        and all(type(item) is str for item in value)
        and value == expected
    )


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def is_commit(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def canonical_json(
    value: object,
    *,
    code: str = "CUTOVER_CONTRACT_INVALID",
) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CutoverContractError(code) from None


def strict_json_object(payload: object, *, code: str) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_JSON_BYTES:
        raise CutoverContractError(code)

    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise CutoverContractError(code)
            value[key] = item
        return value

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=lambda _value: _raise_invalid(code),
        )
    except CutoverContractError:
        raise
    except (
        TypeError,
        ValueError,
        UnicodeDecodeError,
        OverflowError,
        RecursionError,
    ):
        raise CutoverContractError(code) from None
    if type(value) is not dict:
        raise CutoverContractError(code)
    return value


def _raise_invalid(code: str) -> None:
    raise CutoverContractError(code)
