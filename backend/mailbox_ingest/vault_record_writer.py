"""Crash-recoverable encrypted record writes under the vault mutation lock."""

from __future__ import annotations

import hmac
import re

from .errors import VaultError
from .models import PutRecordResult, SecretBuffer, VaultWriteIntent
from .vault_crypto import FRAME_VERSION, VaultCrypto
from .vault_files import AtomicCiphertextStore
from .vault_index import VaultIndex


_IDENTIFIER = re.compile(r"^[0-9a-f]{32}$")


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
    """Reserve metadata, commit ciphertext, then atomically activate the row."""

    selected_digest = crypto.dedup_hmac(plaintext) if digest is None else digest
    intent = index.find_write_intent(selected_digest)
    ciphertext: bytes | None = None
    if intent is None:
        record_id, path_token = identifiers
        ciphertext = crypto.encrypt(record_id, plaintext)
        intent = index.reserve_write(
            _intent(
                record_id, path_token, selected_digest, now,
                expires_at_utc, len(ciphertext), crypto.key_version,
            )
        )
    intent = index.constrain_write_intent_expiry(
        intent.record_id, expires_at_utc,
    )
    if store.exists(intent.encrypted_relpath):
        _validate_committed_ciphertext(intent, crypto, store)
    else:
        if ciphertext is None or intent.record_id != identifiers[0]:
            ciphertext = crypto.encrypt(intent.record_id, plaintext)
        if len(ciphertext) != intent.ciphertext_size:
            raise VaultError("invalid_record_metadata")
        store.write(intent.encrypted_relpath, ciphertext)
    index.activate_reserved(intent.record_id)
    return PutRecordResult(intent.record_id, True)


def _validate_committed_ciphertext(
    intent: VaultWriteIntent,
    crypto: VaultCrypto,
    store: AtomicCiphertextStore,
) -> None:
    plaintext: SecretBuffer | None = None
    try:
        frame = store.read(
            intent.encrypted_relpath, max_size=intent.ciphertext_size,
        )
        if len(frame) != intent.ciphertext_size:
            raise VaultError("ciphertext_read_failed")
        plaintext = crypto.decrypt(intent.record_id, frame)
        if not hmac.compare_digest(
            crypto.dedup_hmac(plaintext), intent.dedup_hmac,
        ):
            raise VaultError("record_authentication_failed")
    finally:
        if plaintext is not None:
            plaintext.wipe()


def _intent(
    record_id: str,
    path_token: str,
    digest: bytes,
    created: int,
    expires: int,
    ciphertext_size: int,
    key_version: int,
) -> VaultWriteIntent:
    return VaultWriteIntent(
        record_id=record_id,
        encrypted_relpath=f"records/{path_token[:2]}/{path_token}.mvlt",
        dedup_hmac=digest,
        created_at_utc=created,
        expires_at_utc=expires,
        ciphertext_size=ciphertext_size,
        format_version=FRAME_VERSION,
        key_version=key_version,
    )


def validate_identifier(value: object) -> None:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise VaultError("invalid_record_id")


__all__ = ["validate_identifier", "write_vault_record"]
