"""Versioned AES-256-GCM record frames with purpose-separated subkeys."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import struct
import uuid
from typing import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import VaultError
from .models import SecretBuffer, VaultRecord, VaultWriteIntent
from .vault_metadata_auth import VaultMetadataAuthenticator


FRAME_MAGIC = b"MBVLT001"
FRAME_VERSION = 1
ALGORITHM_AES_256_GCM = 1
NONCE_SIZE = 12
TAG_SIZE = 16
_HEADER = struct.Struct(">8sBBHBBQ")
_RECORD_ID = re.compile(r"^[0-9a-f]{32}$")
_ENCRYPTION_INFO = b"mailbox-vault/record-encryption/v1"
_DEDUP_INFO = b"mailbox-vault/dedup-hmac/v1"
_RECORD_PURPOSE = b"mailbox-vault-record/v1"


class VaultCrypto:
    """Encrypt individual records and compute non-reversible deduplication HMACs."""

    def __init__(
        self,
        master_key: bytes | bytearray,
        *,
        vault_id: str,
        key_version: int = 1,
        rng: Callable[[int], bytes] = os.urandom,
        max_plaintext_size: int = 16 * 1024 * 1024,
    ) -> None:
        if len(master_key) != 32:
            raise VaultError("invalid_master_key")
        try:
            parsed_vault_id = uuid.UUID(vault_id)
        except (ValueError, TypeError, AttributeError):
            raise VaultError("invalid_vault_id") from None
        if str(parsed_vault_id) != vault_id or not 1 <= key_version <= 65_535:
            raise VaultError("invalid_vault_id")
        if type(max_plaintext_size) is not int or max_plaintext_size <= 0:
            raise VaultError("record_too_large")
        self._vault_id = vault_id
        self._vault_id_bytes = parsed_vault_id.bytes
        self._key_version = key_version
        self._rng = rng
        self._max_plaintext_size = max_plaintext_size
        self._record_encryption_key = _derive_key(
            master_key, self._vault_id_bytes, _ENCRYPTION_INFO
        )
        self._dedup_hmac_key = _derive_key(
            master_key, self._vault_id_bytes, _DEDUP_INFO
        )
        self._metadata_auth = VaultMetadataAuthenticator(
            master_key, self._vault_id_bytes,
        )
        self._seen_nonces: set[bytes] = set()
        self._closed = False

    @property
    def key_version(self) -> int:
        return self._key_version

    @property
    def max_frame_size(self) -> int:
        return (
            _HEADER.size + 32 + NONCE_SIZE
            + self._max_plaintext_size + TAG_SIZE
        )

    def frame_size_for_plaintext(self, plaintext_size: int) -> int:
        self._ensure_open()
        if (
            type(plaintext_size) is not int
            or plaintext_size < 0
            or plaintext_size > self._max_plaintext_size
        ):
            raise VaultError("record_too_large")
        return _HEADER.size + 32 + NONCE_SIZE + plaintext_size + TAG_SIZE

    def _ensure_open(self) -> None:
        if self._closed:
            raise VaultError("crypto_closed")

    def _new_nonce(self) -> bytes:
        try:
            nonce = self._rng(NONCE_SIZE)
        except Exception:
            raise VaultError("invalid_nonce") from None
        if type(nonce) is not bytes or len(nonce) != NONCE_SIZE:
            raise VaultError("invalid_nonce")
        if nonce in self._seen_nonces:
            raise VaultError("nonce_reuse")
        self._seen_nonces.add(nonce)
        return nonce

    def encrypt(self, record_id: str, plaintext: bytes | bytearray) -> bytes:
        self._ensure_open()
        record_bytes = _validate_record_id(record_id)
        if not isinstance(plaintext, (bytes, bytearray)):
            raise VaultError("record_too_large")
        if len(plaintext) > self._max_plaintext_size:
            raise VaultError("record_too_large")
        nonce = self._new_nonce()
        ciphertext_size = len(plaintext) + TAG_SIZE
        header = self._header(len(record_bytes), len(nonce), ciphertext_size)
        aad = self._aad(header, record_bytes, nonce)
        try:
            ciphertext = AESGCM(bytes(self._record_encryption_key)).encrypt(
                nonce, bytes(plaintext), aad
            )
        except Exception:
            raise VaultError("record_authentication_failed") from None
        return header + record_bytes + nonce + ciphertext

    def decrypt(self, record_id: str, frame: bytes | bytearray) -> SecretBuffer:
        self._ensure_open()
        expected_record = _validate_record_id(record_id)
        header, stored_record, nonce, ciphertext = self._parse_frame(frame)
        if stored_record != expected_record:
            raise VaultError("record_binding_mismatch")
        aad = self._aad(header, stored_record, nonce)
        try:
            plaintext = AESGCM(bytes(self._record_encryption_key)).decrypt(
                nonce, ciphertext, aad
            )
        except InvalidTag:
            raise VaultError("record_authentication_failed") from None
        except Exception:
            raise VaultError("record_authentication_failed") from None
        if len(plaintext) > self._max_plaintext_size:
            raise VaultError("record_too_large")
        return SecretBuffer(plaintext)

    def _parse_frame(
        self, frame: bytes | bytearray
    ) -> tuple[bytes, bytes, bytes, bytes]:
        if not isinstance(frame, (bytes, bytearray)) or len(frame) < _HEADER.size:
            raise VaultError("invalid_frame_size")
        raw = bytes(frame)
        try:
            values = _HEADER.unpack(raw[: _HEADER.size])
        except struct.error:
            raise VaultError("invalid_frame") from None
        magic, version, algorithm, key_version, record_size, nonce_size, cipher_size = values
        _validate_header(magic, version, algorithm, key_version, self._key_version)
        if record_size != 32 or nonce_size != NONCE_SIZE:
            raise VaultError("invalid_frame")
        if cipher_size < TAG_SIZE or cipher_size > self._max_plaintext_size + TAG_SIZE:
            raise VaultError("invalid_frame_size")
        expected_size = _HEADER.size + record_size + nonce_size + cipher_size
        if len(raw) != expected_size:
            raise VaultError("invalid_frame_size")
        record_end = _HEADER.size + record_size
        nonce_end = record_end + nonce_size
        stored_record = raw[_HEADER.size:record_end]
        try:
            _validate_record_id(stored_record.decode("ascii"))
        except (UnicodeDecodeError, VaultError):
            raise VaultError("invalid_frame") from None
        return raw[: _HEADER.size], stored_record, raw[record_end:nonce_end], raw[nonce_end:]

    def _header(self, record_size: int, nonce_size: int, cipher_size: int) -> bytes:
        return _HEADER.pack(
            FRAME_MAGIC,
            FRAME_VERSION,
            ALGORITHM_AES_256_GCM,
            self._key_version,
            record_size,
            nonce_size,
            cipher_size,
        )

    def _aad(self, header: bytes, record_id: bytes, nonce: bytes) -> bytes:
        return header + record_id + nonce + self._vault_id_bytes + _RECORD_PURPOSE

    def dedup_hmac(self, plaintext: bytes | bytearray) -> bytes:
        self._ensure_open()
        if not isinstance(plaintext, (bytes, bytearray)):
            raise VaultError("invalid_record_metadata")
        return hmac.new(
            bytes(self._dedup_hmac_key), bytes(plaintext), hashlib.sha256
        ).digest()

    def sign_record_metadata(self, record: VaultRecord) -> VaultRecord:
        self._ensure_open()
        return self._metadata_auth.sign_record(record)

    def sign_intent_metadata(self, intent: VaultWriteIntent) -> VaultWriteIntent:
        self._ensure_open()
        return self._metadata_auth.sign_intent(intent)

    def verify_record_metadata(self, record: VaultRecord) -> None:
        self._ensure_open()
        self._metadata_auth.verify_record(record)

    def verify_intent_metadata(self, intent: VaultWriteIntent) -> None:
        self._ensure_open()
        self._metadata_auth.verify_intent(intent)

    def close(self) -> None:
        if self._closed:
            return
        self._record_encryption_key.wipe()
        self._dedup_hmac_key.wipe()
        self._metadata_auth.close()
        self._seen_nonces.clear()
        self._closed = True

    def __repr__(self) -> str:
        return "VaultCrypto(<redacted>)"


def _derive_key(master_key: bytes | bytearray, salt: bytes, info: bytes) -> SecretBuffer:
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=info
    ).derive(bytes(master_key))
    return SecretBuffer(derived)


def _validate_record_id(record_id: str) -> bytes:
    if not isinstance(record_id, str) or _RECORD_ID.fullmatch(record_id) is None:
        raise VaultError("invalid_record_id")
    return record_id.encode("ascii")


def _validate_header(
    magic: bytes,
    version: int,
    algorithm: int,
    key_version: int,
    expected_key_version: int,
) -> None:
    if magic != FRAME_MAGIC:
        raise VaultError("invalid_frame")
    if version != FRAME_VERSION:
        raise VaultError("unsupported_frame_version")
    if algorithm != ALGORITHM_AES_256_GCM:
        raise VaultError("unsupported_algorithm")
    if key_version != expected_key_version:
        raise VaultError("key_version_mismatch")
