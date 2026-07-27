"""Content-free canonical fingerprints for evidence publication."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def fingerprint(domain: str, value: object) -> str:
    payload = json.dumps(
        {"domain": domain, "value": value},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def path_fingerprint(path: Path) -> str:
    return hashlib.sha256(
        os.path.normcase(str(path)).encode("utf-8")
    ).hexdigest()


def object_identity_fingerprint(path: Path) -> str:
    metadata = os.stat(path, follow_symlinks=False)
    return fingerprint(
        "migration-evidence-object-identity-v1",
        {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "mode": metadata.st_mode,
        },
    )


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
