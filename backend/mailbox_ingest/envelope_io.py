"""Durable, strict file helpers for key-envelope metadata."""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path

from .errors import VaultError


def encode_bytes(value: bytes | bytearray) -> str:
    return base64.b64encode(bytes(value)).decode("ascii")


def decode_bytes(value: object) -> bytes:
    if not isinstance(value, str):
        raise VaultError("invalid_key_envelope")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise VaultError("invalid_key_envelope") from None


def read_json_exact(path: Path, fields: set[str]) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise VaultError("key_envelope_missing") from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise VaultError("key_envelope_read_failed") from None
    if not isinstance(payload, dict) or set(payload) != fields:
        raise VaultError("invalid_key_envelope")
    return payload


def write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    stage = path.with_name(f".{path.name}.{uuid.uuid4().hex}.stage")
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(stage, encoded)
        os.replace(stage, path)
        _fsync_directory(path.parent)
    except VaultError:
        raise
    except OSError:
        raise VaultError("key_envelope_write_failed") from None
    finally:
        try:
            stage.unlink(missing_ok=True)
        except OSError:
            pass


def write_bytes_exclusive(path: Path, data: bytes | bytearray) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_exclusive(path, bytes(data))
        _fsync_directory(path.parent)
    except FileExistsError:
        raise VaultError("recovery_key_exists") from None
    except VaultError:
        raise
    except OSError:
        raise VaultError("key_envelope_write_failed") from None


def _write_exclusive(path: Path, data: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            written = os.write(descriptor, view[offset:])
            if written <= 0:
                raise OSError
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
