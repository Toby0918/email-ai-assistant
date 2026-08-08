"""Strict canonical JSON and domain-separated identity primitives."""

from __future__ import annotations

import hashlib
import json


_MAX_JSON_BYTES = 2 * 1024 * 1024


class CanonicalDataError(ValueError):
    """Private parse failure with no input-derived message."""


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise CanonicalDataError() from None


def fingerprint(domain: str, value: object) -> str:
    try:
        prefix = domain.encode("ascii")
    except (AttributeError, UnicodeEncodeError):
        raise CanonicalDataError() from None
    return hashlib.sha256(prefix + b"\0" + canonical_json(value)).hexdigest()


def strict_object(payload: object) -> dict[str, object]:
    if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_JSON_BYTES:
        raise CanonicalDataError()

    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if type(key) is not str or key in result:
                raise CanonicalDataError()
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda _value: _reject_constant(),
        )
    except CanonicalDataError:
        raise
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError):
        raise CanonicalDataError() from None
    if type(value) is not dict or canonical_json(value) != payload:
        raise CanonicalDataError()
    return value


def is_fingerprint(value: object) -> bool:
    return _is_lower_hex(value, 64)


def is_git_oid(value: object) -> bool:
    return _is_lower_hex(value, 40)


def is_nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_lower_hex(value: object, length: int) -> bool:
    return (
        type(value) is str
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _reject_constant() -> None:
    raise CanonicalDataError()


class CanonicalValue:
    """Immutable canonical bytes with copy-on-read mapping access."""

    __slots__ = ("_canonical_bytes",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("canonical values require a named factory")

    def __getattr__(self, name: str) -> object:
        mapping = self.to_mapping()
        if name not in mapping:
            raise AttributeError(name)
        return mapping[name]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<content-free>)"

    def __eq__(self, other: object) -> bool:
        return type(other) is type(self) and other.to_canonical_json() == self.to_canonical_json()

    def to_mapping(self) -> dict[str, object]:
        return strict_object(self._canonical_bytes)

    def to_canonical_json(self) -> bytes:
        return self._canonical_bytes


def allocate_value(kind: type[CanonicalValue], mapping: dict[str, object]) -> CanonicalValue:
    value = object.__new__(kind)
    object.__setattr__(value, "_canonical_bytes", canonical_json(mapping))
    return value
