"""Fixed-endpoint, read-only Tencent Exmail IMAP transport wrapper."""

from __future__ import annotations

import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .folder_policy import RawFolder
from .imap_errors import ImapReadOnlyError
from .imap_response import (
    parse_bodystructure_response,
    parse_list_response,
    parse_literal_response,
    parse_search_response,
    parse_size_response,
    parse_uidvalidity,
)


IMAP_HOST = "imap.exmail.qq.com"
IMAP_PORT = 993
IMAP_TIMEOUT_SECONDS = 10
MAX_IMAP_UID = 4_294_967_295
MAX_PARTIAL_COUNT = 1024 * 1024
_SECTION = re.compile(r"^[1-9][0-9]*(?:\.[1-9][0-9]*)*$")
_PARTIAL_SELECTOR = re.compile(
    r"^\(BODY\.PEEK\[([1-9][0-9]*(?:\.[1-9][0-9]*)*)\]"
    r"<([0-9]+)\.([1-9][0-9]*)>\)$"
)
_PEEK_SELECTOR = re.compile(
    r"^\(BODY\.PEEK\[(HEADER|[1-9][0-9]*(?:\.[1-9][0-9]*)*)\]\)$"
)
_FIXED_SELECTORS = {"(RFC822.SIZE INTERNALDATE)", "(BODYSTRUCTURE)"}
@dataclass(frozen=True)
class SizeEvidence:
    uid: int
    size: int
    internal_date: datetime


def validate_single_uid_fetch_target(uid: int) -> str:
    if type(uid) is not int or not 1 <= uid <= MAX_IMAP_UID:
        raise ImapReadOnlyError("imap_uid_invalid")
    return str(uid)


def validate_fetch_selector(selector: str) -> str:
    if not isinstance(selector, str) or selector != selector.strip():
        raise ImapReadOnlyError("imap_selector_invalid")
    if selector in _FIXED_SELECTORS or _PEEK_SELECTOR.fullmatch(selector):
        return selector
    partial = _PARTIAL_SELECTOR.fullmatch(selector)
    if partial is None:
        raise ImapReadOnlyError("imap_selector_invalid")
    try:
        offset = int(partial.group(2))
        count = int(partial.group(3))
    except ValueError:
        raise ImapReadOnlyError("imap_selector_invalid") from None
    if offset > 2**63 - 1 or count > MAX_PARTIAL_COUNT:
        raise ImapReadOnlyError("imap_selector_invalid")
    return selector


class ReadOnlyImapSession:
    """Expose six bounded operations and fixed LOGIN/LOGOUT lifecycle only."""

    def __init__(
        self,
        account: str,
        password: str,
        *,
        client_factory: Callable[..., object] = imaplib.IMAP4_SSL,
    ) -> None:
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        try:
            self._imap_client = client_factory(
                IMAP_HOST,
                IMAP_PORT,
                ssl_context=context,
                timeout=IMAP_TIMEOUT_SECONDS,
            )
            status, _data = self._imap_client.login(account, password)
        except Exception:
            raise ImapReadOnlyError("imap_connect_failed") from None
        _require_ok(status, "imap_login_failed")
        self._logged_out = False

    def __enter__(self) -> "ReadOnlyImapSession":
        return self

    def __exit__(self, exception_type: object, *_args: object) -> None:
        if self._logged_out:
            return
        self._logged_out = True
        try:
            status, _data = self._imap_client.logout()
            _require_ok_or_bye(status)
        except ImapReadOnlyError:
            if exception_type is None:
                raise
        except Exception:
            if exception_type is None:
                raise ImapReadOnlyError("imap_logout_failed") from None

    def list_folders(self) -> tuple[RawFolder, ...]:
        try:
            status, data = self._imap_client.list()
        except Exception:
            raise ImapReadOnlyError("imap_list_failed") from None
        _require_ok(status, "imap_list_failed")
        return parse_list_response(data)

    def examine(self, mailbox: str) -> int:
        if not isinstance(mailbox, str) or not mailbox or any(ord(c) < 32 for c in mailbox):
            raise ImapReadOnlyError("imap_mailbox_invalid")
        try:
            status, data = self._imap_client.select(mailbox=mailbox, readonly=True)
            response_code, response_data = self._imap_client.response("UIDVALIDITY")
        except Exception:
            raise ImapReadOnlyError("imap_examine_failed") from None
        _require_ok(status, "imap_examine_failed")
        return parse_uidvalidity(data, response_code, response_data)

    def uid_search(self, since: datetime) -> tuple[int, ...]:
        if not isinstance(since, datetime) or since.tzinfo is None or since.utcoffset() is None:
            raise ImapReadOnlyError("imap_search_date_invalid")
        date = since.strftime("%d-%b-%Y")
        try:
            status, data = self._imap_client.uid("SEARCH", None, "SINCE", date)
        except Exception:
            raise ImapReadOnlyError("imap_search_failed") from None
        _require_ok(status, "imap_search_failed")
        uids = parse_search_response(data)
        for uid in uids:
            validate_single_uid_fetch_target(uid)
        return uids

    def uid_fetch_size(self, uid: int) -> SizeEvidence:
        size, internal_date = parse_size_response(
            self._fetch(uid, "(RFC822.SIZE INTERNALDATE)"), uid
        )
        return SizeEvidence(uid, size, internal_date)

    def uid_fetch_bodystructure(self, uid: int) -> str:
        return parse_bodystructure_response(self._fetch(uid, "(BODYSTRUCTURE)"), uid)

    def uid_fetch_peek(
        self,
        uid: int,
        section: str,
        *,
        offset: int | None = None,
        count: int | None = None,
    ) -> bytes:
        selector = _peek_selector(section, offset=offset, count=count)
        return parse_literal_response(
            self._fetch(uid, selector),
            uid=uid,
            section=section,
            offset=offset,
            count=count,
        )

    def _fetch(self, uid: int, selector: str) -> list[object]:
        try:
            status, data = self._imap_client.uid(
                "FETCH", validate_single_uid_fetch_target(uid), validate_fetch_selector(selector)
            )
        except ImapReadOnlyError:
            raise
        except Exception:
            raise ImapReadOnlyError("imap_fetch_failed") from None
        _require_ok(status, "imap_fetch_failed")
        if not isinstance(data, list):
            raise ImapReadOnlyError()
        return data

    def __repr__(self) -> str:
        return "ReadOnlyImapSession(<redacted>)"


def _peek_selector(section: str, *, offset: int | None, count: int | None) -> str:
    if section != "HEADER" and (
        not isinstance(section, str) or _SECTION.fullmatch(section) is None
    ):
        raise ImapReadOnlyError("imap_selector_invalid")
    if (offset is None) != (count is None):
        raise ImapReadOnlyError("imap_selector_invalid")
    if offset is None:
        return validate_fetch_selector(f"(BODY.PEEK[{section}])")
    if type(offset) is not int or offset < 0 or type(count) is not int or count < 1:
        raise ImapReadOnlyError("imap_selector_invalid")
    return validate_fetch_selector(f"(BODY.PEEK[{section}]<{offset}.{count}>)")


def _require_ok(status: object, code: str) -> None:
    if status != "OK":
        raise ImapReadOnlyError(code)


def _require_ok_or_bye(status: object) -> None:
    if status not in {"OK", "BYE"}:
        raise ImapReadOnlyError("imap_logout_failed")


__all__ = [
    "IMAP_HOST",
    "IMAP_PORT",
    "ImapReadOnlyError",
    "ReadOnlyImapSession",
    "SizeEvidence",
    "validate_fetch_selector",
    "validate_single_uid_fetch_target",
]
