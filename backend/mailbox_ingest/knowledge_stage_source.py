"""One-record-at-a-time raw-vault reader for the administrator staging bridge."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from pathlib import Path
from typing import Callable

from .dpapi import DpapiProtector
from .errors import VaultError
from .existing_vault_policy import validate_existing_vault_location
from .models import SecretBuffer
from .vault_access import open_mailbox_vault


_RECORD_ID = re.compile(r"^[0-9a-f]{32}$")
_ORGANIZATION_DISPLAY = re.compile(
    r"(?i)(?:\b(?:ltd|limited|llc|inc|corp|corporation|company|gmbh|plc)\.?$|"
    r"(?:有限公司|股份有限公司|集团|公司)$)"
)
_FIELDS = {
    "schema_version", "scope", "fingerprint", "opaque_folder_id", "mailbox",
    "uidvalidity", "uid", "internal_date", "expires_at_utc", "header_b64",
    "bodies_b64", "attachments",
}


class RawStageRecord:
    __slots__ = ("text", "context")

    def __init__(
        self,
        text: str,
        people: list[str],
        organizations: list[str],
    ) -> None:
        if not _valid_identity_list(people) or not _valid_identity_list(organizations):
            raise VaultError("stage_record_invalid")
        self.text = text
        self.context = {"people": people, "organizations": organizations}

    def close(self) -> None:
        self.text = ""
        self.context = {}

    def __repr__(self) -> str:
        return "RawStageRecord(<redacted>)"


class _RawRecordContext:
    __slots__ = ("_source", "_record_id", "_record")

    def __init__(self, source: MailboxKnowledgeStageSource, record_id: str) -> None:
        self._source = source
        self._record_id = record_id
        self._record: RawStageRecord | None = None

    def __enter__(self) -> RawStageRecord:
        if self._record is not None:
            raise VaultError("stage_record_invalid")
        secret = self._source._opened.vault.get_record(self._record_id)
        if not isinstance(secret, SecretBuffer):
            raise VaultError("stage_record_invalid")
        with secret:
            self._record = self._source._decode(bytes(secret), self._record_id)
        return self._record

    def __exit__(self, *_args: object) -> None:
        if self._record is not None:
            self._record.close()
            self._record = None

    def __repr__(self) -> str:
        return "RawRecordContext(<redacted>)"


class MailboxKnowledgeStageSource:
    def __init__(
        self,
        opened: object,
        *,
        expected_scope: str,
        account: str,
        window_start: datetime,
        window_end: datetime,
        expected_fingerprint: str | None = None,
        retain_evidence: bool = True,
    ) -> None:
        self._opened = opened
        self._scope = expected_scope
        self._account_domain = account.rsplit("@", 1)[-1].casefold()
        self._window_start = window_start
        self._window_end = window_end
        self._fingerprint = expected_fingerprint
        self._threads: set[str] | None = set() if retain_evidence else None
        self._counterparties: set[str] | None = set() if retain_evidence else None
        self._closed = False

    def read_one_record(self, record_id: str) -> _RawRecordContext:
        if self._closed or not isinstance(record_id, str) or _RECORD_ID.fullmatch(record_id) is None:
            raise VaultError("stage_record_invalid")
        return _RawRecordContext(self, record_id)

    @property
    def evidence(self) -> tuple[str, str]:
        if self._threads is None or self._counterparties is None:
            raise VaultError("stage_evidence_unavailable")
        return (_conversation_bucket(len(self._threads)),
                _counterparty_bucket(len(self._counterparties)))

    def _decode(self, payload: bytes, record_id: str) -> RawStageRecord:
        try:
            value = json.loads(payload.decode("ascii"))
            _validate_record(
                value, self._scope, self._window_start, self._window_end,
                self._fingerprint,
            )
            header = base64.b64decode(value["header_b64"], validate=True)
            bodies = tuple(base64.b64decode(item, validate=True) for item in value["bodies_b64"])
            if sum(map(len, (header, *bodies))) > 25 * 1024 * 1024:
                raise ValueError
            message = BytesParser(policy=policy.default).parsebytes(header)
            people, organizations, addresses = _header_identities(message)
            if self._counterparties is not None and self._threads is not None:
                self._counterparties.update(
                    address.rsplit("@", 1)[-1].casefold()
                    for address in addresses
                    if "@" in address
                    and not address.casefold().endswith("@" + self._account_domain)
                )
                self._threads.add(_thread_key(message, record_id))
            filenames = _filenames(value["attachments"])
            text = "\n".join(
                [header.decode("utf-8", errors="replace")]
                + [item.decode("utf-8", errors="replace") for item in bodies]
                + filenames
            )
            return RawStageRecord(text, people, organizations)
        except (ValueError, TypeError, KeyError, UnicodeError, json.JSONDecodeError):
            raise VaultError("stage_record_invalid") from None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._threads is not None:
            self._threads.clear()
        if self._counterparties is not None:
            self._counterparties.clear()
        self._opened.close()

    def __enter__(self) -> MailboxKnowledgeStageSource:
        if self._closed:
            raise VaultError("stage_source_closed")
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "MailboxKnowledgeStageSource(<redacted>)"


def open_knowledge_stage_source(
    vault_root: Path,
    *,
    authorization_id: str,
    account: str,
    expected_vault_id: str,
    expected_scope: str,
    window_start: datetime,
    window_end: datetime,
    project_root: Path,
    validate_existing: Callable[..., object] = validate_existing_vault_location,
    dpapi_factory: Callable[[], object] = DpapiProtector,
    opener: Callable[..., object] = open_mailbox_vault,
    clock: Callable[[], int],
    expected_fingerprint: str | None = None,
    retain_evidence: bool = True,
) -> MailboxKnowledgeStageSource:
    validate_existing(Path(vault_root), Path(project_root))
    opened = opener(Path(vault_root), dpapi=dpapi_factory(), clock=clock)
    try:
        scope = opened.require_authorization_scope(authorization_id, account)
        if (getattr(opened.identity, "vault_id", None) != expected_vault_id
                or getattr(scope, "opaque_scope_id", None) != expected_scope):
            raise VaultError("stage_scope_mismatch")
        return MailboxKnowledgeStageSource(
            opened, expected_scope=expected_scope, account=account,
            window_start=window_start, window_end=window_end,
            expected_fingerprint=expected_fingerprint,
            retain_evidence=retain_evidence,
        )
    except Exception:
        opened.close()
        raise


def open_evaluation_stage_source(
    vault_root: Path,
    *,
    authorization_id: str,
    account: str,
    expected_vault_id: str,
    expected_scope: str,
    expected_fingerprint: str,
    window_start: datetime,
    window_end: datetime,
    project_root: Path,
    validate_existing: Callable[..., object] = validate_existing_vault_location,
    dpapi_factory: Callable[[], object] = DpapiProtector,
    opener: Callable[..., object] = open_mailbox_vault,
    clock: Callable[[], int],
) -> MailboxKnowledgeStageSource:
    return open_knowledge_stage_source(
        vault_root, authorization_id=authorization_id, account=account,
        expected_vault_id=expected_vault_id, expected_scope=expected_scope,
        window_start=window_start, window_end=window_end,
        project_root=project_root, validate_existing=validate_existing,
        dpapi_factory=dpapi_factory, opener=opener, clock=clock,
        expected_fingerprint=expected_fingerprint, retain_evidence=False,
    )


def _validate_record(
    value: object,
    scope: str,
    start: datetime,
    end: datetime,
    fingerprint: str | None,
) -> None:
    if (not isinstance(value, dict) or set(value) != _FIELDS
            or value["schema_version"] != 1 or value["scope"] != scope
            or (fingerprint is not None and value["fingerprint"] != fingerprint)
            or not isinstance(value["bodies_b64"], list)
            or not isinstance(value["attachments"], list)):
        raise ValueError
    internal = datetime.fromisoformat(value["internal_date"])
    if internal.utcoffset() is None or not start <= internal < end:
        raise ValueError


def _header_identities(
    message: object,
) -> tuple[list[str], list[str], list[str]]:
    values: list[str] = []
    for name in ("from", "to", "cc", "reply-to"):
        values.extend(str(item) for item in message.get_all(name, []))
    pairs = getaddresses(values)
    names = {name.strip() for name, _address in pairs if 1 <= len(name.strip()) <= 200}
    organizations = sorted(name for name in names if _ORGANIZATION_DISPLAY.search(name))
    people = sorted(names - set(organizations))
    addresses = [address for _name, address in pairs]
    return people, organizations, addresses


def _valid_identity_list(values: object) -> bool:
    return (
        isinstance(values, list)
        and len(values) <= 100
        and all(
            isinstance(value, str)
            and 1 <= len(value.strip()) <= 200
            and "\r" not in value
            and "\n" not in value
            for value in values
        )
    )


def _thread_key(message: object, fallback: str) -> str:
    references = str(message.get("references", "")).split()
    return (references[0] if references else str(
        message.get("in-reply-to") or message.get("message-id") or fallback
    ))[:500]


def _filenames(attachments: object) -> list[str]:
    result: list[str] = []
    for item in attachments:
        if not isinstance(item, dict):
            raise ValueError
        filename = item.get("filename")
        if isinstance(filename, str) and filename:
            result.append(filename[:500])
    return result


def _conversation_bucket(count: int) -> str:
    return "1" if count <= 1 else "2" if count == 2 else "3-5" if count <= 5 else "6-10" if count <= 10 else "11+"


def _counterparty_bucket(count: int) -> str:
    return "1" if count <= 1 else "2-3" if count <= 3 else "4-10" if count <= 10 else "11+"
