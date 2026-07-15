"""Independent protected key envelopes for authority, candidate, and snapshot use."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .atomic_ciphertext import read_ciphertext, replace_ciphertext
from .errors import PrivateKnowledgeError


_AUTHORITY_FILE = "authority-keys.pkenv"
_CANDIDATE_FILE = "candidate-key.pkenv"
_AUTHORITY_MAGIC = b"PKAUTHKEY1"
_CANDIDATE_MAGIC = b"PKCANDKEY1"


class KeyProtector(Protocol):
    def protect(self, value: bytes) -> bytes: ...
    def unprotect(self, value: bytes) -> bytes: ...


class SecretBytes(bytearray):
    def wipe(self) -> None:
        for index in range(len(self)):
            self[index] = 0

    def __enter__(self) -> SecretBytes:
        return self

    def __exit__(self, *_args: object) -> None:
        self.wipe()

    def __repr__(self) -> str:
        return "SecretBytes(<redacted>)"


@dataclass(slots=True, repr=False)
class AuthorityKeyMaterial:
    authority_key: SecretBytes = field(repr=False)
    snapshot_key: SecretBytes = field(repr=False)
    signing_seed: SecretBytes = field(repr=False)

    def close(self) -> None:
        self.authority_key.wipe()
        self.snapshot_key.wipe()
        self.signing_seed.wipe()

    def __enter__(self) -> AuthorityKeyMaterial:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "AuthorityKeyMaterial(<redacted>)"


def initialize_private_keys(
    authority_root: Path,
    candidate_root: Path,
    protector: KeyProtector,
    *,
    rng: Callable[[int], bytes] = os.urandom,
) -> None:
    authority = _root(authority_root)
    candidate = _root(candidate_root)
    if (authority == candidate or authority in candidate.parents
            or candidate in authority.parents):
        raise PrivateKnowledgeError("key_namespace_not_separate")
    try:
        authority_path = authority / _AUTHORITY_FILE
        candidate_path = candidate / _CANDIDATE_FILE
        authority_exists = _validate_existing_envelope(
            authority_path, "authority", _AUTHORITY_MAGIC, 96, protector
        )
        candidate_exists = _validate_existing_envelope(
            candidate_path, "candidate", _CANDIDATE_MAGIC, 32, protector
        )
        if not authority_exists:
            _initialize_envelope(
                authority_path, "authority", _AUTHORITY_MAGIC, 96,
                protector, rng,
            )
        if not candidate_exists:
            _initialize_envelope(
                candidate_path, "candidate", _CANDIDATE_MAGIC, 32,
                protector, rng,
            )
    except PrivateKnowledgeError:
        raise
    except Exception:
        raise PrivateKnowledgeError("key_protection_failed") from None


def open_authority_keys(root: Path, protector: KeyProtector) -> AuthorityKeyMaterial:
    payload = _unprotect(_root(root) / _AUTHORITY_FILE, "authority", protector)
    if len(payload) != len(_AUTHORITY_MAGIC) + 96 or not payload.startswith(_AUTHORITY_MAGIC):
        raise PrivateKnowledgeError("key_envelope_invalid")
    offset = len(_AUTHORITY_MAGIC)
    return AuthorityKeyMaterial(
        SecretBytes(payload[offset:offset + 32]),
        SecretBytes(payload[offset + 32:offset + 64]),
        SecretBytes(payload[offset + 64:offset + 96]),
    )


def open_candidate_key(root: Path, protector: KeyProtector) -> SecretBytes:
    payload = _unprotect(_root(root) / _CANDIDATE_FILE, "candidate", protector)
    if len(payload) != len(_CANDIDATE_MAGIC) + 32 or not payload.startswith(_CANDIDATE_MAGIC):
        raise PrivateKnowledgeError("key_envelope_invalid")
    return SecretBytes(payload[-32:])


def _write_envelope(path: Path, purpose: str, protected: bytes) -> None:
    if path.exists() or type(protected) is not bytes or not protected:
        raise PrivateKnowledgeError("key_envelope_exists")
    payload = json.dumps(
        {"format_version": 1, "purpose": purpose,
         "protected": base64.b64encode(protected).decode("ascii")},
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")
    replace_ciphertext(path, payload, error_code="key_envelope_write_failed")


def _validate_existing_envelope(
    path: Path,
    purpose: str,
    magic: bytes,
    key_size: int,
    protector: KeyProtector,
) -> bool:
    if not _envelope_exists(path):
        return False
    payload = _unprotect(path, purpose, protector)
    if len(payload) != len(magic) + key_size or not payload.startswith(magic):
        raise PrivateKnowledgeError("key_envelope_invalid")
    return True


def _initialize_envelope(
    path: Path,
    purpose: str,
    magic: bytes,
    key_size: int,
    protector: KeyProtector,
    rng: Callable[[int], bytes],
) -> None:
    payload = magic + _random(rng, key_size)
    _write_envelope(path, purpose, protector.protect(payload))


def _envelope_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError:
        raise PrivateKnowledgeError("key_envelope_read_failed") from None
    return True


def _unprotect(path: Path, purpose: str, protector: KeyProtector) -> bytes:
    try:
        value = json.loads(read_ciphertext(
            path, maximum=16 * 1024, code="key_envelope_read_failed"
        ).decode("ascii"))
        if (not isinstance(value, dict)
                or set(value) != {"format_version", "purpose", "protected"}
                or value["format_version"] != 1 or value["purpose"] != purpose):
            raise ValueError
        protected = base64.b64decode(value["protected"], validate=True)
        result = protector.unprotect(protected)
        if type(result) is not bytes:
            raise ValueError
        return result
    except PrivateKnowledgeError:
        raise
    except Exception:
        raise PrivateKnowledgeError("key_envelope_invalid") from None


def _random(rng: Callable[[int], bytes], size: int) -> bytes:
    try:
        value = rng(size)
    except Exception:
        raise PrivateKnowledgeError("key_generation_failed") from None
    if type(value) is not bytes or len(value) != size:
        raise PrivateKnowledgeError("key_generation_failed")
    return value


def _root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("path_invalid")
    return path.resolve()
