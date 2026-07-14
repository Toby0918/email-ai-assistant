"""Exact vault-local key-envelope revocation targets."""

from __future__ import annotations

import re
from pathlib import Path

from .errors import VaultError


_RECOVERY_LEAF = r"recovery\.[1-9][0-9]*\.json"
_FIXED_LEAF = r"(?:dpapi\.json|recovery-state\.json|initialization-state\.json)"
_ENVELOPE_LEAF = rf"(?:{_FIXED_LEAF}|{_RECOVERY_LEAF})"
_REVOKE_TARGET = re.compile(
    rf"^(?:{_ENVELOPE_LEAF}|\.{_ENVELOPE_LEAF}\.[0-9a-f]{{32}}\.stage)$"
)


def revoke_vault_key_files(keys: Path) -> None:
    try:
        for path in keys.iterdir():
            if _REVOKE_TARGET.fullmatch(path.name) is not None:
                path.unlink(missing_ok=True)
        if any(
            _REVOKE_TARGET.fullmatch(path.name) is not None
            for path in keys.iterdir()
        ):
            raise OSError
    except FileNotFoundError:
        return
    except OSError:
        raise VaultError("revoke_incomplete") from None
