"""Pure recovery-rewrap state transitions and intent validation."""

from __future__ import annotations

from .errors import VaultError


def prepared_key_id(state: dict[str, object]) -> str:
    value = state["prepared_recovery_key_id"]
    if (
        not isinstance(value, str)
        or len(value) != 32
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise VaultError("rewrap_state_invalid")
    return value


def staged_state(
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
        "prepared_recovery_key_id": None,
    }


def prepared_state(
    state: dict[str, object], generation: int, key_id: str
) -> dict[str, object]:
    return {
        **state,
        "state": "prepared",
        "staged_generation": generation,
        "prior_generation": None,
        "prepared_recovery_key_id": key_id,
    }


def rolled_back_state(state: dict[str, object]) -> dict[str, object]:
    return {
        **state,
        "state": "stable",
        "staged_generation": None,
        "prior_generation": None,
        "prepared_recovery_key_id": None,
    }
