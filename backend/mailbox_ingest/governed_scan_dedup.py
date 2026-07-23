"""Opaque exact-message identity for governed scan aggregate deduplication."""

from __future__ import annotations

import hashlib
import hmac

from .bodystructure import TextBodySection


def message_outcome_token(
    key: bytes, header: bytes, bodystructure: bytes,
    parts: tuple[TextBodySection, ...], bodies: tuple[bytes, ...],
    attachment_material: bytes,
) -> str:
    digest = hmac.new(
        key, b"governed-scan/message-outcome/v1\0", hashlib.sha256,
    )
    values: list[bytes] = [header, bodystructure]
    for part, body in zip(parts, bodies, strict=True):
        values.extend((_part_material(part), body))
    values.append(attachment_material)
    for value in values:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def _part_material(part: TextBodySection) -> bytes:
    if not isinstance(part, TextBodySection):
        raise ValueError
    return "\0".join((
        part.section,
        part.mime_type,
        part.transfer_encoding,
        part.charset,
        str(part.size),
    )).encode("ascii")


__all__ = ["message_outcome_token"]
