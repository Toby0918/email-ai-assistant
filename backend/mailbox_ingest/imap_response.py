"""Strict parsing for bounded IMAP response shapes."""

from __future__ import annotations

import re
from datetime import datetime

from .folder_policy import RawFolder
from .imap_errors import ImapReadOnlyError


_LIST_RESPONSE = re.compile(rb'^\(([^)]*)\) "([^"]*)" ("(?:[^"\\]|\\.)*"|[^ ]+)$')
_SIZE_RESPONSE = re.compile(
    rb'^([1-9][0-9]*) \(RFC822\.SIZE ([0-9]+) INTERNALDATE "([^"]+)"\)$'
)
_BODYSTRUCTURE_RESPONSE = re.compile(
    rb'^([1-9][0-9]*) \(BODYSTRUCTURE (.*)\)$', re.DOTALL
)
_LITERAL_HEADER = re.compile(
    rb'^([1-9][0-9]*) \(BODY\[([^]]+)\](?:<([0-9]+)>)? \{([0-9]+)\}$'
)


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
    match = _SIZE_RESPONSE.fullmatch(data[0])
    if match is None or int(match.group(1)) != uid:
        raise ImapReadOnlyError()
    try:
        internal_date = datetime.strptime(
            match.group(3).decode("ascii"), "%d-%b-%Y %H:%M:%S %z"
        )
    except (UnicodeError, ValueError):
        raise ImapReadOnlyError() from None
    return int(match.group(2)), internal_date


def parse_bodystructure_response(data: object, uid: int) -> str:
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], bytes):
        raise ImapReadOnlyError()
    match = _BODYSTRUCTURE_RESPONSE.fullmatch(data[0])
    if match is None or int(match.group(1)) != uid:
        raise ImapReadOnlyError()
    try:
        return match.group(2).decode("ascii", errors="strict")
    except UnicodeError:
        raise ImapReadOnlyError() from None


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
    if match is None or int(match.group(1)) != uid:
        raise ImapReadOnlyError()
    try:
        response_section = match.group(2).decode("ascii", errors="strict")
    except UnicodeError:
        raise ImapReadOnlyError() from None
    expected_offset = None if offset is None else str(offset).encode("ascii")
    if (
        response_section != section
        or match.group(3) != expected_offset
        or int(match.group(4)) != len(literal)
        or count is not None and len(literal) > count
    ):
        raise ImapReadOnlyError()
    return literal


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
        mailbox = raw_mailbox.decode("utf-8", errors="strict")
    except UnicodeError:
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
