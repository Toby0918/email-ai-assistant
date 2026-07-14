"""Strict parsing for bounded IMAP response shapes."""

from __future__ import annotations

import re
from datetime import datetime

from .bodystructure_syntax import BodyStructureError, parse_sexpression
from .folder_policy import RawFolder
from .imap_errors import ImapReadOnlyError
from .imap_utf7 import MailboxDecodeError, decode_modified_utf7


_LIST_RESPONSE = re.compile(rb'^\(([^)]*)\) "([^"]*)" ("(?:[^"\\]|\\.)*"|[^ ]+)$')
_FETCH_RESPONSE = re.compile(rb'^([1-9][0-9]*) (\(.*\))$', re.DOTALL)
_LITERAL_HEADER = re.compile(
    rb'^([1-9][0-9]*) \(UID ([1-9][0-9]*) BODY\[([^]]+)\]'
    rb'(?:<([0-9]+)>)? \{([0-9]+)\}$'
)
_MAX_UID = 4_294_967_295


def parse_list_response(data: object) -> tuple[RawFolder, ...]:
    if not isinstance(data, list) or not data:
        raise ImapReadOnlyError()
    folders = tuple(_parse_list_item(item) for item in data)
    if len({folder.mailbox.casefold() for folder in folders}) != len(folders):
        raise ImapReadOnlyError()
    return folders


def parse_uidvalidity(select_data: object, code: object, response_data: object) -> int:
    if (
        not isinstance(select_data, list)
        or len(select_data) != 1
        or not isinstance(select_data[0], bytes)
        or not select_data[0].isdigit()
        or code != "UIDVALIDITY"
        or not isinstance(response_data, list)
        or len(response_data) != 1
        or not isinstance(response_data[0], bytes)
        or not response_data[0].isdigit()
    ):
        raise ImapReadOnlyError()
    value = int(response_data[0])
    if value < 1:
        raise ImapReadOnlyError()
    return value


def parse_search_response(data: object) -> tuple[int, ...]:
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], bytes):
        raise ImapReadOnlyError()
    if not data[0]:
        return ()
    try:
        uids = tuple(int(item) for item in data[0].split())
    except ValueError:
        raise ImapReadOnlyError() from None
    if len(set(uids)) != len(uids):
        raise ImapReadOnlyError()
    return uids


def parse_size_response(data: object, uid: int) -> tuple[int, datetime]:
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], bytes):
        raise ImapReadOnlyError()
    items = _requested_fetch_items(
        data[0], uid, {"UID", "RFC822.SIZE", "INTERNALDATE"}
    )
    size = items["RFC822.SIZE"]
    raw_date = items["INTERNALDATE"]
    if type(size) is not int or size < 0 or not isinstance(raw_date, str):
        raise ImapReadOnlyError()
    try:
        internal_date = datetime.strptime(raw_date, "%d-%b-%Y %H:%M:%S %z")
    except ValueError:
        raise ImapReadOnlyError() from None
    return size, internal_date


def parse_bodystructure_response(data: object, uid: int) -> str:
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], bytes):
        raise ImapReadOnlyError()
    items = _requested_fetch_items(data[0], uid, {"UID", "BODYSTRUCTURE"})
    bodystructure = items["BODYSTRUCTURE"]
    if not isinstance(bodystructure, list):
        raise ImapReadOnlyError()
    return _serialize_sexpression(bodystructure)


def parse_literal_response(
    data: object,
    *,
    uid: int,
    section: str,
    offset: int | None,
    count: int | None,
) -> bytes:
    if not isinstance(data, list) or len(data) != 2 or data[1] != b")":
        raise ImapReadOnlyError()
    first = data[0]
    if not isinstance(first, tuple) or len(first) != 2:
        raise ImapReadOnlyError()
    if not all(isinstance(item, bytes) for item in first):
        raise ImapReadOnlyError()
    header, literal = first
    match = _LITERAL_HEADER.fullmatch(header)
    if (
        match is None
        or not _valid_sequence_number(match.group(1))
        or int(match.group(2)) != uid
    ):
        raise ImapReadOnlyError()
    try:
        response_section = match.group(3).decode("ascii", errors="strict")
    except UnicodeError:
        raise ImapReadOnlyError() from None
    expected_offset = None if offset is None else str(offset).encode("ascii")
    if (
        response_section != section
        or match.group(4) != expected_offset
        or int(match.group(5)) != len(literal)
        or count is not None and len(literal) > count
    ):
        raise ImapReadOnlyError()
    return literal


def _requested_fetch_items(
    line: bytes,
    uid: int,
    expected: set[str],
) -> dict[str, object]:
    match = _FETCH_RESPONSE.fullmatch(line)
    if match is None or not _valid_sequence_number(match.group(1)):
        raise ImapReadOnlyError()
    try:
        parsed = parse_sexpression(match.group(2).decode("ascii", errors="strict"))
    except (BodyStructureError, UnicodeError):
        raise ImapReadOnlyError() from None
    if not isinstance(parsed, list) or len(parsed) % 2:
        raise ImapReadOnlyError()
    items: dict[str, object] = {}
    for offset in range(0, len(parsed), 2):
        key = parsed[offset]
        if not isinstance(key, str):
            raise ImapReadOnlyError()
        normalized = key.upper()
        if normalized in items:
            raise ImapReadOnlyError()
        items[normalized] = parsed[offset + 1]
    if set(items) != expected or items.get("UID") != uid:
        raise ImapReadOnlyError()
    return items


def _valid_sequence_number(value: bytes) -> bool:
    number = int(value)
    return 1 <= number <= _MAX_UID


def _serialize_sexpression(value: object) -> str:
    if isinstance(value, list):
        return "(" + " ".join(_serialize_sexpression(item) for item in value) + ")"
    if value is None:
        return "NIL"
    if type(value) is int and value >= 0:
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise ImapReadOnlyError()


def _parse_list_item(item: object) -> RawFolder:
    if not isinstance(item, bytes):
        raise ImapReadOnlyError()
    match = _LIST_RESPONSE.fullmatch(item)
    if match is None:
        raise ImapReadOnlyError()
    try:
        flags = tuple(value.decode("ascii") for value in match.group(1).split())
        raw_mailbox = match.group(3)
        if raw_mailbox.startswith(b'"'):
            raw_mailbox = raw_mailbox[1:-1].replace(b'\\"', b'"').replace(b"\\\\", b"\\")
        mailbox = decode_modified_utf7(raw_mailbox)
    except (MailboxDecodeError, UnicodeError):
        raise ImapReadOnlyError() from None
    return RawFolder(flags, mailbox)


__all__ = [
    "parse_bodystructure_response",
    "parse_list_response",
    "parse_literal_response",
    "parse_search_response",
    "parse_size_response",
    "parse_uidvalidity",
]
