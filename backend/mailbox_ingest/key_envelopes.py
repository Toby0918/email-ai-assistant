"""DPAPI and separate offline recovery envelopes for one vault master key."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Callable

from .dpapi import DpapiProtector
from .envelope_cleanup import revoke_vault_key_files
from .envelope_io import (
    decode_bytes,
    encode_bytes,
    read_json_exact,
    write_json_atomic,
)
from .errors import VaultError
from .models import SecretBuffer
from .recovery_envelopes import (
    decrypt_recovery_envelope as _decrypt_recovery_envelope,
    read_recovery_key as _read_recovery_key,
    write_recovery_envelope as _write_recovery_envelope,
    write_recovery_key as _write_recovery_key,
)


KEYS_DIRECTORY = "keys"
DPAPI_ENVELOPE = "dpapi.json"
RECOVERY_STATE = "recovery-state.json"
_MASTER_MAGIC = b"MBMASTER1"
_FORMAT_VERSION = 1
_KEY_VERSION = 1
_DPAPI_PURPOSE = "mailbox-vault-master-current-user"
_DPAPI_FIELDS = {
    "format_version", "algorithm", "vault_id", "key_version", "purpose",
    "protected_master_key",
}
_STATE_FIELDS = {
    "format_version", "vault_id", "state", "active_generation",
    "staged_generation", "prior_generation", "active_recovery_key_id",
    "prepared_recovery_key_id",
}


def initialize_key_envelopes(
    vault_root: Path,
    recovery_key_path: Path,
    dpapi: DpapiProtector,
    *,
    rng: Callable[[int], bytes] = os.urandom,
    distinct_volume_check: Callable[[Path, Path], bool] | None = None,
    vault_id: str | None = None,
    crash_hook: Callable[[str], None] | None = None,
) -> None:
    from .key_initialization import initialize_key_envelopes as implementation

    implementation(
        vault_root,
        recovery_key_path,
        dpapi,
        rng=rng,
        distinct_volume_check=distinct_volume_check,
        vault_id=vault_id,
        crash_hook=crash_hook,
    )


def open_master_key(vault_root: Path, dpapi: DpapiProtector) -> SecretBuffer:
    keys = Path(vault_root) / KEYS_DIRECTORY
    envelope = read_json_exact(keys / DPAPI_ENVELOPE, _DPAPI_FIELDS)
    _validate_dpapi_envelope(envelope)
    protected = decode_bytes(envelope["protected_master_key"])
    payload = dpapi.unprotect(protected)
    try:
        return _parse_master_payload(
            payload, str(envelope["vault_id"]), int(envelope["key_version"])
        )
    finally:
        payload.wipe()


def open_master_key_with_recovery(
    vault_root: Path, recovery_key_path: Path
) -> SecretBuffer:
    keys = Path(vault_root) / KEYS_DIRECTORY
    state = _load_state(keys)
    generation = _strict_positive_int(state["active_generation"])
    recovery_key_id, recovery_kek = _read_recovery_key(Path(recovery_key_path))
    try:
        return _decrypt_recovery_envelope(
            keys,
            str(state["vault_id"]),
            generation,
            recovery_key_id,
            recovery_kek,
        )
    finally:
        recovery_kek.wipe()


def _write_dpapi_envelope(keys: Path, vault_id: str, protected: bytes) -> None:
    write_json_atomic(
        keys / DPAPI_ENVELOPE,
        {
            "format_version": _FORMAT_VERSION,
            "algorithm": "DPAPI_CURRENT_USER",
            "vault_id": vault_id,
            "key_version": _KEY_VERSION,
            "purpose": _DPAPI_PURPOSE,
            "protected_master_key": encode_bytes(protected),
        },
    )


def _validate_dpapi_envelope(envelope: dict[str, object]) -> None:
    if (
        envelope["format_version"] != _FORMAT_VERSION
        or envelope["algorithm"] != "DPAPI_CURRENT_USER"
        or envelope["key_version"] != _KEY_VERSION
        or envelope["purpose"] != _DPAPI_PURPOSE
    ):
        raise VaultError("invalid_key_envelope")
    _validate_vault_id(envelope["vault_id"])


def _master_payload(vault_id: str, master_key: bytes | bytearray) -> bytes:
    return _MASTER_MAGIC + uuid.UUID(vault_id).bytes + _KEY_VERSION.to_bytes(2, "big") + bytes(master_key)


def _parse_master_payload(
    payload: bytes | bytearray, vault_id: str, key_version: int
) -> SecretBuffer:
    expected_size = len(_MASTER_MAGIC) + 16 + 2 + 32
    if len(payload) != expected_size or not bytes(payload).startswith(_MASTER_MAGIC):
        raise VaultError("invalid_key_envelope")
    offset = len(_MASTER_MAGIC)
    stored_vault = bytes(payload[offset:offset + 16])
    stored_version = int.from_bytes(payload[offset + 16:offset + 18], "big")
    if stored_vault != uuid.UUID(vault_id).bytes or stored_version != key_version:
        raise VaultError("invalid_key_envelope")
    return SecretBuffer(payload[-32:])


def _stable_state(vault_id: str, generation: int, key_id: str) -> dict[str, object]:
    return {
        "format_version": _FORMAT_VERSION,
        "vault_id": vault_id,
        "state": "stable",
        "active_generation": generation,
        "staged_generation": None,
        "prior_generation": None,
        "active_recovery_key_id": key_id,
        "prepared_recovery_key_id": None,
    }


def _load_state(keys: Path) -> dict[str, object]:
    state = read_json_exact(keys / RECOVERY_STATE, _STATE_FIELDS)
    _validate_vault_id(state["vault_id"])
    if state["format_version"] != _FORMAT_VERSION:
        raise VaultError("rewrap_state_invalid")
    return state


def _write_state(keys: Path, state: dict[str, object]) -> None:
    write_json_atomic(keys / RECOVERY_STATE, state)


def _validate_vault_id(value: object) -> None:
    if not isinstance(value, str):
        raise VaultError("invalid_vault_id")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise VaultError("invalid_vault_id") from None
    if str(parsed) != value:
        raise VaultError("invalid_vault_id")


def _strict_positive_int(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise VaultError("rewrap_state_invalid")
    return value


def _random_exact(rng: Callable[[int], bytes], size: int) -> bytes:
    try:
        value = rng(size)
    except Exception:
        raise VaultError("key_envelope_write_failed") from None
    if type(value) is not bytes or len(value) != size:
        raise VaultError("key_envelope_write_failed")
    return value


def _require_distinct_volume(
    vault: Path,
    recovery: Path,
    checker: Callable[[Path, Path], bool] | None,
) -> None:
    try:
        distinct = (
            checker(vault, recovery)
            if checker is not None
            else os.stat(vault).st_dev != os.stat(recovery.parent).st_dev
        )
    except Exception:
        raise VaultError("recovery_volume_not_separate") from None
    if distinct is not True:
        raise VaultError("recovery_volume_not_separate")


def revoke_key_envelopes(vault_root: Path) -> None:
    """Remove vault-local usable envelopes, never the offline recovery medium."""

    revoke_vault_key_files(Path(vault_root) / KEYS_DIRECTORY)


def rewrap_recovery_key(*args: object, **kwargs: object) -> None:
    from .recovery_rewrap import rewrap_recovery_key as implementation

    implementation(*args, **kwargs)


def reconcile_recovery_rewrap(*args: object, **kwargs: object) -> None:
    from .recovery_rewrap import reconcile_recovery_rewrap as implementation

    implementation(*args, **kwargs)
