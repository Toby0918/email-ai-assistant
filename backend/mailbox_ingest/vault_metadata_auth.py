"""Purpose-separated authentication for security-sensitive vault metadata."""

from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import replace

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import VaultError
from .models import SecretBuffer, VaultRecord, VaultWriteIntent


_RECORD_INFO = b"mailbox-vault/active-record-metadata-auth/v1"
_INTENT_INFO = b"mailbox-vault/write-intent-metadata-auth/v1"
_RECORD_DOMAIN = b"active-record/v1"
_INTENT_DOMAIN = b"write-intent/v1"
_INTEGER_FIELDS = struct.Struct(">QQQHH")


class VaultMetadataAuthenticator:
    def __init__(self, master_key: bytes | bytearray, vault_id: bytes) -> None:
        self._record_key = _derive_key(master_key, vault_id, _RECORD_INFO)
        self._intent_key = _derive_key(master_key, vault_id, _INTENT_INFO)
        self._closed = False

    def sign_record(self, record: VaultRecord) -> VaultRecord:
        self._ensure_open()
        mac = _mac(self._record_key, _record_payload(record))
        return replace(record, metadata_mac=mac)

    def sign_intent(self, intent: VaultWriteIntent) -> VaultWriteIntent:
        self._ensure_open()
        mac = _mac(self._intent_key, _intent_payload(intent))
        return replace(intent, metadata_mac=mac)

    def verify_record(self, record: VaultRecord) -> None:
        self._ensure_open()
        expected = _mac(self._record_key, _record_payload(record))
        _verify_mac(record.metadata_mac, expected)

    def verify_intent(self, intent: VaultWriteIntent) -> None:
        self._ensure_open()
        expected = _mac(self._intent_key, _intent_payload(intent))
        _verify_mac(intent.metadata_mac, expected)

    def close(self) -> None:
        if self._closed:
            return
        self._record_key.wipe()
        self._intent_key.wipe()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise VaultError("crypto_closed")

    def __repr__(self) -> str:
        return "VaultMetadataAuthenticator(<redacted>)"


def _record_payload(record: VaultRecord) -> bytes:
    return _common_payload(
        _RECORD_DOMAIN, record.record_id, record.encrypted_relpath,
        record.dedup_hmac, record.created_at_utc, record.expires_at_utc,
        record.ciphertext_size, record.format_version, record.key_version,
    ) + _field(record.lifecycle_state.encode("ascii"))


def _intent_payload(intent: VaultWriteIntent) -> bytes:
    return _common_payload(
        _INTENT_DOMAIN, intent.record_id, intent.encrypted_relpath,
        intent.dedup_hmac, intent.created_at_utc, intent.expires_at_utc,
        intent.ciphertext_size, intent.format_version, intent.key_version,
    )


def _common_payload(
    domain: bytes,
    record_id: str,
    encrypted_relpath: str,
    dedup_hmac: bytes,
    created: int,
    expires: int,
    ciphertext_size: int,
    format_version: int,
    key_version: int,
) -> bytes:
    try:
        integers = _INTEGER_FIELDS.pack(
            created, expires, ciphertext_size, format_version, key_version,
        )
        return b"".join((
            _field(domain), _field(record_id.encode("ascii")),
            _field(encrypted_relpath.encode("ascii")), _field(dedup_hmac),
            _field(integers),
        ))
    except (AttributeError, OverflowError, struct.error, UnicodeEncodeError):
        raise VaultError("invalid_record_metadata") from None


def _field(value: bytes) -> bytes:
    return struct.pack(">I", len(value)) + value


def _mac(key: SecretBuffer, payload: bytes) -> bytes:
    return hmac.new(bytes(key), payload, hashlib.sha256).digest()


def _verify_mac(actual: bytes, expected: bytes) -> None:
    if type(actual) is not bytes or not hmac.compare_digest(actual, expected):
        raise VaultError("record_authentication_failed")


def _derive_key(
    master_key: bytes | bytearray, salt: bytes, info: bytes,
) -> SecretBuffer:
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=info,
    ).derive(bytes(master_key))
    return SecretBuffer(derived)
