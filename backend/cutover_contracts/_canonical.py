"""Strict canonical JSON primitives shared by Issue #51 value contracts."""

from __future__ import annotations

import json

from .errors import CutoverContractError


_MAX_JSON_BYTES = 128 * 1024


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CutoverContractError("CUTOVER_CONTRACT_INVALID") from None


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
