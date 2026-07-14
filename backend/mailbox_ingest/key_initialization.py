"""Crash-recoverable initial publication of vault key envelopes."""

from __future__ import annotations

import hmac
import os
import uuid
from pathlib import Path
from typing import Callable

from .dpapi import DpapiProtector
from .envelope_cleanup import revoke_vault_key_files
from .envelope_io import read_json_exact, write_json_atomic
from .errors import VaultError
from .key_envelopes import (
    DPAPI_ENVELOPE,
    KEYS_DIRECTORY,
    RECOVERY_STATE,
    _decrypt_recovery_envelope,
    _load_state,
    _master_payload,
    _random_exact,
    _read_recovery_key,
    _require_distinct_volume,
    _stable_state,
    _validate_vault_id,
    _write_dpapi_envelope,
    _write_recovery_envelope,
    _write_recovery_key,
    _write_state,
    open_master_key,
)
from .models import SecretBuffer
from .recovery_envelopes import recovery_key_id


INITIALIZATION_STATE = "initialization-state.json"
_FORMAT_VERSION = 1
_PURPOSE = "mailbox-vault-initialization"
_INTENT_FIELDS = {
    "format_version", "state", "purpose", "vault_id", "generation",
    "recovery_key_id",
}
CrashHook = Callable[[str], None]


def initialize_key_envelopes(
    vault_root: Path,
    recovery_key_path: Path,
    dpapi: DpapiProtector,
    *,
    rng: Callable[[int], bytes] = os.urandom,
    distinct_volume_check: Callable[[Path, Path], bool] | None = None,
    vault_id: str | None = None,
    crash_hook: CrashHook | None = None,
) -> None:
    vault = Path(vault_root)
    recovery = Path(recovery_key_path)
    _require_distinct_volume(vault, recovery, distinct_volume_check)
    keys = vault / KEYS_DIRECTORY
    intent_path = keys / INITIALIZATION_STATE
    if intent_path.exists() and _resume_intent(
        keys, recovery, dpapi, vault_id
    ):
        return
    _reject_preexisting_material(keys, recovery)
    selected_id = str(uuid.uuid4()) if vault_id is None else vault_id
    _validate_vault_id(selected_id)
    _start_initialization(
        keys, recovery, dpapi, selected_id, rng, crash_hook
    )


def _start_initialization(
    keys: Path,
    recovery: Path,
    dpapi: DpapiProtector,
    vault_id: str,
    rng: Callable[[int], bytes],
    crash_hook: CrashHook | None,
) -> None:
    master = SecretBuffer(_random_exact(rng, 32))
    recovery_key = SecretBuffer(_random_exact(rng, 32))
    try:
        protected = dpapi.protect(_master_payload(vault_id, master))
        key_id = recovery_key_id(recovery_key)
        intent = _new_intent(vault_id, key_id)
        write_json_atomic(keys / INITIALIZATION_STATE, intent)
        _call_hook(crash_hook, "prepared")
        _write_recovery_envelope(
            keys, vault_id, 1, key_id, recovery_key, master,
            _random_exact(rng, 12),
        )
        _write_dpapi_envelope(keys, vault_id, protected)
        if _write_recovery_key(recovery, recovery_key) != key_id:
            raise VaultError("recovery_key_invalid")
        _call_hook(crash_hook, "recovery_key_created")
    finally:
        master.wipe()
        recovery_key.wipe()
    _finalize_intent(keys, recovery, dpapi, intent)


def _resume_intent(
    keys: Path,
    recovery: Path,
    dpapi: DpapiProtector,
    requested_vault_id: str | None,
) -> bool:
    intent = _load_intent(keys)
    if requested_vault_id is not None:
        _validate_vault_id(requested_vault_id)
        if requested_vault_id != intent["vault_id"]:
            raise VaultError("key_envelopes_exist")
    if not recovery.exists():
        if (keys / RECOVERY_STATE).exists():
            raise VaultError("recovery_key_missing")
        revoke_vault_key_files(keys)
        return False
    _finalize_intent(keys, recovery, dpapi, intent)
    return True


def _finalize_intent(
    keys: Path,
    recovery: Path,
    dpapi: DpapiProtector,
    intent: dict[str, object],
) -> None:
    expected_key_id = str(intent["recovery_key_id"])
    key_id, recovery_key = _read_recovery_key(recovery)
    dpapi_master = recovery_master = None
    try:
        if key_id != expected_key_id:
            raise VaultError("recovery_key_invalid")
        dpapi_master = open_master_key(keys.parent, dpapi)
        recovery_master = _decrypt_recovery_envelope(
            keys, str(intent["vault_id"]), 1, key_id, recovery_key
        )
        if not hmac.compare_digest(bytes(dpapi_master), bytes(recovery_master)):
            raise VaultError("invalid_key_envelope")
    finally:
        recovery_key.wipe()
        if dpapi_master is not None:
            dpapi_master.wipe()
        if recovery_master is not None:
            recovery_master.wipe()
    _publish_stable_state(keys, intent)
    try:
        (keys / INITIALIZATION_STATE).unlink(missing_ok=True)
    except OSError:
        raise VaultError("key_envelope_write_failed") from None


def _publish_stable_state(
    keys: Path, intent: dict[str, object]
) -> None:
    expected = _stable_state(
        str(intent["vault_id"]), 1, str(intent["recovery_key_id"])
    )
    if (keys / RECOVERY_STATE).exists():
        if _load_state(keys) != expected:
            raise VaultError("rewrap_state_invalid")
        return
    _write_state(keys, expected)


def _reject_preexisting_material(keys: Path, recovery: Path) -> None:
    if recovery.exists():
        raise VaultError("recovery_key_exists")
    active = (DPAPI_ENVELOPE, RECOVERY_STATE, "recovery.1.json")
    if any((keys / name).exists() for name in active):
        raise VaultError("key_envelopes_exist")


def _new_intent(vault_id: str, key_id: str) -> dict[str, object]:
    return {
        "format_version": _FORMAT_VERSION,
        "state": "prepared",
        "purpose": _PURPOSE,
        "vault_id": vault_id,
        "generation": 1,
        "recovery_key_id": key_id,
    }


def _load_intent(keys: Path) -> dict[str, object]:
    intent = read_json_exact(keys / INITIALIZATION_STATE, _INTENT_FIELDS)
    _validate_vault_id(intent["vault_id"])
    key_id = intent["recovery_key_id"]
    if (
        intent["format_version"] != _FORMAT_VERSION
        or intent["state"] != "prepared"
        or intent["purpose"] != _PURPOSE
        or intent["generation"] != 1
        or not isinstance(key_id, str)
        or len(key_id) != 32
        or any(character not in "0123456789abcdef" for character in key_id)
    ):
        raise VaultError("invalid_key_envelope")
    return intent


def _call_hook(hook: CrashHook | None, state: str) -> None:
    if hook is not None:
        hook(state)
