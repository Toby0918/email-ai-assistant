"""Module-owned bindings for immutable ACL adapters and baseline receipts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from weakref import WeakKeyDictionary

from .acl_contracts import (
    AclCompatibilityPolicyV1,
    AclDescriptorObservationV1,
)


@dataclass(frozen=True, slots=True, repr=False)
class AclAdapterState:
    paths: object
    profile_fingerprint: str
    authorization_fingerprint: str
    policy: AclCompatibilityPolicyV1
    operator_sid: bytes
    root: Path
    marker: Path
    root_identity: str
    marker_identity: str


@dataclass(frozen=True, slots=True, repr=False)
class BaselineState:
    adapter: object
    role: object
    observation: AclDescriptorObservationV1


@dataclass(frozen=True, slots=True, repr=False)
class AppliedAclState:
    container_identity: str
    principal_sids: tuple[bytes, ...]
    descriptor_observation_fingerprint: str


_LOCK = Lock()
_ADAPTERS: WeakKeyDictionary[Any, AclAdapterState] = WeakKeyDictionary()
_BASELINES: WeakKeyDictionary[Any, BaselineState] = WeakKeyDictionary()
_APPLIED: WeakKeyDictionary[Any, AppliedAclState] = WeakKeyDictionary()


def register_adapter(adapter: object, state: AclAdapterState) -> None:
    with _LOCK:
        _ADAPTERS[adapter] = state


def adapter_state(adapter: object) -> AclAdapterState:
    with _LOCK:
        try:
            return _ADAPTERS[adapter]
        except (KeyError, TypeError):
            raise LookupError("ACL adapter state unavailable") from None


def register_baseline(receipt: object, state: BaselineState) -> None:
    with _LOCK:
        _BASELINES[receipt] = state


def baseline_state(receipt: object) -> BaselineState:
    with _LOCK:
        try:
            return _BASELINES[receipt]
        except (KeyError, TypeError):
            raise LookupError("ACL baseline state unavailable") from None


def register_applied(adapter: object, state: AppliedAclState) -> None:
    with _LOCK:
        _APPLIED[adapter] = state


def applied_state(adapter: object) -> AppliedAclState:
    with _LOCK:
        try:
            return _APPLIED[adapter]
        except (KeyError, TypeError):
            raise LookupError("applied ACL state unavailable") from None
