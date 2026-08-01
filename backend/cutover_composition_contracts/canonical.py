"""Canonical content-free value helpers."""

from __future__ import annotations

import hashlib
import json

from .errors import CompositionContractError


_MAX_JSON_BYTES = 128 * 1024


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
        and all(item in "0123456789abcdef" for item in value)
    )


def strict_json_object(payload: object, *, code: str) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_JSON_BYTES:
        raise CompositionContractError(code)

    def reject_duplicates(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise CompositionContractError(code)
            value[key] = item
        return value

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: _invalid_json(code),
        )
    except CompositionContractError:
        raise
    except (
        TypeError,
        ValueError,
        UnicodeDecodeError,
        OverflowError,
        RecursionError,
    ):
        raise CompositionContractError(code) from None
    if type(value) is not dict:
        raise CompositionContractError(code)
    return value


def _invalid_json(code: str) -> None:
    raise CompositionContractError(code)


UNBOUND_FINGERPRINT = fingerprint(
    "project-container-composition-unbound-v1",
    {"bound": False},
)
