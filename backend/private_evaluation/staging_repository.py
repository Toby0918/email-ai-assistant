"""Independent authenticated repository for deidentified evaluation staging."""

from __future__ import annotations

import json
import os
import struct
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .errors import PrivateEvaluationError
from .repository_io import read_bounded_checked, replace_bounded_checked
from .repository_path import _validate_external_private_path
from .schema import EvaluationCaseV1


STAGE_MAGIC = b"PKESTG01"
STAGE_PURPOSE = b"private-evaluation-staging/v1"
MAX_STAGE_BYTES = 8 * 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
_VERSION = 1
_HEADER = struct.Struct(">8sB16sQ")
_STAGE_FIELDS = frozenset({"schema_version", "stage_namespace", "cases"})


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationStageV1:
    schema_version: str
    stage_namespace: str
    cases: tuple[EvaluationCaseV1, ...] = field(repr=False)

    @classmethod
    def from_mapping(cls, value: object) -> EvaluationStageV1:
        if type(value) is not dict or set(value) != _STAGE_FIELDS:
            _schema_invalid()
        if value["schema_version"] != "PrivateEvaluationStageV1":
            _schema_invalid()
        namespace = _uuid4(value["stage_namespace"])
        raw_cases = value["cases"]
        if type(raw_cases) is not list or len(raw_cases) != 200:
            _schema_invalid()
        try:
            cases = tuple(EvaluationCaseV1.from_mapping(item) for item in raw_cases)
        except PrivateEvaluationError:
            _schema_invalid()
        if len({case.case_id for case in cases}) != 200:
            _schema_invalid()
        return cls("PrivateEvaluationStageV1", namespace, cases)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "stage_namespace": self.stage_namespace,
            "cases": [case.to_mapping() for case in self.cases],
        }


def read_encrypted_stage(
    path: Path,
    key: bytes | bytearray,
) -> EvaluationStageV1:
    key_copy = _copy_key(key)
    try:
        frame = _read_frame(Path(path))
        payload, namespace = _decrypt(frame, key_copy)
        try:
            value = json.loads(payload.decode("utf-8"))
            stage = EvaluationStageV1.from_mapping(value)
        except PrivateEvaluationError:
            raise
        except (UnicodeError, json.JSONDecodeError):
            _schema_invalid()
        if stage.stage_namespace != namespace:
            _decrypt_invalid()
        return stage
    finally:
        _wipe(key_copy)


def write_encrypted_stage(
    path: Path,
    cases: tuple[EvaluationCaseV1, ...],
    key: bytes | bytearray,
) -> None:
    if not isinstance(cases, tuple):
        _schema_invalid()
    stage = EvaluationStageV1.from_mapping({
        "schema_version": "PrivateEvaluationStageV1",
        "stage_namespace": str(uuid.uuid4()),
        "cases": [case.to_mapping() for case in cases if isinstance(case, EvaluationCaseV1)],
    })
    if len(stage.cases) != len(cases):
        _schema_invalid()
    key_copy = _copy_key(key)
    try:
        payload = json.dumps(
            stage.to_mapping(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        frame = _encrypt(payload, stage.stage_namespace, key_copy)
        if len(frame) > MAX_STAGE_BYTES:
            _schema_invalid()
        _replace_frame(Path(path), frame)
    finally:
        _wipe(key_copy)


def _encrypt(payload: bytes, namespace: str, key: bytearray) -> bytes:
    namespace_bytes = uuid.UUID(namespace).bytes
    nonce = _nonce()
    cipher_size = len(payload) + TAG_SIZE
    header = _HEADER.pack(STAGE_MAGIC, _VERSION, namespace_bytes, cipher_size)
    derived = _derive(key, namespace_bytes)
    try:
        try:
            ciphertext = AESGCM(bytes(derived)).encrypt(
                nonce, payload, header + STAGE_PURPOSE
            )
        except Exception:
            _decrypt_invalid()
    finally:
        _wipe(derived)
    return header + nonce + ciphertext


def _decrypt(frame: bytes, key: bytearray) -> tuple[bytes, str]:
    minimum = _HEADER.size + NONCE_SIZE + TAG_SIZE
    if type(frame) is not bytes or not minimum <= len(frame) <= MAX_STAGE_BYTES:
        _decrypt_invalid()
    try:
        magic, version, namespace_bytes, cipher_size = _HEADER.unpack(
            frame[:_HEADER.size]
        )
    except struct.error:
        _decrypt_invalid()
    if (
        magic != STAGE_MAGIC or version != _VERSION or cipher_size < TAG_SIZE
        or len(frame) != _HEADER.size + NONCE_SIZE + cipher_size
    ):
        _decrypt_invalid()
    try:
        namespace = str(uuid.UUID(bytes=namespace_bytes))
    except ValueError:
        _decrypt_invalid()
    header = frame[:_HEADER.size]
    nonce = frame[_HEADER.size:_HEADER.size + NONCE_SIZE]
    ciphertext = frame[_HEADER.size + NONCE_SIZE:]
    derived = _derive(key, namespace_bytes)
    try:
        try:
            payload = AESGCM(bytes(derived)).decrypt(
                nonce, ciphertext, header + STAGE_PURPOSE
            )
        except (InvalidTag, ValueError):
            _decrypt_invalid()
        except Exception:
            _decrypt_invalid()
    finally:
        _wipe(derived)
    return payload, namespace


def _read_frame(path: Path) -> bytes:
    try:
        return read_bounded_checked(
            path, MAX_STAGE_BYTES, _validate_external_stage_path, _test_race_hook
        )
    except PrivateEvaluationError as exc:
        if exc.code in {"dataset_decrypt_invalid", "evaluation_stage_decrypt_invalid"}:
            _decrypt_invalid()
        _unavailable()


def _replace_frame(path: Path, frame: bytes) -> None:
    try:
        replace_bounded_checked(
            path, frame, MAX_STAGE_BYTES, _validate_external_stage_path,
            _test_race_hook,
        )
    except PrivateEvaluationError:
        _unavailable()


def _validate_external_stage_path(value: Path) -> Path:
    try:
        return _validate_external_private_path(Path(value), ".pkevalstage")
    except PrivateEvaluationError:
        _unavailable()


def _derive(key: bytearray, namespace: bytes) -> bytearray:
    return bytearray(HKDF(
        algorithm=hashes.SHA256(), length=32, salt=namespace,
        info=STAGE_PURPOSE,
    ).derive(bytes(key)))


def _nonce() -> bytes:
    try:
        value = os.urandom(NONCE_SIZE)
    except Exception:
        _decrypt_invalid()
    if type(value) is not bytes or len(value) != NONCE_SIZE:
        _decrypt_invalid()
    return value


def _copy_key(value: bytes | bytearray) -> bytearray:
    if not isinstance(value, (bytes, bytearray)) or len(value) != 32:
        raise PrivateEvaluationError("evaluation_key_unavailable")
    return bytearray(value)


def _uuid4(value: object) -> str:
    if type(value) is not str:
        _schema_invalid()
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        _schema_invalid()
    if str(parsed) != value or parsed.version != 4:
        _schema_invalid()
    return value


def _wipe(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _test_race_hook(_stage: str, _path: Path) -> None:
    return None


def _schema_invalid() -> None:
    raise PrivateEvaluationError("evaluation_stage_schema_invalid")


def _decrypt_invalid() -> None:
    raise PrivateEvaluationError("evaluation_stage_decrypt_invalid")


def _unavailable() -> None:
    raise PrivateEvaluationError("evaluation_stage_unavailable")
