"""Encrypted, purpose-bound control state outside the metadata-only index."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .models import SecretBuffer


_MAGIC = b"MBCTRL01"
_NONCE_SIZE = 12
_NAME = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class ControlStoreError(ValueError):
    def __init__(self, code: str = "control_store_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"ControlStoreError(code={self.code!r})"


class EncryptedControlStore:
    def __init__(
        self,
        vault_root: Path,
        *,
        vault_id: str,
        master_key: bytes | bytearray,
        rng: Callable[[int], bytes] = os.urandom,
        max_plaintext_size: int = 1024 * 1024,
    ) -> None:
        try:
            vault_bytes = uuid.UUID(vault_id).bytes
        except (ValueError, TypeError, AttributeError):
            raise ControlStoreError() from None
        if len(master_key) != 32 or type(max_plaintext_size) is not int or max_plaintext_size < 1:
            raise ControlStoreError()
        self._root = Path(vault_root).resolve() / "control"
        self._vault_id = vault_bytes
        self._key = SecretBuffer(
            HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=vault_bytes,
                info=b"mailbox-vault/control-store/v1",
            ).derive(bytes(master_key))
        )
        self._rng = rng
        self._maximum = max_plaintext_size
        self._closed = False
        self._seen_nonces: set[bytes] = set()

    def write(self, name: str, payload: dict[str, object]) -> None:
        token, aad = self._name(name)
        try:
            plaintext = json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode("ascii")
        except (TypeError, ValueError):
            raise ControlStoreError() from None
        if len(plaintext) > self._maximum:
            raise ControlStoreError("control_store_too_large")
        nonce = self._nonce()
        ciphertext = AESGCM(bytes(self._key)).encrypt(nonce, plaintext, aad)
        self._atomic_write(token, _MAGIC + nonce + ciphertext)

    def read(self, name: str) -> dict[str, object]:
        token, aad = self._name(name)
        path = self._root / token
        try:
            metadata = path.lstat()
            if path.is_symlink() or not path.is_file():
                raise ControlStoreError()
            if metadata.st_size < len(_MAGIC) + _NONCE_SIZE + 16:
                raise ControlStoreError()
            if metadata.st_size > self._maximum + len(_MAGIC) + _NONCE_SIZE + 16:
                raise ControlStoreError("control_store_too_large")
            frame = path.read_bytes()
        except FileNotFoundError:
            raise ControlStoreError("control_store_missing") from None
        except ControlStoreError:
            raise
        except OSError:
            raise ControlStoreError() from None
        if len(frame) != metadata.st_size or not frame.startswith(_MAGIC):
            raise ControlStoreError()
        nonce = frame[len(_MAGIC):len(_MAGIC) + _NONCE_SIZE]
        try:
            plaintext = AESGCM(bytes(self._key)).decrypt(
                nonce, frame[len(_MAGIC) + _NONCE_SIZE:], aad
            )
            payload = json.loads(plaintext)
        except (InvalidTag, UnicodeError, json.JSONDecodeError, ValueError):
            raise ControlStoreError() from None
        if not isinstance(payload, dict):
            raise ControlStoreError()
        return payload

    def _name(self, name: str) -> tuple[str, bytes]:
        if self._closed or not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise ControlStoreError()
        digest = hashlib.sha256(bytes(self._key) + name.encode("ascii")).hexdigest()
        aad = _MAGIC + self._vault_id + name.encode("ascii")
        return f"{digest}.mctl", aad

    def _nonce(self) -> bytes:
        try:
            nonce = self._rng(_NONCE_SIZE)
        except Exception:
            raise ControlStoreError() from None
        if type(nonce) is not bytes or len(nonce) != _NONCE_SIZE or nonce in self._seen_nonces:
            raise ControlStoreError("control_nonce_invalid")
        self._seen_nonces.add(nonce)
        return nonce

    def _atomic_write(self, token: str, frame: bytes) -> None:
        stage: Path | None = None
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            target = self._root / token
            stage = self._root / f".{uuid.uuid4().hex}.stage"
            with stage.open("xb") as stream:
                os.chmod(stage, 0o600)
                stream.write(frame)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(stage, target)
        except OSError:
            raise ControlStoreError("control_store_write_failed") from None
        finally:
            if stage is not None:
                try:
                    stage.unlink(missing_ok=True)
                except OSError:
                    pass

    def close(self) -> None:
        self._key.wipe()
        self._closed = True
        self._seen_nonces.clear()

    def __enter__(self) -> "EncryptedControlStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "EncryptedControlStore(<redacted>)"


__all__ = ["ControlStoreError", "EncryptedControlStore"]
