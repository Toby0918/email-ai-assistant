"""Strict shared validation for encrypted mailbox scan-record envelopes."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from datetime import datetime

from .bodystructure import MAX_PARTS
from .bodystructure_syntax import MAX_STRING_LENGTH
from .first_pass_transfer import MAX_HEADER_BYTES
from .text_body_decoder import MAX_DECODED_TEXT_BYTES


RAW_SCAN_RECORD_FIELDS = frozenset({
    "schema_version", "scope", "fingerprint", "opaque_folder_id", "mailbox",
    "uidvalidity", "uid", "internal_date", "expires_at_utc", "header_b64",
    "bodies_b64", "attachments",
})
GOVERNED_SCAN_RECORD_FIELDS = (
    RAW_SCAN_RECORD_FIELDS | {"learning_projection"}
)
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_SECTION = re.compile(r"^[1-9][0-9]*(?:\.[1-9][0-9]*)*$")
_MIME = re.compile(r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")
_MAX_TIMESTAMP = 253_402_300_799
_MAX_PROJECTION_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class ValidatedScanRecord:
    value: dict[str, object] = field(repr=False)
    internal_date: datetime
    header: bytes = field(repr=False)
    bodies: tuple[bytes, ...] = field(repr=False)


def validate_scan_record(value: object) -> ValidatedScanRecord:
    if not isinstance(value, dict):
        raise ValueError
    version = value.get("schema_version")
    expected = (
        RAW_SCAN_RECORD_FIELDS if version == 1
        else GOVERNED_SCAN_RECORD_FIELDS if version == 2
        else None
    )
    if type(version) is not int or expected is None or set(value) != expected:
        raise ValueError
    if not all(
        _matches(_HEX64, value.get(name))
        for name in ("scope", "fingerprint", "opaque_folder_id")
    ):
        raise ValueError
    _validate_location_and_time(value)
    header = _decode_base64(value["header_b64"], MAX_HEADER_BYTES)
    bodies = _decode_bodies(value["bodies_b64"])
    _validate_attachments(value["attachments"])
    if version == 2:
        projection = value["learning_projection"]
        if (
            type(projection) is not str
            or not projection
            or len(projection.encode("utf-8")) > _MAX_PROJECTION_BYTES
        ):
            raise ValueError
    internal = _parse_internal_date(value["internal_date"])
    return ValidatedScanRecord(value, internal, header, bodies)


def _validate_location_and_time(value: dict[str, object]) -> None:
    mailbox = value["mailbox"]
    if (
        type(mailbox) is not str
        or not mailbox
        or len(mailbox) > MAX_STRING_LENGTH
        or any(ord(character) < 32 for character in mailbox)
        or type(value["uidvalidity"]) is not int
        or not 1 <= value["uidvalidity"] <= 4_294_967_295
        or type(value["uid"]) is not int
        or not 1 <= value["uid"] <= 4_294_967_295
        or type(value["expires_at_utc"]) is not int
        or not 0 <= value["expires_at_utc"] <= _MAX_TIMESTAMP
    ):
        raise ValueError


def _decode_bodies(value: object) -> tuple[bytes, ...]:
    if not isinstance(value, list) or len(value) > MAX_PARTS:
        raise ValueError
    bodies = tuple(
        _decode_base64(item, MAX_DECODED_TEXT_BYTES) for item in value
    )
    if sum(map(len, bodies)) > MAX_DECODED_TEXT_BYTES:
        raise ValueError
    return bodies


def _decode_base64(value: object, maximum: int) -> bytes:
    if type(value) is not str or not value.isascii():
        raise ValueError
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError from None
    if (
        len(decoded) > maximum
        or base64.b64encode(decoded).decode("ascii") != value
    ):
        raise ValueError
    return decoded


def _validate_attachments(value: object) -> None:
    if not isinstance(value, list) or len(value) > MAX_PARTS:
        raise ValueError
    keys = {"candidate_id", "section", "mime_type", "size", "filename"}
    for item in value:
        if not isinstance(item, dict) or set(item) != keys:
            raise ValueError
        filename = item["filename"]
        if (
            not _matches(_HEX32, item.get("candidate_id"))
            or not _matches(_SECTION, item.get("section"))
            or not _matches(_MIME, item.get("mime_type"))
            or type(item["size"]) is not int
            or not 0 <= item["size"] <= _MAX_TIMESTAMP
            or (
                filename is not None
                and (
                    type(filename) is not str
                    or not filename
                    or len(filename) > MAX_STRING_LENGTH
                    or any(ord(character) < 32 for character in filename)
                )
            )
        ):
            raise ValueError


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _parse_internal_date(value: object) -> datetime:
    if type(value) is not str or len(value) > 64:
        raise ValueError
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError
    return parsed


__all__ = [
    "GOVERNED_SCAN_RECORD_FIELDS",
    "RAW_SCAN_RECORD_FIELDS",
    "ValidatedScanRecord",
    "validate_scan_record",
]
