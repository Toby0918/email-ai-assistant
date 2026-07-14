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
    _advance_rewrap(keys, new_path, crash_hook)


def reconcile_recovery_rewrap(
    vault_root: Path,
    old_recovery_path: Path,
    new_recovery_path: Path,
    *,
    distinct_volume_check: Callable[[Path, Path], bool] | None = None,
) -> None:
    vault = Path(vault_root)
    new_path = Path(new_recovery_path)
    _require_distinct_volume(vault, new_path, distinct_volume_check)
    keys = vault / KEYS_DIRECTORY
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
    recovery_key = None
    try:
        recovery_key = _new_recovery_key(new_path, rng)
        key_id = _recovery_key_id(new_path, recovery_key)
        nonce = _random_exact(rng, 12)
        _write_recovery_envelope(
            keys,
            str(state["vault_id"]),
            generation,
            key_id,
            recovery_key,
            master,
            nonce,
        )
        _call_hook(crash_hook, "envelope_staged")
        _write_state(keys, _staged_state(state, generation))
        _call_hook(crash_hook, "staged")
    finally:
        master.wipe()
        if recovery_key is not None:
            recovery_key.wipe()


def _new_recovery_key(path: Path, rng: Callable[[int], bytes]):
    from .models import SecretBuffer

    key = SecretBuffer(_random_exact(rng, 32))
    _write_recovery_key(path, key)
    return key


def _recovery_key_id(path: Path, key) -> str:
    key_id, reread = _read_recovery_key(path)
    try:
        if bytes(reread) != bytes(key):
            raise VaultError("recovery_key_invalid")
        return key_id
    finally:
        reread.wipe()


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


def _staged_state(
    state: dict[str, object], generation: int
) -> dict[str, object]:
    return {
        "format_version": state["format_version"],
        "vault_id": state["vault_id"],
        "state": "staged",
        "active_generation": state["active_generation"],
        "staged_generation": generation,
        "prior_generation": None,
        "active_recovery_key_id": state["active_recovery_key_id"],
    }


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
