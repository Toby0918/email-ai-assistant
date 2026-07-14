"""Crash-recoverable recovery-envelope stage/verify/activate/finalize flow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from .errors import VaultError
from .key_envelopes import (
    KEYS_DIRECTORY,
    _decrypt_recovery_envelope,
    _load_state,
    _random_exact,
    _read_recovery_key,
    _require_distinct_volume,
    _strict_positive_int,
    _write_recovery_envelope,
    _write_recovery_key,
    _write_state,
    open_master_key_with_recovery,
)
from .models import SecretBuffer
from .recovery_envelopes import recovery_key_id as _recovery_key_id
from .recovery_rewrap_state import (
    prepared_key_id as _prepared_key_id,
    prepared_state as _prepared_state,
    rolled_back_state as _rolled_back_state,
    staged_state as _staged_state,
)


CrashHook = Callable[[str], None]


def rewrap_recovery_key(
    vault_root: Path,
    old_recovery_path: Path,
    new_recovery_path: Path,
    *,
    rng: Callable[[int], bytes] = os.urandom,
    distinct_volume_check: Callable[[Path, Path], bool] | None = None,
    crash_hook: CrashHook | None = None,
) -> None:
    vault = Path(vault_root)
    new_path = Path(new_recovery_path)
    _require_distinct_volume(vault, new_path, distinct_volume_check)
    keys = vault / KEYS_DIRECTORY
    state = _load_state(keys)
    if state["state"] == "stable":
        _stage_rewrap(
            keys,
            Path(old_recovery_path),
            new_path,
            state,
            rng,
            crash_hook,
        )
    elif state["state"] == "prepared":
        _resume_prepared(
            keys, Path(old_recovery_path), new_path, state, rng, crash_hook
        )
    _advance_rewrap(keys, new_path, crash_hook)


def reconcile_recovery_rewrap(
    vault_root: Path,
    old_recovery_path: Path,
    new_recovery_path: Path,
    *,
    rng: Callable[[int], bytes] = os.urandom,
    distinct_volume_check: Callable[[Path, Path], bool] | None = None,
) -> None:
    vault = Path(vault_root)
    new_path = Path(new_recovery_path)
    _require_distinct_volume(vault, new_path, distinct_volume_check)
    keys = vault / KEYS_DIRECTORY
    state = _load_state(keys)
    if state["state"] == "prepared":
        if not new_path.exists():
            _write_state(keys, _rolled_back_state(state))
            return
        _resume_prepared(
            keys, Path(old_recovery_path), new_path, state, rng, None
        )
        state = _load_state(keys)
    if state["state"] == "stable":
        generation = _strict_positive_int(state["active_generation"]) + 1
        if not (keys / f"recovery.{generation}.json").exists():
            return
        _record_untracked_stage(keys, new_path, state, generation)
    _advance_rewrap(keys, new_path, None)


def _stage_rewrap(
    keys: Path,
    old_path: Path,
    new_path: Path,
    state: dict[str, object],
    rng: Callable[[int], bytes],
    crash_hook: CrashHook | None,
) -> None:
    active_generation = _strict_positive_int(state["active_generation"])
    generation = active_generation + 1
    envelope_path = keys / f"recovery.{generation}.json"
    if envelope_path.exists():
        _record_untracked_stage(keys, new_path, state, generation)
        return
    if new_path.exists():
        raise VaultError("recovery_key_exists")
    master = open_master_key_with_recovery(keys.parent, old_path)
    recovery_key = SecretBuffer(_random_exact(rng, 32))
    try:
        key_id = _recovery_key_id(recovery_key)
        prepared = _prepared_state(state, generation, key_id)
        _write_state(keys, prepared)
        written_key_id = _write_recovery_key(new_path, recovery_key)
        if written_key_id != key_id:
            raise VaultError("recovery_key_invalid")
        _call_hook(crash_hook, "recovery_key_created")
        _persist_prepared_envelope(
            keys, prepared, key_id, recovery_key, master, rng, crash_hook
        )
    finally:
        master.wipe()
        recovery_key.wipe()


def _resume_prepared(
    keys: Path,
    old_path: Path,
    new_path: Path,
    state: dict[str, object],
    rng: Callable[[int], bytes],
    crash_hook: CrashHook | None,
) -> None:
    expected_key_id = _prepared_key_id(state)
    key_id, recovery_key = _read_recovery_key(new_path)
    master = None
    try:
        if key_id != expected_key_id:
            raise VaultError("recovery_key_invalid")
        master = open_master_key_with_recovery(keys.parent, old_path)
        _persist_prepared_envelope(
            keys, state, key_id, recovery_key, master, rng, crash_hook
        )
    finally:
        recovery_key.wipe()
        if master is not None:
            master.wipe()


def _persist_prepared_envelope(
    keys: Path,
    state: dict[str, object],
    key_id: str,
    recovery_key: SecretBuffer,
    master: SecretBuffer,
    rng: Callable[[int], bytes],
    crash_hook: CrashHook | None,
) -> None:
    generation = _strict_positive_int(state["staged_generation"])
    envelope_path = keys / f"recovery.{generation}.json"
    if envelope_path.exists():
        staged_master = _decrypt_recovery_envelope(
            keys, str(state["vault_id"]), generation, key_id, recovery_key
        )
        try:
            if bytes(staged_master) != bytes(master):
                raise VaultError("invalid_key_envelope")
        finally:
            staged_master.wipe()
    else:
        _write_recovery_envelope(
            keys, str(state["vault_id"]), generation, key_id,
            recovery_key, master, _random_exact(rng, 12)
        )
        _call_hook(crash_hook, "envelope_staged")
    _write_state(keys, _staged_state(state, generation))
    _call_hook(crash_hook, "staged")


def _record_untracked_stage(
    keys: Path,
    new_path: Path,
    state: dict[str, object],
    generation: int,
) -> None:
    key_id, key = _read_recovery_key(new_path)
    try:
        master = _decrypt_recovery_envelope(
            keys, str(state["vault_id"]), generation, key_id, key
        )
        master.wipe()
        _write_state(keys, _staged_state(state, generation))
    finally:
        key.wipe()


def _advance_rewrap(
    keys: Path, new_path: Path, crash_hook: CrashHook | None
) -> None:
    state = _load_state(keys)
    if state["state"] == "staged":
        _verify_staged(keys, new_path, state)
        state["state"] = "verified"
        _write_state(keys, state)
        _call_hook(crash_hook, "verified")
        state = _load_state(keys)
    if state["state"] == "verified":
        state = _activate(keys, new_path, state)
        _call_hook(crash_hook, "activated")
    if state["state"] == "activated":
        _finalize(keys, new_path, state)
        _call_hook(crash_hook, "finalized")
        return
    if state["state"] != "stable":
        raise VaultError("rewrap_state_invalid")


def _verify_staged(
    keys: Path, new_path: Path, state: dict[str, object]
) -> None:
    generation = _strict_positive_int(state["staged_generation"])
    key_id, key = _read_recovery_key(new_path)
    try:
        master = _decrypt_recovery_envelope(
            keys, str(state["vault_id"]), generation, key_id, key
        )
        master.wipe()
    finally:
        key.wipe()


def _activate(
    keys: Path, new_path: Path, state: dict[str, object]
) -> dict[str, object]:
    generation = _strict_positive_int(state["staged_generation"])
    key_id, key = _read_recovery_key(new_path)
    try:
        master = _decrypt_recovery_envelope(
            keys, str(state["vault_id"]), generation, key_id, key
        )
        master.wipe()
    finally:
        key.wipe()
    activated = {
        **state,
        "state": "activated",
        "active_generation": generation,
        "staged_generation": None,
        "prior_generation": state["active_generation"],
        "active_recovery_key_id": key_id,
    }
    _write_state(keys, activated)
    return activated


def _finalize(
    keys: Path, new_path: Path, state: dict[str, object]
) -> None:
    active_generation = _strict_positive_int(state["active_generation"])
    prior_generation = _strict_positive_int(state["prior_generation"])
    key_id, key = _read_recovery_key(new_path)
    try:
        master = _decrypt_recovery_envelope(
            keys, str(state["vault_id"]), active_generation, key_id, key
        )
        master.wipe()
    finally:
        key.wipe()
    try:
        (keys / f"recovery.{prior_generation}.json").unlink(missing_ok=True)
    except OSError:
        raise VaultError("rewrap_reconcile_failed") from None
    stable = {
        **state,
        "state": "stable",
        "prior_generation": None,
        "active_recovery_key_id": key_id,
    }
    _write_state(keys, stable)


def _call_hook(hook: CrashHook | None, state: str) -> None:
    if hook is not None:
        hook(state)
