"""Independent authenticated storage for private evaluation datasets."""

from __future__ import annotations

import json
import os
import struct
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .schema import EvaluationDatasetV1, PrivateEvaluationError
from .repository_io import read_bounded_checked, replace_bounded_checked
from .repository_path import (
    _inside_raw_vault,
    _overlaps_other_store,
    _reject_reparse,
    _validate_external_dataset_path,
)


DATASET_MAGIC = b"PKEVAL01"
DATASET_PURPOSE = b"private-evaluation-dataset/v1"
MAX_DATASET_BYTES = 8 * 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
_VERSION = 1
_HEADER = struct.Struct(">8sB16sQ")
def read_encrypted_dataset(path: Path, key: bytes | bytearray) -> EvaluationDatasetV1:
    original = Path(path)
    key_copy = _copy_key(key)
    try:
        frame = read_bounded_checked(
            original, MAX_DATASET_BYTES, _validate_external_dataset_path,
            _test_race_hook,
        )
        payload, namespace = _decrypt(frame, key_copy)
        try:
            decoded = json.loads(payload.decode("utf-8"))
            dataset = EvaluationDatasetV1.from_mapping(decoded)
        except PrivateEvaluationError:
            raise
        except (UnicodeError, json.JSONDecodeError):
            raise PrivateEvaluationError("dataset_schema_invalid") from None
        if dataset.dataset_namespace != namespace:
            raise PrivateEvaluationError("dataset_decrypt_invalid")
        return dataset
    finally:
        _wipe(key_copy)


def write_encrypted_dataset(
    path: Path,
    dataset: EvaluationDatasetV1,
    key: bytes | bytearray,
) -> None:
    _write_encrypted_dataset(path, dataset, key, require_absent=False)


def write_new_encrypted_dataset(
    path: Path,
    dataset: EvaluationDatasetV1,
    key: bytes | bytearray,
) -> None:
    _write_encrypted_dataset(path, dataset, key, require_absent=True)


def _write_encrypted_dataset(
    path: Path,
    dataset: EvaluationDatasetV1,
    key: bytes | bytearray,
    *,
    require_absent: bool,
) -> None:
    original = Path(path)
    if not isinstance(dataset, EvaluationDatasetV1):
        raise PrivateEvaluationError("dataset_schema_invalid")
    validated = EvaluationDatasetV1.from_mapping(dataset.to_mapping())
    key_copy = _copy_key(key)
    try:
        payload = _dataset_payload(validated)
        frame = _encrypt(payload, validated.dataset_namespace, key_copy)
        if len(frame) > MAX_DATASET_BYTES:
            raise PrivateEvaluationError("dataset_schema_invalid")
        replace_bounded_checked(
            original, frame, MAX_DATASET_BYTES, _validate_external_dataset_path,
            _test_race_hook, require_absent=require_absent,
        )
    finally:
        _wipe(key_copy)


def _dataset_payload(dataset: EvaluationDatasetV1) -> bytes:
    return json.dumps(
        dataset.to_mapping(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _encrypt(payload: bytes, namespace: str, key: bytearray) -> bytes:
    namespace_bytes = uuid.UUID(namespace).bytes
    nonce = _nonce()
    cipher_size = len(payload) + TAG_SIZE
    header = _HEADER.pack(DATASET_MAGIC, _VERSION, namespace_bytes, cipher_size)
    derived = _derive(key, namespace_bytes)
    try:
        try:
            ciphertext = AESGCM(bytes(derived)).encrypt(
                nonce, payload, header + DATASET_PURPOSE
            )
        except Exception:
            raise PrivateEvaluationError("dataset_decrypt_invalid") from None
    finally:
        _wipe(derived)
    return header + nonce + ciphertext


def _decrypt(frame: bytes, key: bytearray) -> tuple[bytes, str]:
    minimum = _HEADER.size + NONCE_SIZE + TAG_SIZE
    if type(frame) is not bytes or not minimum <= len(frame) <= MAX_DATASET_BYTES:
        raise PrivateEvaluationError("dataset_decrypt_invalid")
    try:
        magic, version, namespace_bytes, cipher_size = _HEADER.unpack(frame[:_HEADER.size])
    except struct.error:
        raise PrivateEvaluationError("dataset_decrypt_invalid") from None
    if (
        magic != DATASET_MAGIC or version != _VERSION or cipher_size < TAG_SIZE
        or len(frame) != _HEADER.size + NONCE_SIZE + cipher_size
    ):
        raise PrivateEvaluationError("dataset_decrypt_invalid")
    try:
        namespace = str(uuid.UUID(bytes=namespace_bytes))
    except ValueError:
        raise PrivateEvaluationError("dataset_decrypt_invalid") from None
    header = frame[:_HEADER.size]
    nonce = frame[_HEADER.size:_HEADER.size + NONCE_SIZE]
    ciphertext = frame[_HEADER.size + NONCE_SIZE:]
    derived = _derive(key, namespace_bytes)
    try:
        try:
            payload = AESGCM(bytes(derived)).decrypt(
                nonce, ciphertext, header + DATASET_PURPOSE
            )
        except (InvalidTag, ValueError):
            raise PrivateEvaluationError("dataset_decrypt_invalid") from None
        except Exception:
            raise PrivateEvaluationError("dataset_decrypt_invalid") from None
    finally:
        _wipe(derived)
    return payload, namespace


def _derive(key: bytearray, namespace: bytes) -> bytearray:
    return bytearray(HKDF(
        algorithm=hashes.SHA256(), length=32, salt=namespace,
        info=DATASET_PURPOSE,
    ).derive(bytes(key)))


def _nonce() -> bytes:
    try:
        value = os.urandom(NONCE_SIZE)
    except Exception:
        raise PrivateEvaluationError("dataset_decrypt_invalid") from None
    if type(value) is not bytes or len(value) != NONCE_SIZE:
        raise PrivateEvaluationError("dataset_decrypt_invalid")
    return value


def _copy_key(key: bytes | bytearray) -> bytearray:
    if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
        raise PrivateEvaluationError("evaluation_key_unavailable")
    return bytearray(key)


def _wipe(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _test_race_hook(_stage: str, _path: Path) -> None:
    """No-op seam: tests may only mutate paths; all checks still run afterward."""
    return None
