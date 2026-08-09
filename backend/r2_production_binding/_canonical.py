"""Internal canonical encoding helpers for production bindings."""

from __future__ import annotations

import hashlib
import json

from .errors import ProductionBindingError


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def fingerprint(domain: str, value: object) -> str:
    payload = domain.encode("ascii") + b"\0" + canonical_json(value)
    return hashlib.sha256(payload).hexdigest()


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def strict_json_object(payload: object) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= 128 * 1024:
        raise ProductionBindingError()

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ProductionBindingError()
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: _invalid_json(),
        )
    except ProductionBindingError:
        raise
    except (TypeError, ValueError, UnicodeDecodeError, OverflowError, RecursionError):
        raise ProductionBindingError() from None
    if type(value) is not dict:
        raise ProductionBindingError()
    return value


def fingerprint_entries(values: object) -> list[dict[str, object]]:
    return [
        {"role": role.value, "fingerprint": value}
        for role, value in values
    ]


def parse_fingerprint_entries(value: object, enum_type: object) -> dict:
    if type(value) is not list or len(value) != len(enum_type):
        raise ProductionBindingError()
    result = {}
    for expected, entry in zip(enum_type, value, strict=True):
        if (
            type(entry) is not dict
            or set(entry) != {"role", "fingerprint"}
            or entry["role"] != expected.value
            or not is_fingerprint(entry["fingerprint"])
        ):
            raise ProductionBindingError()
        result[expected] = entry["fingerprint"]
    return result


def _invalid_json() -> None:
    raise ProductionBindingError()
