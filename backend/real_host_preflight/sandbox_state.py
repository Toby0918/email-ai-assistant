"""Module-owned state for the Windows test-sandbox capability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from weakref import WeakKeyDictionary


@dataclass(frozen=True, slots=True, repr=False)
class SandboxStateV1:
    root: Path
    marker: Path
    root_identity: str
    root_normalized_path: str
    root_volume_fingerprint: str
    marker_identity: str
    marker_name_fingerprint: str


_LOCK = Lock()
_PERMITS: WeakKeyDictionary[Any, SandboxStateV1] = WeakKeyDictionary()
_SCOPES: WeakKeyDictionary[Any, SandboxStateV1] = WeakKeyDictionary()
_OBSERVERS: WeakKeyDictionary[Any, SandboxStateV1] = WeakKeyDictionary()


def _register_permit(permit: object, state: SandboxStateV1) -> None:
    with _LOCK:
        _PERMITS[permit] = state


def _claim_permit(permit: object) -> SandboxStateV1:
    with _LOCK:
        try:
            return _PERMITS.pop(permit)
        except (KeyError, TypeError):
            raise LookupError("sandbox permit invalid") from None


def _register_scope(scope: object, state: SandboxStateV1) -> None:
    with _LOCK:
        _SCOPES[scope] = state


def _scope_state(scope: object) -> SandboxStateV1:
    with _LOCK:
        try:
            return _SCOPES[scope]
        except (KeyError, TypeError):
            raise LookupError("sandbox scope invalid") from None


def _register_observer(observer: object, state: SandboxStateV1) -> None:
    with _LOCK:
        _OBSERVERS[observer] = state


def _observer_state(observer: object) -> SandboxStateV1:
    with _LOCK:
        try:
            return _OBSERVERS[observer]
        except (KeyError, TypeError):
            raise LookupError("sandbox observer invalid") from None
