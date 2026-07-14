"""Strict offline recovery-key and AES-GCM master-envelope primitives."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .envelope_io import (
    decode_bytes,
    encode_bytes,
    read_json_exact,
    write_bytes_exclusive,
    write_json_atomic,
)
from .errors import VaultError
from .models import SecretBuffer


_RECOVERY_KEY_MAGIC = b"MBRKEY01"
_FORMAT_VERSION = 1
_KEY_VERSION = 1
_RECOVERY_PURPOSE = "mailbox-vault-master-recovery"
_RECOVERY_FIELDS = {
    "format_version", "algorithm", "vault_id", "key_version",
    "recovery_key_id", "generation", "purpose", "nonce", "ciphertext",
}


def write_recovery_key(path: Path, key: bytes | bytearray) -> str:
    key_id = hashlib.sha256(b"mailbox-vault-recovery-id" + bytes(key)).digest()[:16]
    write_bytes_exclusive(path, _RECOVERY_KEY_MAGIC + key_id + bytes(key))
    return key_id.hex()


def read_recovery_key(path: Path) -> tuple[str, SecretBuffer]:
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        raise VaultError("recovery_key_missing") from None
    except OSError:
        raise VaultError("recovery_key_invalid") from None
    if len(payload) != 56 or not payload.startswith(_RECOVERY_KEY_MAGIC):
        raise VaultError("recovery_key_invalid")
    key_id = payload[8:24]
    key = SecretBuffer(payload[24:])
    expected = hashlib.sha256(b"mailbox-vault-recovery-id" + bytes(key)).digest()[:16]
    if not hmac.compare_digest(key_id, expected):
        key.wipe()
        raise VaultError("recovery_key_invalid")
    return key_id.hex(), key


def write_recovery_envelope(
    keys: Path,
    vault_id: str,
    generation: int,
    recovery_key_id: str,
    recovery_kek: bytes | bytearray,
    master_key: bytes | bytearray,
    nonce: bytes,
) -> None:
    metadata = _recovery_metadata(vault_id, generation, recovery_key_id, nonce)
    aad = _canonical_metadata(metadata)
    ciphertext = AESGCM(bytes(recovery_kek)).encrypt(nonce, bytes(master_key), aad)
    write_json_atomic(
        keys / f"recovery.{generation}.json",
        {**metadata, "ciphertext": encode_bytes(ciphertext)},
    )


def decrypt_recovery_envelope(
    keys: Path,
    vault_id: str,
    generation: int,
    recovery_key_id: str,
    recovery_kek: bytes | bytearray,
) -> SecretBuffer:
    envelope = read_json_exact(
        keys / f"recovery.{generation}.json", _RECOVERY_FIELDS
    )
    nonce = decode_bytes(envelope["nonce"])
    metadata = {key: value for key, value in envelope.items() if key != "ciphertext"}
    if metadata != _recovery_metadata(vault_id, generation, recovery_key_id, nonce):
        raise VaultError("invalid_key_envelope")
    try:
        plaintext = AESGCM(bytes(recovery_kek)).decrypt(
            nonce, decode_bytes(envelope["ciphertext"]), _canonical_metadata(metadata)
        )
    except InvalidTag:
        raise VaultError("recovery_authentication_failed") from None
    except Exception:
        raise VaultError("recovery_authentication_failed") from None
    if len(plaintext) != 32:
        raise VaultError("invalid_master_key")
    return SecretBuffer(plaintext)


def _recovery_metadata(
    vault_id: str, generation: int, recovery_key_id: str, nonce: bytes
) -> dict[str, object]:
    return {
        "format_version": _FORMAT_VERSION,
        "algorithm": "AES-256-GCM",
        "vault_id": vault_id,
        "key_version": _KEY_VERSION,
        "recovery_key_id": recovery_key_id,
        "generation": generation,
        "purpose": _RECOVERY_PURPOSE,
        "nonce": encode_bytes(nonce),
    }


def _canonical_metadata(metadata: dict[str, object]) -> bytes:
    return json.dumps(
        metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
