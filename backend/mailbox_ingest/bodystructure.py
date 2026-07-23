"""Bounded, fail-closed parser for IMAP BODYSTRUCTURE values."""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.header import decode_header
from urllib.parse import unquote_to_bytes

from .bodystructure_syntax import (
    BodyStructureError,
    MAX_STRING_LENGTH,
    parse_sexpression,
)

MAX_PARTS = 256
_ENCODINGS = {"7BIT", "8BIT", "BINARY", "BASE64", "QUOTED-PRINTABLE"}
_CHARSETS = {
    "ascii": "us-ascii",
    "us-ascii": "us-ascii",
    "utf-8": "utf-8",
    "utf8": "utf-8",
    "gb18030": "gb18030",
    "gbk": "gbk",
    "big5": "big5",
    "iso-8859-1": "iso-8859-1",
    "windows-1252": "windows-1252",
}


@dataclass(frozen=True)
class AttachmentMetadata:
    section: str
    mime_type: str
    size: int
    filename: str | None = None


@dataclass(frozen=True)
class TextBodySection:
    section: str
    transfer_encoding: str
    charset: str
    size: int
    mime_type: str = "text/plain"


@dataclass(frozen=True)
class BodyPlan:
    body_sections: tuple[TextBodySection, ...]
    attachments: tuple[AttachmentMetadata, ...]


def parse_bodystructure(source: str) -> BodyPlan:
    root = parse_sexpression(source)
    if not isinstance(root, list) or not root:
        raise BodyStructureError()
    attachments: list[AttachmentMetadata] = []
    bodies, part_count = _walk(root, "", attachments)
    if part_count > MAX_PARTS:
        raise BodyStructureError()
    return BodyPlan(tuple(bodies), tuple(attachments))


def _walk(
    node: list[object],
    prefix: str,
    attachments: list[AttachmentMetadata],
) -> tuple[list[TextBodySection], int]:
    if node and isinstance(node[0], list):
        parts: list[list[object]] = []
        offset = 0
        while offset < len(node) and isinstance(node[offset], list):
            parts.append(node[offset])
            offset += 1
        if not parts or offset >= len(node) or not isinstance(node[offset], str):
            raise BodyStructureError()
        subtype = node[offset].upper()
        candidates: list[tuple[str, list[TextBodySection]]] = []
        count = 0
        for index, part in enumerate(parts, start=1):
            section = f"{prefix}.{index}" if prefix else str(index)
            body, child_count = _walk(part, section, attachments)
            candidates.append((_body_kind(part), body))
            count += child_count
        if subtype == "ALTERNATIVE":
            for wanted in ("text/plain", "text/html"):
                for kind, body in candidates:
                    if kind == wanted and body:
                        return body[:1], count
            return [], count
        return [item for _kind, body in candidates for item in body], count

    return _single_part(node, prefix or "1", attachments), 1


def _single_part(
    node: list[object],
    section: str,
    attachments: list[AttachmentMetadata],
) -> list[TextBodySection]:
    if len(node) < 7 or not isinstance(node[0], str) or not isinstance(node[1], str):
        raise BodyStructureError()
    media_type = node[0].upper()
    subtype = node[1].upper()
    if media_type == "MESSAGE" and subtype == "RFC822":
        raise BodyStructureError("message_rfc822_forbidden")
    encoding = node[5]
    size = node[6]
    if not isinstance(encoding, str) or encoding.upper() not in _ENCODINGS:
        raise BodyStructureError()
    if type(size) is not int or size < 0:
        raise BodyStructureError()
    parameters = _parameters(node[2])
    disposition_index = 9 if media_type == "TEXT" else 8
    disposition, disposition_parameters = _disposition(
        node[disposition_index] if len(node) > disposition_index else None
    )
    filename = _filename(parameters, disposition_parameters)
    mime_type = f"{media_type.lower()}/{subtype.lower()}"
    is_attachment = disposition == "ATTACHMENT" or filename is not None
    if is_attachment:
        attachments.append(AttachmentMetadata(section, mime_type, size, filename))
        return []
    if mime_type not in {"text/plain", "text/html"}:
        return []
    charset = _text_charset(parameters)
    return [TextBodySection(section, encoding.upper(), charset, size, mime_type)]


def _text_charset(parameters: dict[str, str]) -> str:
    raw = parameters.get("CHARSET", "us-ascii")
    if not isinstance(raw, str) or not raw or len(raw) > 64:
        raise BodyStructureError()
    normalized = raw.casefold()
    if normalized not in _CHARSETS:
        raise BodyStructureError()
    return _CHARSETS[normalized]


