"""Module-owned bindings and new-directory provenance for Issue #55."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from weakref import WeakKeyDictionary, finalize

from .filesystem_contracts import (
    FilesystemMutationExpectationV1,
    FilesystemMutationObservationV1,
)


@dataclass(frozen=True, slots=True, repr=False)
class DirectoryPrimitiveState:
    root: Path
    marker: Path
    parent: Path
    target: Path
    profile_fingerprint: str
    operator_fingerprint: str
    authorization_fingerprint: str
    root_identity: str
    marker_identity: str
    parent_identity: str
    volume_fingerprint: str
    expectation: FilesystemMutationExpectationV1
    guarded_container: bool
    target_race_barrier: object | None


@dataclass(frozen=True, slots=True, repr=False)
class NewDirectoryClaim:
    target: Path
    object_identity: str
    parent_identity: str
    volume_fingerprint: str
    profile_fingerprint: str
    guarded_container: bool
    resource: Any | None


@dataclass(frozen=True, slots=True, repr=False)
class NoReplacePrimitiveState:
    root: Path
    marker: Path
    source: Path
    target_parent: Path
    target: Path
    profile_fingerprint: str
    authorization_fingerprint: str
    root_identity: str
    marker_identity: str
    source_identity: str
    parent_identity: str
    volume_fingerprint: str
    expectation: FilesystemMutationExpectationV1
    target_race_barrier: object | None


_LOCK = Lock()
_DIRECTORY_PRIMITIVES: WeakKeyDictionary[Any, DirectoryPrimitiveState] = (
    WeakKeyDictionary()
)
_NEW_DIRECTORIES: WeakKeyDictionary[Any, NewDirectoryClaim] = (
    WeakKeyDictionary()
)
_NO_REPLACE_PRIMITIVES: WeakKeyDictionary[
    Any, NoReplacePrimitiveState
] = WeakKeyDictionary()


def register_directory_primitive(
    primitive: object,
    state: DirectoryPrimitiveState,
) -> None:
    with _LOCK:
        _DIRECTORY_PRIMITIVES[primitive] = state


def directory_primitive_state(primitive: object) -> DirectoryPrimitiveState:
    with _LOCK:
        try:
            return _DIRECTORY_PRIMITIVES[primitive]
        except (KeyError, TypeError):
            raise LookupError("directory primitive unavailable") from None


def register_new_directory(
    observation: FilesystemMutationObservationV1,
    claim: NewDirectoryClaim,
) -> None:
    with _LOCK:
        _NEW_DIRECTORIES[observation] = claim
        if claim.resource is not None:
            finalize(observation, claim.resource.close_silently)


def claim_new_directory(
    observation: object,
) -> NewDirectoryClaim:
    with _LOCK:
        try:
            return _NEW_DIRECTORIES.pop(observation)
        except (KeyError, TypeError):
            raise LookupError("new directory claim unavailable") from None


def new_directory_claim(observation: object) -> NewDirectoryClaim:
    with _LOCK:
        try:
            return _NEW_DIRECTORIES[observation]
        except (KeyError, TypeError):
            raise LookupError("new directory claim unavailable") from None


def register_no_replace_primitive(
    primitive: object,
    state: NoReplacePrimitiveState,
) -> None:
    with _LOCK:
        _NO_REPLACE_PRIMITIVES[primitive] = state


def no_replace_primitive_state(
    primitive: object,
) -> NoReplacePrimitiveState:
    with _LOCK:
        try:
            return _NO_REPLACE_PRIMITIVES[primitive]
        except (KeyError, TypeError):
            raise LookupError("no-replace primitive unavailable") from None
