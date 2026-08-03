"""Internal canonical encoding and content-free identity helpers."""

from __future__ import annotations

import hashlib
import json

from .errors import FinalMasterClosureError


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
    payload = domain.encode("ascii") + b"\0" + canonical_json(value)
    return hashlib.sha256(payload).hexdigest()


def is_fingerprint(value: object) -> bool:
    return _is_lower_hex(value, 64)


def is_git_oid(value: object) -> bool:
    return _is_lower_hex(value, 40)


def strict_json_object(payload: object) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_JSON_BYTES:
        raise FinalMasterClosureError()

    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise FinalMasterClosureError()
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: _invalid_json(),
        )
    except FinalMasterClosureError:
        raise
    except (TypeError, ValueError, UnicodeDecodeError, OverflowError, RecursionError):
        raise FinalMasterClosureError() from None
    if type(value) is not dict:
        raise FinalMasterClosureError()
    return value


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _invalid_json() -> None:
    raise FinalMasterClosureError()
