"""Independent authenticated storage for private evaluation datasets."""

from __future__ import annotations

import json
import os
import stat
import struct
import tempfile
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .schema import EvaluationDatasetV1, PrivateEvaluationError


DATASET_MAGIC = b"PKEVAL01"
DATASET_PURPOSE = b"private-evaluation-dataset/v1"
MAX_DATASET_BYTES = 8 * 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
_VERSION = 1
_HEADER = struct.Struct(">8sB16sQ")
_OTHER_STORE_SUFFIXES = frozenset({
    ".pkauth", ".pkcand", ".pkimpt", ".pksnap", ".pkkey", ".pkstage",
})
_OTHER_STORE_MARKERS = frozenset({
    "authority-keys.pkenv", "candidate-key.pkenv", "snapshot-key.pkenv",
    "candidate-store.pkcand", "candidate-import.pkimpt",
})


def read_encrypted_dataset(path: Path, key: bytes | bytearray) -> EvaluationDatasetV1:
    target = _validate_external_dataset_path(path)
    key_copy = _copy_key(key)
    try:
        try:
            frame = target.read_bytes()
        except FileNotFoundError:
            raise PrivateEvaluationError("dataset_unavailable") from None
        except OSError:
            raise PrivateEvaluationError("dataset_unavailable") from None
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
    target = _validate_external_dataset_path(path)
    if not isinstance(dataset, EvaluationDatasetV1):
        raise PrivateEvaluationError("dataset_schema_invalid")
    validated = EvaluationDatasetV1.from_mapping(dataset.to_mapping())
    key_copy = _copy_key(key)
    try:
        payload = _dataset_payload(validated)
        frame = _encrypt(payload, validated.dataset_namespace, key_copy)
        if len(frame) > MAX_DATASET_BYTES:
            raise PrivateEvaluationError("dataset_schema_invalid")
        _atomic_write(target, frame)
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


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except OSError:
        raise PrivateEvaluationError("dataset_unavailable") from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _validate_external_dataset_path(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.suffix != ".pkeval":
        raise PrivateEvaluationError("dataset_unavailable")
    try:
        _reject_reparse(path)
        resolved = path.resolve(strict=False)
        _reject_reparse(resolved)
    except (OSError, RuntimeError):
        raise PrivateEvaluationError("dataset_unavailable") from None
    project = Path(__file__).resolve().parents[2]
    temporary = Path(tempfile.gettempdir()).resolve()
    forbidden = (project, temporary)
    if (
        any(resolved == root or root in resolved.parents for root in forbidden)
        or any(
            part.casefold().startswith("onedrive")
            for part in (*path.parts, *resolved.parts)
        )
        or (resolved.exists() and not resolved.is_file())
        or _inside_raw_vault(resolved)
        or _overlaps_other_store(resolved)
    ):
        raise PrivateEvaluationError("dataset_unavailable")
    return resolved


def _reject_reparse(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & reparse:
            raise PrivateEvaluationError("dataset_unavailable")


def _inside_raw_vault(path: Path) -> bool:
    try:
        return any(
            (parent / "vault-index.sqlite3").exists()
            or (parent / "keys" / "recovery-state.json").exists()
            for parent in (path.parent, *path.parents)
        )
    except OSError:
        raise PrivateEvaluationError("dataset_unavailable") from None


def _overlaps_other_store(path: Path) -> bool:
    for parent in (path.parent, *path.parents):
        try:
            entries = tuple(parent.iterdir()) if parent.exists() else ()
        except OSError:
            raise PrivateEvaluationError("dataset_unavailable") from None
        if any(
            entry != path and (
                entry.suffix.casefold() in _OTHER_STORE_SUFFIXES
                or entry.name.casefold() in _OTHER_STORE_MARKERS
            )
            for entry in entries
        ):
            return True
    return False
