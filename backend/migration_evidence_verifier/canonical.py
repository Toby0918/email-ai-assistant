"""Canonical content-free verifier records and fingerprints."""

from __future__ import annotations

import hashlib
import json


class VerifierProcessError(Exception):
    """Private fixed verifier failure."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def decode_canonical_object(payload: bytes) -> dict[str, object]:
    def reject_constant(_value: str):
        raise VerifierProcessError

    def object_pairs(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        value: dict[str, object] = {}
        for key, item in pairs:
            if key in value:
                raise VerifierProcessError
            value[key] = item
        return value

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=reject_constant,
        )
    except VerifierProcessError:
        raise
    except Exception:
        raise VerifierProcessError from None
    if type(value) is not dict or canonical_json(value) != payload:
        raise VerifierProcessError
    return value


def is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(
            character in "0123456789abcdef"
            for character in value
        )
    )
