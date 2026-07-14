"""Codec for inventory evidence stored only inside encrypted control state."""

from __future__ import annotations

from datetime import datetime, timezone

from .inventory import (
    FolderEvidence,
    FolderInventory,
    InventoryBundle,
    InventoryError,
    InventoryV1,
    MessageEvidence,
)
from .imap_utf7 import MailboxDecodeError, decode_modified_utf7


def encode_inventory_bundle(bundle: InventoryBundle) -> dict[str, object]:
    inventory = bundle.inventory
    return {
        "schema_version": 1,
        "public": inventory.to_dict(),
        "evidence": [
            {
                "mailbox": folder.mailbox,
                "wire_mailbox": folder.wire_mailbox.decode("ascii"),
                "opaque_folder_id": folder.opaque_folder_id,
                "uidvalidity": folder.uidvalidity,
                "messages": [
                    {
                        "uid": message.uid,
                        "size": message.size,
                        "internal_date": message.internal_date.isoformat(),
                    }
                    for message in folder.messages
                ],
            }
            for folder in bundle.evidence
        ],
    }


def decode_inventory_bundle(payload: object) -> InventoryBundle:
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version", "public", "evidence"
    } or payload["schema_version"] != 1:
        raise InventoryError("inventory_control_invalid")
    public = payload["public"]
    evidence = payload["evidence"]
    if not isinstance(public, dict) or set(public) != {
        "schema_version", "opaque_scope_id", "endpoint", "window_start",
        "window_end", "folders", "total_count", "aggregate_size", "fingerprint",
    }:
        raise InventoryError("inventory_control_invalid")
    if public["schema_version"] != 1 or public["endpoint"] != "tencent_exmail_fixed_imaps_v1":
        raise InventoryError("inventory_control_invalid")
    try:
        folders = tuple(_public_folder(item) for item in public["folders"])
        inventory = InventoryV1(
            _hex(public["opaque_scope_id"], 64),
            _datetime(public["window_start"]),
            _datetime(public["window_end"]),
            folders,
            _integer(public["total_count"], minimum=0),
            _integer(public["aggregate_size"], minimum=0),
            _hex(public["fingerprint"], 64),
        )
        private = tuple(_private_folder(item) for item in evidence)
    except (TypeError, KeyError, InventoryError):
        raise InventoryError("inventory_control_invalid") from None
    if (
        inventory.window_start >= inventory.window_end
        or inventory.total_count != sum(folder.count for folder in folders)
        or inventory.aggregate_size != sum(folder.aggregate_size for folder in folders)
        or {folder.opaque_folder_id for folder in folders}
        != {folder.opaque_folder_id for folder in private}
    ):
        raise InventoryError("inventory_control_invalid")
    return InventoryBundle(inventory, private)


def _public_folder(value: object) -> FolderInventory:
    if not isinstance(value, dict) or set(value) != {
        "opaque_folder_id", "uidvalidity", "count", "aggregate_size"
    }:
        raise InventoryError()
    return FolderInventory(
        _hex(value["opaque_folder_id"], 64),
        _integer(value["uidvalidity"], minimum=1),
        _integer(value["count"], minimum=0),
        _integer(value["aggregate_size"], minimum=0),
    )


def _private_folder(value: object) -> FolderEvidence:
    if not isinstance(value, dict) or set(value) != {
        "mailbox", "wire_mailbox", "opaque_folder_id", "uidvalidity", "messages"
    }:
        raise InventoryError()
    mailbox = value["mailbox"]
    wire_mailbox = value["wire_mailbox"]
    messages = value["messages"]
    if (
        not isinstance(mailbox, str)
        or not mailbox
        or not isinstance(wire_mailbox, str)
        or not wire_mailbox.isascii()
        or not isinstance(messages, list)
    ):
        raise InventoryError()
    try:
        wire = wire_mailbox.encode("ascii")
        if decode_modified_utf7(wire) != mailbox:
            raise InventoryError()
    except (MailboxDecodeError, UnicodeError):
        raise InventoryError() from None
    parsed = tuple(_message(item) for item in messages)
    if len({item.uid for item in parsed}) != len(parsed):
        raise InventoryError()
    return FolderEvidence(
        mailbox,
        _hex(value["opaque_folder_id"], 64),
        _integer(value["uidvalidity"], minimum=1),
        parsed,
        wire,
    )


def _message(value: object) -> MessageEvidence:
    if not isinstance(value, dict) or set(value) != {"uid", "size", "internal_date"}:
        raise InventoryError()
    return MessageEvidence(
        _integer(value["uid"], minimum=1, maximum=4_294_967_295),
        _integer(value["size"], minimum=0),
        _datetime(value["internal_date"]),
    )


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise InventoryError()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InventoryError() from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InventoryError()
    return parsed.astimezone(timezone.utc)


def _integer(value: object, *, minimum: int, maximum: int | None = None) -> int:
    if type(value) is not int or value < minimum or maximum is not None and value > maximum:
        raise InventoryError()
    return value


def _hex(value: object, length: int) -> str:
    if (
        not isinstance(value, str)
        or len(value) != length
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise InventoryError()
    return value


__all__ = ["decode_inventory_bundle", "encode_inventory_bundle"]
