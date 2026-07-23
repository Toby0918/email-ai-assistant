"""Exact purge planning and corpus-reference checks for a mailbox vault."""

from __future__ import annotations

import hmac
from typing import Callable

from .errors import VaultError
from .models import (
    PurgeReport,
    SecretBuffer,
    VaultRecord,
    VaultWriteIntent,
    VerifyReport,
)
from .vault_crypto import VaultCrypto
from .vault_files import AtomicCiphertextStore
from .vault_index import VaultIndex


def plan_expired_record_ids(
    index: VaultIndex, *, now_utc: int, limit: int,
) -> tuple[str, ...]:
    pending = index.list_delete_pending(limit=limit)
    remaining = limit - len(pending)
    intents = (
        index.list_expired_write_intents(now_utc=now_utc, limit=remaining)
        if remaining else []
    )
    remaining -= len(intents)
    expired = (
        index.list_expired(now_utc=now_utc, limit=remaining)
        if remaining else []
    )
    return tuple(
        record.record_id for record in (*pending, *intents, *expired)
    )


def eligible_planned_records(
    index: VaultIndex, record_ids: tuple[str, ...], *, now_utc: int,
) -> tuple[VaultRecord | VaultWriteIntent, ...]:
    _validate_record_ids(record_ids, maximum=1_000)
    records = {record.record_id: record for record in index.list_records()}
    intents = {
        intent.record_id: intent for intent in index.list_write_intents()
    }
    selected: list[VaultRecord | VaultWriteIntent] = []
    for record_id in record_ids:
        record = records.get(record_id)
        intent = intents.get(record_id)
        if record is not None and intent is not None:
            raise VaultError("index_schema_invalid")
        item = record if record is not None else intent
        if item is None:
            continue
        if isinstance(item, VaultWriteIntent):
            if item.expires_at_utc > now_utc:
                raise VaultError("invalid_expiry")
            selected.append(item)
            continue
        if record is None:
            continue
        if (
            record.lifecycle_state != "delete_pending"
            and record.expires_at_utc > now_utc
        ):
            raise VaultError("invalid_expiry")
        selected.append(record)
    return tuple(selected)


def count_inactive_or_missing_records(
    index: VaultIndex,
    record_ids: tuple[str, ...],
) -> int:
    _validate_record_ids(record_ids, maximum=None)
    records = {record.record_id: record for record in index.list_records()}
    return sum(
        record_id not in records
        or records[record_id].lifecycle_state != "active"
        for record_id in record_ids
    )


def purge_expired_locked(
    index: VaultIndex,
    store: AtomicCiphertextStore,
    *,
    now_utc: int,
    limit: int,
    reconcile: Callable[[int], int],
    delete_record: Callable[[VaultRecord], None],
) -> PurgeReport:
    reconciled = reconcile(limit)
    remaining_budget = limit - reconciled
    intents = (
        index.list_expired_write_intents(
            now_utc=now_utc, limit=remaining_budget,
        ) if remaining_budget else []
    )
    for intent in intents:
        store.unlink(intent.encrypted_relpath)
        index.delete_write_intent(intent.record_id)
    remaining_budget -= len(intents)
    records = (
        index.list_expired(now_utc=now_utc, limit=remaining_budget)
        if remaining_budget else []
    )
    for record in records:
        delete_record(record)
    deleted = reconciled + len(intents) + len(records)
    return PurgeReport(deleted, _remaining_eligible(index, now_utc))


def purge_planned_locked(
    index: VaultIndex,
    store: AtomicCiphertextStore,
    record_ids: tuple[str, ...],
    *,
    now_utc: int,
    delete_record: Callable[[VaultRecord], None],
) -> PurgeReport:
    records = eligible_planned_records(index, record_ids, now_utc=now_utc)
    for record in records:
        if isinstance(record, VaultRecord):
            delete_record(record)
        else:
            store.unlink(record.encrypted_relpath)
            index.delete_write_intent(record.record_id)
    return PurgeReport(len(records), _remaining_eligible(index, now_utc))


def verify_vault(
    index: VaultIndex,
    crypto: VaultCrypto,
    store: AtomicCiphertextStore,
) -> VerifyReport:
    records = index.list_records()
    write_intents = index.list_write_intents()
    indexed_paths = {
        item.encrypted_relpath for item in (*records, *write_intents)
    }
    actual_paths = store.iter_paths()
    stage_paths = store.iter_stage_paths()
    intent_paths = {
        intent.encrypted_relpath for intent in write_intents
    }
    managed_stages = {
        path for path in stage_paths
        if path in intent_paths and path not in actual_paths
    }
    missing = 0
    integrity_failures = 0
    pending = 0
    for record in records:
        if record.lifecycle_state == "delete_pending":
            pending += 1
        elif not store.exists(record.encrypted_relpath):
            missing += 1
        elif not record_integrity_ok(crypto, store, record):
            integrity_failures += 1
    return VerifyReport(
        total_count=len(records),
        missing_count=missing,
        orphan_count=(
            len(actual_paths - indexed_paths)
            + len(stage_paths - managed_stages)
        ),
        integrity_failure_count=integrity_failures,
        delete_pending_count=pending,
        write_pending_count=len(write_intents),
    )


def record_integrity_ok(
    crypto: VaultCrypto,
    store: AtomicCiphertextStore,
    record: VaultRecord,
) -> bool:
    plaintext: SecretBuffer | None = None
    try:
        frame = store.read(
            record.encrypted_relpath, max_size=record.ciphertext_size,
        )
        if len(frame) != record.ciphertext_size:
            return False
        plaintext = crypto.decrypt(record.record_id, frame)
        expected_hmac = crypto.dedup_hmac(plaintext)
        return hmac.compare_digest(expected_hmac, record.dedup_hmac)
    except VaultError:
        return False
    finally:
        if plaintext is not None:
            plaintext.wipe()


def _remaining_eligible(index: VaultIndex, now_utc: int) -> int:
    return (
        index.count_expired(now_utc=now_utc)
        + index.count_delete_pending()
        + index.count_expired_write_intents(now_utc=now_utc)
    )


def _validate_record_ids(
    record_ids: tuple[str, ...], *, maximum: int | None,
) -> None:
    if (
        not isinstance(record_ids, tuple)
        or (maximum is not None and len(record_ids) > maximum)
        or any(not _is_record_id(value) for value in record_ids)
        or len(set(record_ids)) != len(record_ids)
    ):
        raise VaultError("invalid_record_id")


def _is_record_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 32
        and value == value.lower()
        and set(value).issubset(set("0123456789abcdef"))
    )


__all__ = [
    "count_inactive_or_missing_records",
    "eligible_planned_records",
    "plan_expired_record_ids",
    "purge_expired_locked",
    "purge_planned_locked",
    "record_integrity_ok",
    "verify_vault",
]
