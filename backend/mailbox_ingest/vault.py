"""Encrypted record lifecycle over a metadata-only index and ciphertext store."""

from __future__ import annotations

import calendar
import hmac
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .errors import VaultError
from .key_envelopes import revoke_key_envelopes
from .models import (
    PurgeReport,
    RevokeResult,
    SecretBuffer,
    VaultRecord,
    VerifyReport,
)
from .vault_crypto import FRAME_VERSION, VaultCrypto
from .vault_files import AtomicCiphertextStore
from .vault_index import MAX_BATCH_LIMIT, VaultIndex, VaultMutationLock


def max_expiry_utc(now_utc: int, *, months: int = 24) -> int:
    if type(now_utc) is not int or type(months) is not int or months <= 0:
        raise VaultError("invalid_expiry")
    try:
        current = datetime.fromtimestamp(now_utc, timezone.utc)
        month_index = current.month - 1 + months
        year = current.year + month_index // 12
        month = month_index % 12 + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return int(current.replace(year=year, month=month, day=day).timestamp())
    except (OverflowError, OSError, ValueError):
        raise VaultError("invalid_expiry") from None


class MailboxVault:
    def __init__(
        self,
        vault_root: Path,
        *,
        vault_id: str,
        crypto: VaultCrypto,
        index: VaultIndex,
        ciphertext_store: AtomicCiphertextStore | None = None,
        clock: Callable[[], int],
        random_identifier: Callable[[], str] | None = None,
    ) -> None:
        self._root = Path(vault_root)
        self._vault_id = vault_id
        self._crypto = crypto
        self._index = index
        self._store = (
            AtomicCiphertextStore(self._root)
            if ciphertext_store is None
            else ciphertext_store
        )
        self._clock = clock
        self._random_identifier = (
            (lambda: secrets.token_hex(16))
            if random_identifier is None
            else random_identifier
        )
        self.mutation_lock = VaultMutationLock(self._root / ".mutation.lock")

    def _ensure_active(self) -> None:
        if self._index.get_vault_state() != "active":
            raise VaultError("vault_revoked")

    def _now(self) -> int:
        try:
            now = self._clock()
        except Exception:
            raise VaultError("invalid_expiry") from None
        if type(now) is not int:
            raise VaultError("invalid_expiry")
        return now

    def _new_identifiers(self) -> tuple[str, str]:
        try:
            record_id = self._random_identifier()
            path_token = self._random_identifier()
        except Exception:
            raise VaultError("invalid_record_id") from None
        _validate_identifier(record_id)
        _validate_identifier(path_token)
        if path_token == record_id:
            raise VaultError("invalid_record_id")
        return record_id, path_token

    def put_record(
        self, plaintext: bytes | bytearray, *, expires_at_utc: int
    ) -> str:
        now = self._now()
        _validate_expiry(expires_at_utc, now)
        local = SecretBuffer(plaintext) if isinstance(plaintext, (bytes, bytearray)) else None
        if local is None:
            raise VaultError("record_too_large")
        try:
            with self.mutation_lock:
                self._ensure_active()
                record_id, path_token = self._new_identifiers()
                relative_path = f"records/{path_token[:2]}/{path_token}.mvlt"
                ciphertext = self._crypto.encrypt(record_id, local)
                metadata = VaultRecord(
                    record_id=record_id,
                    encrypted_relpath=relative_path,
                    dedup_hmac=self._crypto.dedup_hmac(local),
                    created_at_utc=now,
                    expires_at_utc=expires_at_utc,
                    ciphertext_size=len(ciphertext),
                    format_version=FRAME_VERSION,
                    key_version=self._crypto.key_version,
                    lifecycle_state="active",
                )
                self._store.write(relative_path, ciphertext)
                self._index.add_record(metadata)
                return record_id
        finally:
            local.wipe()

    def get_record(self, record_id: str) -> SecretBuffer:
        self._ensure_active()
        metadata = self._index.get_record(record_id)
        if metadata is None or metadata.lifecycle_state != "active":
            raise VaultError("record_not_found")
        if metadata.expires_at_utc <= self._now():
            raise VaultError("record_not_found")
        frame = self._store.read(
            metadata.encrypted_relpath, max_size=metadata.ciphertext_size
        )
        if len(frame) != metadata.ciphertext_size:
            raise VaultError("ciphertext_read_failed")
        return self._crypto.decrypt(record_id, frame)

    def delete_record(self, record_id: str) -> None:
        with self.mutation_lock:
            self._ensure_active()
            record = self._index.get_record(record_id)
            if record is None:
                raise VaultError("record_not_found")
            self._delete_locked(record)

    def _delete_locked(self, record: VaultRecord) -> None:
        if record.lifecycle_state != "delete_pending":
            self._index.mark_delete_pending(record.record_id)
        self._store.unlink(record.encrypted_relpath)
        self._index.delete_record(record.record_id)

    def reconcile_delete_pending(self, *, limit: int = 100) -> int:
        _validate_limit(limit)
        with self.mutation_lock:
            return self._reconcile_locked(limit)

    def _reconcile_locked(self, limit: int) -> int:
        reconciled = 0
        for record in self._index.list_delete_pending(limit=limit):
            self._store.unlink(record.encrypted_relpath)
            self._index.delete_record(record.record_id)
            reconciled += 1
        return reconciled

    def purge_expired(self, *, limit: int = 100) -> PurgeReport:
        _validate_limit(limit)
        now = self._now()
        with self.mutation_lock:
            self._ensure_active()
            reconciled = self._reconcile_locked(limit)
            remaining_budget = limit - reconciled
            records = (
                self._index.list_expired(now_utc=now, limit=remaining_budget)
                if remaining_budget
                else []
            )
            for record in records:
                self._delete_locked(record)
            remaining = (
                self._index.count_expired(now_utc=now)
                + self._index.count_delete_pending()
            )
        return PurgeReport(reconciled + len(records), remaining)

    def verify(self) -> VerifyReport:
        with self.mutation_lock:
            records = self._index.list_records()
            indexed_paths = {record.encrypted_relpath for record in records}
            actual_paths = self._store.iter_paths()
            missing = 0
            integrity_failures = 0
            pending = 0
            for record in records:
                if record.lifecycle_state == "delete_pending":
                    pending += 1
                    continue
                if not self._store.exists(record.encrypted_relpath):
                    missing += 1
                    continue
                if not self._record_integrity_ok(record):
                    integrity_failures += 1
            return VerifyReport(
                total_count=len(records),
                missing_count=missing,
                orphan_count=len(actual_paths - indexed_paths),
                integrity_failure_count=integrity_failures,
                delete_pending_count=pending,
            )

    def _record_integrity_ok(self, record: VaultRecord) -> bool:
        plaintext: SecretBuffer | None = None
        try:
            frame = self._store.read(
                record.encrypted_relpath, max_size=record.ciphertext_size
            )
            if len(frame) != record.ciphertext_size:
                return False
            plaintext = self._crypto.decrypt(record.record_id, frame)
            expected_hmac = self._crypto.dedup_hmac(plaintext)
            return hmac.compare_digest(expected_hmac, record.dedup_hmac)
        except VaultError:
            return False
        finally:
            if plaintext is not None:
                plaintext.wipe()

    def revoke(
        self,
        confirmation: str,
        *,
        envelope_revoker: Callable[[], None] | None = None,
    ) -> RevokeResult:
        if confirmation != f"REVOKE:{self._vault_id}":
            raise VaultError("revoke_confirmation_required")
        revoker = (
            (lambda: revoke_key_envelopes(self._root))
            if envelope_revoker is None
            else envelope_revoker
        )
        with self.mutation_lock:
            if self._index.get_vault_state() == "revoked":
                return RevokeResult("revoked")
            self._index.set_vault_state("revoking")
            try:
                try:
                    revoker()
                except Exception:
                    self._mark_revoke_incomplete()
                    raise VaultError("revoke_incomplete") from None
                try:
                    self._index.set_vault_state("revoked")
                except VaultError:
                    self._mark_revoke_incomplete()
                    raise
                except Exception:
                    self._mark_revoke_incomplete()
                    raise VaultError("index_write_failed") from None
                return RevokeResult("revoked")
            finally:
                self._crypto.close()

    def _mark_revoke_incomplete(self) -> None:
        try:
            self._index.set_vault_state("revoke_incomplete")
        except Exception:
            pass

    def __repr__(self) -> str:
        return "MailboxVault(<redacted>)"


def _validate_identifier(value: object) -> None:
    if not isinstance(value, str) or len(value) != 32:
        raise VaultError("invalid_record_id")
    if value != value.lower() or any(character not in "0123456789abcdef" for character in value):
        raise VaultError("invalid_record_id")


def _validate_expiry(expires_at_utc: object, now_utc: int) -> None:
    if type(expires_at_utc) is not int:
        raise VaultError("invalid_expiry")
    if expires_at_utc > max_expiry_utc(now_utc, months=24):
        raise VaultError("expiry_exceeds_retention")


def _validate_limit(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= MAX_BATCH_LIMIT:
        raise VaultError("invalid_limit")


__all__ = ["AtomicCiphertextStore", "MailboxVault", "max_expiry_utc"]
