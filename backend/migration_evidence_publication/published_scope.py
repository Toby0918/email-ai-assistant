"""One-time private handoff from publication to verification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from weakref import WeakKeyDictionary

from .publication_receipts import (
    MigrationEvidenceCreatedReceiptV1,
    _publication_binding,
)


_SCOPE_ERROR = "MIGRATION_EVIDENCE_PUBLISHED_SCOPE_REJECTED"


@dataclass(slots=True)
class _PublishedScope:
    target: Path
    claimed: bool = False


_SCOPES: WeakKeyDictionary[object, _PublishedScope] = WeakKeyDictionary()
_SCOPES_LOCK = Lock()


def _register_published_target(
    receipt: MigrationEvidenceCreatedReceiptV1,
    target: Path,
) -> None:
    _publication_binding(receipt)
    if not isinstance(target, Path) or not target.is_absolute():
        raise ValueError(_SCOPE_ERROR)
    with _SCOPES_LOCK:
        if receipt in _SCOPES:
            raise ValueError(_SCOPE_ERROR)
        _SCOPES[receipt] = _PublishedScope(target=target)


def _claim_published_target(
    receipt: MigrationEvidenceCreatedReceiptV1,
) -> Path:
    _publication_binding(receipt)
    with _SCOPES_LOCK:
        scope = _SCOPES.get(receipt)
        if scope is None or scope.claimed:
            raise ValueError(_SCOPE_ERROR)
        scope.claimed = True
        return scope.target
