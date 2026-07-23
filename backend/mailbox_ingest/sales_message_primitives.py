"""Bounded canonicalization and HMAC primitives for governed sales messages."""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata


_DOMAIN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\Z"
)
_LOCAL = re.compile(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]+\Z")


def domain(value: object) -> str:
    result = ascii_value(value, 253)
    if not _DOMAIN.fullmatch(result):
        raise ValueError
    return result


def address(value: object) -> str:
    result = ascii_value(value, 254)
    if result.count("@") != 1:
        raise ValueError
    local, selected_domain = result.rsplit("@", 1)
    if (
        not _LOCAL.fullmatch(local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or not _DOMAIN.fullmatch(selected_domain)
    ):
        raise ValueError
    return result


def ascii_value(value: object, limit: int) -> str:
    if type(value) is not str:
        raise ValueError
    result = unicodedata.normalize("NFKC", value).casefold()
    if result != result.strip() or not 1 <= len(result) <= limit:
        raise ValueError
    result.encode("ascii", "strict")
    return result


def has_control(value: str) -> bool:
    return any(
        char not in "\r\n\t" and unicodedata.category(char).startswith("C")
        for char in value
    )


def frame(*fields: bytes) -> bytes:
    return b"".join(len(field).to_bytes(8, "big") + field for field in fields)


def opaque(key: bytes, purpose: bytes, material: bytes) -> bytes:
    framed = b"sales-corpus/v1/" + purpose + b"\0" + material
    return hmac.new(key, framed, hashlib.sha256).digest()


__all__ = ["address", "ascii_value", "domain", "frame", "has_control", "opaque"]
