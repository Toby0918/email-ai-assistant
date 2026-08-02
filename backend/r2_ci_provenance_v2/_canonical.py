"""Canonical content-free identity helpers for Issue #100."""

from __future__ import annotations

import hashlib
import json

from .errors import R2CiProvenanceError


def canonical_json(value):
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("ascii")


def fingerprint(domain, value):
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical_json(value)).hexdigest()


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def is_fingerprint(value):
    return _is_hex(value, 64)


def is_oid(value):
    return _is_hex(value, 40)


def strict_object(payload):
    if type(payload) is not bytes or not 1 <= len(payload) <= 262_144:
        raise R2CiProvenanceError()

    def pairs(values):
        result = {}
        for key, value in values:
            if type(key) is not str or key in result:
                raise R2CiProvenanceError()
            result[key] = value
        return result

    try:
        value = json.loads(payload.decode("ascii"), object_pairs_hook=pairs,
                           parse_constant=lambda _value: _invalid())
    except R2CiProvenanceError:
        raise
    except Exception:
        raise R2CiProvenanceError() from None
    if type(value) is not dict:
        raise R2CiProvenanceError()
    return value


def _is_hex(value, size):
    return type(value) is str and len(value) == size and all(
        character in "0123456789abcdef" for character in value
    )


def _invalid():
    raise R2CiProvenanceError()
