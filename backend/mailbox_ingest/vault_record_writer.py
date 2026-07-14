"""Locked encrypted-record writer shared by normal and deduplicated inserts."""

from __future__ import annotations

from .models import PutRecordResult, SecretBuffer, VaultRecord
from .vault_crypto import FRAME_VERSION, VaultCrypto
from .vault_files import AtomicCiphertextStore
from .vault_index import VaultIndex


def write_vault_record(
    plaintext: SecretBuffer,
    *,
    now: int,
    expires_at_utc: int,
    identifiers: tuple[str, str],
    crypto: VaultCrypto,
    index: VaultIndex,
    store: AtomicCiphertextStore,
    digest: bytes | None = None,
) -> PutRecordResult:
    """Write one record while the caller holds the cross-process mutation lock."""

    record_id, path_token = identifiers
    relative_path = f"records/{path_token[:2]}/{path_token}.mvlt"
    ciphertext = crypto.encrypt(record_id, plaintext)
    metadata = VaultRecord(
        record_id=record_id,
        encrypted_relpath=relative_path,
        dedup_hmac=crypto.dedup_hmac(plaintext) if digest is None else digest,
        created_at_utc=now,
        expires_at_utc=expires_at_utc,
        ciphertext_size=len(ciphertext),
        format_version=FRAME_VERSION,
        key_version=crypto.key_version,
        lifecycle_state="active",
    )
    store.write(relative_path, ciphertext)
    index.add_record(metadata)
    return PutRecordResult(record_id, True)


__all__ = ["write_vault_record"]
