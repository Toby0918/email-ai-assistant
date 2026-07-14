"""Content-free inventory with a private, HMAC-bound evidence bundle."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .authorization import AuthorizationScope, DateWindow
from .folder_policy import SelectedFolder


class InventoryError(ValueError):
    def __init__(self, code: str = "inventory_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"InventoryError(code={self.code!r})"


@dataclass(frozen=True)
class MessageEvidence:
    uid: int = field(repr=False)
    size: int
    internal_date: datetime = field(repr=False)


@dataclass(frozen=True)
class FolderEvidence:
    mailbox: str = field(repr=False)
    opaque_folder_id: str
    uidvalidity: int
    messages: tuple[MessageEvidence, ...] = field(repr=False)
    wire_mailbox: bytes = field(repr=False, default=b"")


@dataclass(frozen=True)
class FolderInventory:
    opaque_folder_id: str
    uidvalidity: int
    count: int
    aggregate_size: int

    def to_dict(self) -> dict[str, object]:
        return {
            "opaque_folder_id": self.opaque_folder_id,
            "uidvalidity": self.uidvalidity,
            "count": self.count,
            "aggregate_size": self.aggregate_size,
        }


@dataclass(frozen=True)
class InventoryV1:
    opaque_scope_id: str
    window_start: datetime
    window_end: datetime
    folders: tuple[FolderInventory, ...]
    total_count: int
    aggregate_size: int
    fingerprint: str
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "opaque_scope_id": self.opaque_scope_id,
            "endpoint": "tencent_exmail_fixed_imaps_v1",
            "window_start": _iso(self.window_start),
            "window_end": _iso(self.window_end),
            "folders": [item.to_dict() for item in self.folders],
            "total_count": self.total_count,
            "aggregate_size": self.aggregate_size,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class InventoryBundle:
    inventory: InventoryV1
    evidence: tuple[FolderEvidence, ...] = field(repr=False)


def build_inventory(
    session: object,
    *,
    scope: AuthorizationScope,
    folders: tuple[SelectedFolder, ...],
    window: DateWindow,
    fingerprint_key: bytes,
) -> InventoryBundle:
    if type(fingerprint_key) is not bytes or len(fingerprint_key) < 32:
        raise InventoryError()
    public_folders: list[FolderInventory] = []
    evidence_folders: list[FolderEvidence] = []
    for folder in folders:
        public, evidence = _build_folder_inventory(session, folder, window)
        public_folders.append(public)
        evidence_folders.append(evidence)
    public_folders.sort(key=lambda item: item.opaque_folder_id)
    evidence_folders.sort(key=lambda item: item.opaque_folder_id)
    preliminary = InventoryV1(
        scope.opaque_scope_id,
        window.window_start,
        window.window_end,
        tuple(public_folders),
        sum(item.count for item in public_folders),
        sum(item.aggregate_size for item in public_folders),
        "",
    )
    fingerprint = _fingerprint(preliminary, evidence_folders, fingerprint_key)
    inventory = InventoryV1(**{**preliminary.__dict__, "fingerprint": fingerprint})
    return InventoryBundle(inventory, tuple(evidence_folders))


def _build_folder_inventory(
    session: object,
    folder: SelectedFolder,
    window: DateWindow,
) -> tuple[FolderInventory, FolderEvidence]:
    try:
        uidvalidity = session.examine(folder.wire_mailbox)
        candidates = session.uid_search(
            window.window_start.replace(hour=0, minute=0, second=0, microsecond=0)
        )
    except Exception:
        raise InventoryError("inventory_transport_failed") from None
    if type(uidvalidity) is not int or uidvalidity < 1:
        raise InventoryError()
    if not isinstance(candidates, tuple) or len(set(candidates)) != len(candidates):
        raise InventoryError()
    messages = _message_evidence(session, candidates, window)
    aggregate = sum(item.size for item in messages)
    public = FolderInventory(
        folder.opaque_folder_id, uidvalidity, len(messages), aggregate
    )
    private = FolderEvidence(
        folder.mailbox,
        folder.opaque_folder_id,
        uidvalidity,
        tuple(messages),
        folder.wire_mailbox,
    )
    return public, private


def _message_evidence(
    session: object,
    candidates: tuple[int, ...],
    window: DateWindow,
) -> list[MessageEvidence]:
    messages: list[MessageEvidence] = []
    for uid in candidates:
        if type(uid) is not int or not 1 <= uid <= 4_294_967_295:
            raise InventoryError()
        try:
            item = session.uid_fetch_size(uid)
        except Exception:
            raise InventoryError("inventory_transport_failed") from None
        if getattr(item, "uid", None) != uid:
            raise InventoryError()
        size = getattr(item, "size", None)
        internal_date = getattr(item, "internal_date", None)
        _validate_message(size, internal_date, window)
        if window.window_start <= internal_date <= window.window_end:
            messages.append(MessageEvidence(uid, size, internal_date))
    messages.sort(key=lambda item: item.uid)
    return messages


def _validate_message(size: object, internal_date: object, window: DateWindow) -> None:
    if type(size) is not int or size < 0:
        raise InventoryError()
    if (
        not isinstance(internal_date, datetime)
        or internal_date.tzinfo is None
        or internal_date.utcoffset() is None
    ):
        raise InventoryError()
    if internal_date > window.window_end:
        raise InventoryError("inventory_future_internaldate")


def _fingerprint(
    inventory: InventoryV1,
    evidence: list[FolderEvidence],
    key: bytes,
) -> str:
    public = inventory.to_dict()
    public.pop("fingerprint")
    private = [
        {
            "folder": folder.opaque_folder_id,
            "uidvalidity": folder.uidvalidity,
            "messages": [
                [message.uid, message.size, _iso(message.internal_date)]
                for message in folder.messages
            ],
        }
        for folder in evidence
    ]
    payload = json.dumps(
        {"public": public, "private": private},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hmac.new(key, b"mailbox-inventory/v1\0" + payload, hashlib.sha256).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "FolderEvidence",
    "InventoryBundle",
    "InventoryError",
    "InventoryV1",
    "MessageEvidence",
    "build_inventory",
]
