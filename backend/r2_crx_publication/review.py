"""Held reviewed CRX identity, format, size, and hash."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from backend.r2_database_publication.windows_handle import SourceHandle


@dataclass(frozen=True, slots=True, repr=False)
class ReviewedCrxV1:
    source_identity_fingerprint: str = field(repr=False)
    artifact_hash: str = field(repr=False)
    size_bytes: int
    format_version: int


def review_source(source: Path) -> ReviewedCrxV1:
    handle = SourceHandle(source)
    try:
        observed = handle.observe()
        payload = handle.read_all(limit=1024 * 1024 * 1024)
        return ReviewedCrxV1(
            observed.identity_fingerprint,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            format_version(payload),
        )
    finally:
        handle.close()


def format_version(payload: bytes) -> int:
    if len(payload) < 12 or payload[:4] != b"Cr24":
        raise ValueError("crx_format_invalid")
    version = int.from_bytes(payload[4:8], "little")
    if version == 2 and len(payload) >= 16:
        end = 16 + int.from_bytes(payload[8:12], "little")
        end += int.from_bytes(payload[12:16], "little")
    elif version == 3:
        end = 12 + int.from_bytes(payload[8:12], "little")
    else:
        raise ValueError("crx_format_invalid")
    if end >= len(payload):
        raise ValueError("crx_format_invalid")
    return version
