"""Strict bounded transfer and charset decoding for selected text MIME parts."""

from __future__ import annotations

import base64
import binascii
import quopri
import re

from .bodystructure import TextBodySection


MAX_ENCODED_TEXT_BYTES = 2 * 1024 * 1024
MAX_DECODED_TEXT_BYTES = 4 * 1024 * 1024
_INVALID_QP_ESCAPE = re.compile(rb"=(?!(?:[0-9A-Fa-f]{2}|\r\n))")


class TextBodyDecodeError(ValueError):
    pass


def decode_text_body(part: TextBodySection, payload: bytes) -> bytes:
    if (
        not isinstance(part, TextBodySection)
        or type(payload) is not bytes
        or part.size != len(payload)
        or not 0 <= len(payload) <= MAX_ENCODED_TEXT_BYTES
    ):
        raise TextBodyDecodeError("text_body_decode_failed")
    try:
        decoded = _decode_transfer(part.transfer_encoding, payload)
        text = decoded.decode(part.charset, errors="strict")
        normalized = text.encode("utf-8", errors="strict")
    except (LookupError, UnicodeError, ValueError, binascii.Error):
        raise TextBodyDecodeError("text_body_decode_failed") from None
    if len(decoded) > MAX_DECODED_TEXT_BYTES or len(normalized) > MAX_DECODED_TEXT_BYTES:
        raise TextBodyDecodeError("text_body_decode_failed")
    return normalized


def _decode_transfer(encoding: str, payload: bytes) -> bytes:
    if encoding == "BASE64":
        compact = b"".join(payload.splitlines())
        return base64.b64decode(compact, validate=True)
    if encoding == "QUOTED-PRINTABLE":
        if _INVALID_QP_ESCAPE.search(payload):
            raise TextBodyDecodeError("text_body_decode_failed")
        return quopri.decodestring(payload, header=False)
    if encoding == "7BIT":
        if any(value > 127 for value in payload):
            raise TextBodyDecodeError("text_body_decode_failed")
        return payload
    if encoding == "8BIT":
        return payload
    raise TextBodyDecodeError("text_body_decode_failed")


__all__ = ["TextBodyDecodeError", "decode_text_body"]
