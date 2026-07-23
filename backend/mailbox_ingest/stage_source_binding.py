"""Shared authority and path binding for fixed-mode stage sources."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .errors import VaultError


def open_bound_stage_vault(
    vault_root: Path,
    *,
    authorization_id: str,
    account: str,
    expected_vault_id: str,
    expected_scope: str,
    project_root: Path,
    validate_existing: Callable[..., object],
    dpapi_factory: Callable[[], object],
    opener: Callable[..., object],
    clock: Callable[[], int],
) -> object:
    validate_existing(Path(vault_root), Path(project_root))
    opened = opener(Path(vault_root), dpapi=dpapi_factory(), clock=clock)
    try:
        scope = opened.require_authorization_scope(authorization_id, account)
        if (
            getattr(opened.identity, "vault_id", None) != expected_vault_id
            or getattr(scope, "opaque_scope_id", None) != expected_scope
        ):
            raise VaultError("stage_scope_mismatch")
        return opened
    except Exception:
        opened.close()
        raise