def _body_kind(node: list[object]) -> str:
    if len(node) >= 2 and isinstance(node[0], str) and isinstance(node[1], str):
        return f"{node[0].lower()}/{node[1].lower()}"
    return "multipart"


def _parameters(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, list) or len(value) % 2:
        raise BodyStructureError()
    result: dict[str, str] = {}
    for offset in range(0, len(value), 2):
        key, item = value[offset:offset + 2]
        if not isinstance(key, str) or not isinstance(item, str):
            raise BodyStructureError()
        normalized = key.upper()
        if normalized in result:
            raise BodyStructureError()
        result[normalized] = item
    return result


def _disposition(value: object) -> tuple[str | None, dict[str, str]]:
    if value is None:
        return None, {}
    if not isinstance(value, list) or not value or not isinstance(value[0], str):
        raise BodyStructureError()
    if len(value) > 2:
        raise BodyStructureError()
    return value[0].upper(), _parameters(value[1] if len(value) == 2 else None)


def _filename(params: dict[str, str], disposition: dict[str, str]) -> str | None:
    values = (
        _parameter_filename(params, "NAME"),
        _parameter_filename(disposition, "FILENAME"),
    )
    decoded = {value for value in values if value is not None}
    if len(decoded) > 1:
        raise BodyStructureError()
    return next(iter(decoded), None)


def _parameter_filename(params: dict[str, str], base: str) -> str | None:
    direct: list[str] = []
    if base in params:
        direct.append(_decode_filename(params[base]))
    if f"{base}*" in params:
        direct.append(_decode_extended(params[f"{base}*"]))
    segments: list[tuple[int, bool, str]] = []
    prefix = f"{base}*"
    for key, value in params.items():
        if not key.startswith(prefix) or key == prefix:
            continue
        match = re.fullmatch(r"(\d+)(\*)?", key[len(prefix):])
        if match is None:
            raise BodyStructureError()
        segments.append((int(match.group(1)), match.group(2) is not None, value))
    if direct and segments:
        raise BodyStructureError()
    if direct:
        if len(set(direct)) != 1:
            raise BodyStructureError()
        return direct[0]
    if not segments:
        return None
    segments.sort(key=lambda item: item[0])
    if [item[0] for item in segments] != list(range(len(segments))):
        raise BodyStructureError()
    return _decode_continuation(segments)


def _decode_continuation(segments: list[tuple[int, bool, str]]) -> str:
    if not any(encoded for _index, encoded, _value in segments):
        return _decode_filename("".join(value for _index, _encoded, value in segments))
    if not segments[0][1]:
        raise BodyStructureError()
    charset, first = _extended_parts(segments[0][2])
    raw = bytearray(_percent_decode(first))
    try:
        for _index, encoded, value in segments[1:]:
            raw.extend(_percent_decode(value) if encoded else value.encode("ascii"))
        return _validate_filename(bytes(raw).decode(charset, errors="strict"))
    except (LookupError, UnicodeError, ValueError):
        raise BodyStructureError() from None


def _decode_extended(value: str) -> str:
    charset, encoded = _extended_parts(value)
    try:
        return _validate_filename(
            _percent_decode(encoded).decode(charset, errors="strict")
        )
    except (LookupError, UnicodeError, ValueError):
        raise BodyStructureError() from None


def _extended_parts(value: str) -> tuple[str, str]:
    try:
        charset, _language, encoded = value.split("'", 2)
    except ValueError:
        raise BodyStructureError() from None
    if not charset:
        raise BodyStructureError()
    return charset, encoded


def _percent_decode(value: str) -> bytes:
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        raise BodyStructureError()
    return unquote_to_bytes(value)


def _decode_filename(value: str) -> str:
    try:
        pieces: list[str] = []
        for item, charset in decode_header(value):
            pieces.append(
                item.decode(charset or "ascii", errors="strict")
                if isinstance(item, bytes)
                else item
            )
        result = "".join(pieces)
    except (LookupError, UnicodeError, ValueError):
        raise BodyStructureError() from None
    return _validate_filename(result)


def _validate_filename(result: str) -> str:
    if not result or len(result) > MAX_STRING_LENGTH or any(ord(c) < 32 for c in result):
        raise BodyStructureError()
    return result


__all__ = [
    "AttachmentMetadata",
    "BodyPlan",
    "BodyStructureError",
    "TextBodySection",
    "parse_bodystructure",
]
