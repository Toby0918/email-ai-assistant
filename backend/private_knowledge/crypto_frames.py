"""Purpose-separated authenticated frames for private-knowledge stores."""

from __future__ import annotations

import os
import struct
import uuid
from collections.abc import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import PrivateKnowledgeError


NONCE_SIZE = 12
TAG_SIZE = 16
_VERSION = 1
_HEADER = struct.Struct(">8sB16sQ")


def encrypt_frame(
    payload: bytes,
    *,
    magic: bytes,
    purpose: bytes,
    namespace_id: str,
    master_key: bytes | bytearray,
    rng: Callable[[int], bytes] = os.urandom,
) -> bytes:
    namespace = _namespace(namespace_id)
    key = _derive_key(master_key, namespace, purpose)
    try:
        nonce = rng(NONCE_SIZE)
    except Exception:
        raise PrivateKnowledgeError("crypto_nonce_invalid") from None
    if type(nonce) is not bytes or len(nonce) != NONCE_SIZE:
        raise PrivateKnowledgeError("crypto_nonce_invalid")
    header = _HEADER.pack(magic, _VERSION, namespace, len(payload) + TAG_SIZE)
    try:
        ciphertext = AESGCM(key).encrypt(nonce, payload, header + purpose)
    except Exception:
        raise PrivateKnowledgeError("crypto_encrypt_failed") from None
    return header + nonce + ciphertext


def decrypt_frame(
    frame: bytes,
    *,
    magic: bytes,
    purpose: bytes,
    namespace_id: str,
    master_key: bytes | bytearray,
    error_code: str,
    maximum: int = 8 * 1024 * 1024,
) -> bytes:
    minimum = _HEADER.size + NONCE_SIZE + TAG_SIZE
    if type(frame) is not bytes or not minimum <= len(frame) <= maximum:
        raise PrivateKnowledgeError(error_code)
    try:
        stored_magic, version, namespace, cipher_size = _HEADER.unpack(
            frame[:_HEADER.size]
        )
    except struct.error:
        raise PrivateKnowledgeError(error_code) from None
    expected_namespace = _namespace(namespace_id)
    if (stored_magic != magic or version != _VERSION or namespace != expected_namespace
            or cipher_size < TAG_SIZE
            or len(frame) != _HEADER.size + NONCE_SIZE + cipher_size):
        raise PrivateKnowledgeError(error_code)
    header = frame[:_HEADER.size]
    nonce = frame[_HEADER.size:_HEADER.size + NONCE_SIZE]
    ciphertext = frame[_HEADER.size + NONCE_SIZE:]
    key = _derive_key(master_key, expected_namespace, purpose)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, header + purpose)
    except (InvalidTag, ValueError):
        raise PrivateKnowledgeError(error_code) from None
    except Exception:
        raise PrivateKnowledgeError(error_code) from None


def validate_uuid4(value: object, code: str = "identifier_invalid") -> str:
    if not isinstance(value, str):
        raise PrivateKnowledgeError(code)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise PrivateKnowledgeError(code) from None
    if str(parsed) != value or parsed.version != 4:
        raise PrivateKnowledgeError(code)
    return value


def _namespace(value: str) -> bytes:
    return uuid.UUID(validate_uuid4(value)).bytes


def _derive_key(
    master_key: bytes | bytearray,
    salt: bytes,
    purpose: bytes,
) -> bytes:
    if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != 32:
        raise PrivateKnowledgeError("private_key_invalid")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        info=b"private-knowledge/" + purpose + b"/key/v1",
    ).derive(bytes(master_key))
