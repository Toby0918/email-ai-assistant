"""Ed25519-signed AES-256-GCM runtime snapshot frame codec."""

from __future__ import annotations

import os
import struct
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .crypto_frames import validate_uuid4
from .errors import PrivateKnowledgeError


SNAPSHOT_MAGIC = b"PKSNAP01"
_VERSION = 1
_KEY_VERSION = 1
_NONCE_SIZE = 12
_SIGNATURE_SIZE = 64
_TAG_SIZE = 16
_PURPOSE = b"private-knowledge/runtime-snapshot/v1"
_HEADER = struct.Struct(">8sBH16s16sqqHQ")


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    snapshot_id: str
    authority_id: str
    created_epoch: int
    expires_epoch: int
    card_count: int


def encode_snapshot_frame(
    payload: bytes,
    metadata: SnapshotMetadata,
    *,
    encryption_key: bytes | bytearray,
    signing_private_key: Ed25519PrivateKey,
    rng: Callable[[int], bytes] = os.urandom,
) -> bytes:
    snapshot = uuid.UUID(validate_uuid4(metadata.snapshot_id, "snapshot_id_invalid")).bytes
    authority = uuid.UUID(validate_uuid4(metadata.authority_id, "authority_invalid")).bytes
    _validate_metadata(metadata)
    key = _derive_key(encryption_key, snapshot + authority)
    try:
        nonce = rng(_NONCE_SIZE)
    except Exception:
        raise PrivateKnowledgeError("snapshot_nonce_invalid") from None
    if type(nonce) is not bytes or len(nonce) != _NONCE_SIZE:
        raise PrivateKnowledgeError("snapshot_nonce_invalid")
    header = _HEADER.pack(
        SNAPSHOT_MAGIC, _VERSION, _KEY_VERSION, snapshot, authority,
        metadata.created_epoch, metadata.expires_epoch, metadata.card_count,
        len(payload) + _TAG_SIZE,
    )
    try:
        ciphertext = AESGCM(key).encrypt(nonce, payload, header + _PURPOSE)
        signature = signing_private_key.sign(header + nonce + ciphertext)
    except Exception:
        raise PrivateKnowledgeError("snapshot_crypto_failed") from None
    if len(signature) != _SIGNATURE_SIZE:
        raise PrivateKnowledgeError("snapshot_crypto_failed")
    return header + nonce + ciphertext + signature


def decode_snapshot_frame(
    frame: bytes,
    *,
    encryption_key: bytes | bytearray,
    verification_public_key: Ed25519PublicKey,
) -> tuple[SnapshotMetadata, bytes]:
    minimum = _HEADER.size + _NONCE_SIZE + _TAG_SIZE + _SIGNATURE_SIZE
    if type(frame) is not bytes or not minimum <= len(frame) <= 4 * 1024 * 1024:
        raise PrivateKnowledgeError("snapshot_signature_invalid")
    try:
        fields = _HEADER.unpack(frame[:_HEADER.size])
    except struct.error:
        raise PrivateKnowledgeError("snapshot_signature_invalid") from None
    magic, version, key_version, snapshot, authority, created, expires, count, size = fields
    expected = _HEADER.size + _NONCE_SIZE + size + _SIGNATURE_SIZE
    if (magic != SNAPSHOT_MAGIC or version != _VERSION or key_version != _KEY_VERSION
            or size < _TAG_SIZE or len(frame) != expected or count > 1_000):
        raise PrivateKnowledgeError("snapshot_signature_invalid")
    signed = frame[:-_SIGNATURE_SIZE]
    signature = frame[-_SIGNATURE_SIZE:]
    try:
        verification_public_key.verify(signature, signed)
    except (InvalidSignature, ValueError, TypeError, AttributeError):
        raise PrivateKnowledgeError("snapshot_signature_invalid") from None
    metadata = SnapshotMetadata(
        str(uuid.UUID(bytes=snapshot)), str(uuid.UUID(bytes=authority)),
        created, expires, count,
    )
    _validate_metadata(metadata)
    nonce = frame[_HEADER.size:_HEADER.size + _NONCE_SIZE]
    ciphertext = frame[_HEADER.size + _NONCE_SIZE:-_SIGNATURE_SIZE]
    key = _derive_key(encryption_key, snapshot + authority)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, frame[:_HEADER.size] + _PURPOSE)
    except (InvalidTag, ValueError):
        raise PrivateKnowledgeError("snapshot_decrypt_invalid") from None
    except Exception:
        raise PrivateKnowledgeError("snapshot_decrypt_invalid") from None
    return metadata, plaintext


def _validate_metadata(value: SnapshotMetadata) -> None:
    if (type(value.created_epoch) is not int or type(value.expires_epoch) is not int
            or type(value.card_count) is not int or value.card_count < 0
            or value.card_count > 1_000 or value.expires_epoch <= value.created_epoch):
        raise PrivateKnowledgeError("snapshot_schema_invalid")


def _derive_key(master_key: bytes | bytearray, salt: bytes) -> bytes:
    if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != 32:
        raise PrivateKnowledgeError("snapshot_key_invalid")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        info=b"private-knowledge/snapshot-encryption/v1",
    ).derive(bytes(master_key))
