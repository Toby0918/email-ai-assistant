"""Fingerprint-gated first-pass mailbox scanning into the encrypted vault."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Callable

from .authorization import add_calendar_months
from .bodystructure import BodyStructureError, parse_bodystructure
from .control_store import ControlStoreError
from .inventory import InventoryBundle
from .scan_record import ScanRecordError, encode_scan_record
from .text_body_decoder import decode_text_body


class ScanError(ValueError):
    def __init__(self, code: str = "scan_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"ScanError(code={self.code!r})"


@dataclass(frozen=True)
class ScanReport:
    processed_count: int
    created_count: int
    duplicate_count: int
    sensitive_count: int
    ambiguous_count: int


def classify_message(header: bytes, bodies: tuple[bytes, ...]) -> str:
    """Conservative local filter; uncertain decoding is ambiguous."""

    try:
        text = b"\n".join((header, *bodies)).decode("utf-8", errors="strict").casefold()
    except UnicodeError:
        return "ambiguous"
    sensitive = (
        "payroll", "salary", "medical", "health record", "password",
        "credential", "security incident", "人事", "薪资", "医疗", "密码", "安全事件",
    )
    return "sensitive" if any(marker in text for marker in sensitive) else "eligible"


def scan_mailbox(
    *,
    session: object,
    inventory_bundle: InventoryBundle,
    confirmed_fingerprint: str,
    vault: object,
    control_store: object,
    rebuild_inventory: Callable[[], InventoryBundle],
    classifier: Callable[[bytes, tuple[bytes, ...]], str] = classify_message,
    candidate_id_factory: Callable[[], str] = lambda: secrets.token_hex(16),
) -> ScanReport:
    inventory = inventory_bundle.inventory
    _verify_inventory(inventory_bundle, confirmed_fingerprint, rebuild_inventory)
    state = _load_or_create_state(control_store, inventory_bundle)
    counters = [0, 0, 0, 0, 0]
    for folder in inventory_bundle.evidence:
        _scan_folder(
            session, folder, inventory, state, counters, vault, control_store,
            classifier, candidate_id_factory,
        )
    return ScanReport(*counters)


def _verify_inventory(
    bundle: InventoryBundle,
    confirmed_fingerprint: str,
    rebuild_inventory: Callable[[], InventoryBundle],
) -> None:
    if confirmed_fingerprint != bundle.inventory.fingerprint:
        raise ScanError("inventory_fingerprint_mismatch")
    try:
        rebuilt = rebuild_inventory()
    except Exception:
        raise ScanError("inventory_recompute_failed") from None
    if (
        not isinstance(rebuilt, InventoryBundle)
        or rebuilt.inventory.fingerprint != bundle.inventory.fingerprint
    ):
        raise ScanError("inventory_changed")


def _scan_folder(
    session: object, folder: object, inventory: object, state: dict[str, object],
    counters: list[int], vault: object, control_store: object,
    classifier: Callable[[bytes, tuple[bytes, ...]], str],
    candidate_id_factory: Callable[[], str],
) -> None:
    folder_state = state["folders"].get(folder.opaque_folder_id)
    if not isinstance(folder_state, dict):
        raise ScanError("scan_state_invalid")
    _require_uidvalidity(session, folder.mailbox, folder.uidvalidity)
    cursor = folder_state.get("cursor")
    if type(cursor) is not int or cursor < 0:
        raise ScanError("scan_state_invalid")
    for message in folder.messages:
        if message.uid <= cursor:
            continue
        _require_uidvalidity(session, folder.mailbox, folder.uidvalidity)
        outcome = _process_one(
            session, folder.mailbox, inventory.opaque_scope_id,
            inventory.fingerprint, folder.opaque_folder_id, folder.uidvalidity,
            message, vault, classifier, candidate_id_factory,
        )
        _count_outcome(counters, outcome)
        folder_state["cursor"] = message.uid
        folder_state["processed_count"] = int(
            folder_state.get("processed_count", 0)
        ) + 1
        try:
            control_store.write("scan-state", state)
        except Exception:
            raise ScanError("scan_state_write_failed") from None


def _count_outcome(counters: list[int], outcome: str) -> None:
    positions = {"created": 1, "duplicate": 2, "sensitive": 3}
    counters[0] += 1
    counters[positions.get(outcome, 4)] += 1


def _process_one(
    session: object,
    mailbox: str,
    scope: str,
    fingerprint: str,
    opaque_folder_id: str,
    uidvalidity: int,
    message: object,
    vault: object,
    classifier: Callable[[bytes, tuple[bytes, ...]], str],
    candidate_id_factory: Callable[[], str],
) -> str:
    try:
        source = session.uid_fetch_bodystructure(message.uid)
        plan = parse_bodystructure(source)
    except Exception:
        return "ambiguous"
    try:
        header = session.uid_fetch_peek(message.uid, "HEADER")
        bodies = tuple(
            decode_text_body(
                part,
                session.uid_fetch_peek(message.uid, part.section),
            )
            for part in plan.body_sections
        )
        classification = classifier(header, bodies)
    except Exception:
        return "ambiguous"
    if classification not in {"eligible", "sensitive", "ambiguous"}:
        return "ambiguous"
    if classification != "eligible":
        return classification
    expires = int(add_calendar_months(message.internal_date, 24).timestamp())
    record = _encode_eligible_record(
        scope, fingerprint, opaque_folder_id, mailbox, uidvalidity, message,
        expires, header, bodies, plan.attachments, candidate_id_factory,
    )
    try:
        result = vault.put_record_if_absent(record, expires_at_utc=expires)
    except Exception:
        raise ScanError("scan_persist_failed") from None
    return "created" if result.created else "duplicate"


def _encode_eligible_record(
    scope: str, fingerprint: str, opaque_folder_id: str, mailbox: str,
    uidvalidity: int, message: object, expires: int, header: bytes,
    bodies: tuple[bytes, ...], attachments: tuple[object, ...],
    candidate_id_factory: Callable[[], str],
) -> bytes:
    try:
        return encode_scan_record(
            scope=scope,
            fingerprint=fingerprint,
            opaque_folder_id=opaque_folder_id,
            mailbox=mailbox,
            uidvalidity=uidvalidity,
            uid=message.uid,
            internal_date=message.internal_date,
            expires_at_utc=expires,
            header=header,
            bodies=bodies,
            attachments=attachments,
            candidate_id_factory=candidate_id_factory,
        )
    except ScanRecordError as error:
        raise ScanError(str(error)) from None


def _load_or_create_state(control_store: object, bundle: InventoryBundle) -> dict[str, object]:
    inventory = bundle.inventory
    try:
        state = control_store.read("scan-state")
    except ControlStoreError as error:
        if error.code != "control_store_missing":
            raise ScanError("scan_state_invalid") from None
        state = {
            "schema_version": 1,
            "scope": inventory.opaque_scope_id,
            "fingerprint": inventory.fingerprint,
            "window_start": inventory.window_start.isoformat(),
            "window_end": inventory.window_end.isoformat(),
            "folders": {
                folder.opaque_folder_id: {
                    "uidvalidity": folder.uidvalidity,
                    "cursor": 0,
                    "processed_count": 0,
                }
                for folder in bundle.evidence
            },
        }
        try:
            control_store.write("scan-state", state)
        except Exception:
            raise ScanError("scan_state_write_failed") from None
    _validate_state(state, bundle)
    return state


def _validate_state(state: object, bundle: InventoryBundle) -> None:
    inventory = bundle.inventory
    if not isinstance(state, dict) or set(state) != {
        "schema_version", "scope", "fingerprint", "window_start", "window_end", "folders"
    }:
        raise ScanError("scan_state_invalid")
    if (
        state["schema_version"] != 1
        or state["scope"] != inventory.opaque_scope_id
        or state["fingerprint"] != inventory.fingerprint
        or state["window_start"] != inventory.window_start.isoformat()
        or state["window_end"] != inventory.window_end.isoformat()
        or not isinstance(state["folders"], dict)
        or set(state["folders"]) != {folder.opaque_folder_id for folder in bundle.evidence}
    ):
        raise ScanError("scan_state_invalid")
    expected = {folder.opaque_folder_id: folder.uidvalidity for folder in bundle.evidence}
    for folder_id, folder_state in state["folders"].items():
        if (
            not isinstance(folder_state, dict)
            or set(folder_state) != {"uidvalidity", "cursor", "processed_count"}
            or folder_state["uidvalidity"] != expected[folder_id]
        ):
            raise ScanError("scan_state_invalid")


def _require_uidvalidity(session: object, mailbox: str, expected: int) -> None:
    try:
        actual = session.examine(mailbox)
    except Exception:
        raise ScanError("uidvalidity_check_failed") from None
    if actual != expected:
        raise ScanError("uidvalidity_changed")


__all__ = ["ScanError", "ScanReport", "classify_message", "scan_mailbox"]
