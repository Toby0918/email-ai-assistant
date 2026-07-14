"""Strict RFC 3501 modified UTF-7 decoding for non-UTF8 LIST mailbox names."""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata


MAX_MAILBOX_BYTES = 1_024
_SHIFTED = re.compile(rb"^[A-Za-z0-9+,]+$")


class MailboxDecodeError(ValueError):
    pass


def decode_modified_utf7(value: bytes) -> str:
    if type(value) is not bytes or not value or len(value) > MAX_MAILBOX_BYTES:
        raise MailboxDecodeError("mailbox_decode_failed")
    output: list[str] = []
    offset = 0
    try:
        while offset < len(value):
            byte = value[offset]
            if byte != 0x26:
                if not 0x20 <= byte <= 0x7E:
                    raise MailboxDecodeError("mailbox_decode_failed")
                output.append(chr(byte))
                offset += 1
                continue
            end = value.find(b"-", offset + 1)
            if end < 0:
                raise MailboxDecodeError("mailbox_decode_failed")
            shifted = value[offset + 1:end]
            if not shifted:
                output.append("&")
            else:
                output.append(_decode_shifted(shifted))
            offset = end + 1
    except (UnicodeError, ValueError, binascii.Error):
        raise MailboxDecodeError("mailbox_decode_failed") from None
    normalized = unicodedata.normalize("NFC", "".join(output))
    if not normalized or any(ord(character) < 32 for character in normalized):
        raise MailboxDecodeError("mailbox_decode_failed")
    return normalized


def _decode_shifted(value: bytes) -> str:
    if _SHIFTED.fullmatch(value) is None or len(value) % 4 == 1:
        raise MailboxDecodeError("mailbox_decode_failed")
    standard = value.replace(b",", b"/")
    padded = standard + b"=" * ((-len(standard)) % 4)
    raw = base64.b64decode(padded, validate=True)
    if not raw or len(raw) % 2:
        raise MailboxDecodeError("mailbox_decode_failed")
    decoded = raw.decode("utf-16-be", errors="strict")
    if any(ord(character) <= 0x7F for character in decoded):
        raise MailboxDecodeError("mailbox_decode_failed")
    return decoded


__all__ = ["MailboxDecodeError", "decode_modified_utf7"]
