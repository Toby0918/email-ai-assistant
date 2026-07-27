"""Stable no-follow opened-handle chain for one controlled Windows path."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .contracts import HostObjectKind, HostObjectObservationV1
from .errors import RealHostPreflightError
from .windows_api import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    _NativeObservation,
    _WindowsApi,
    _WindowsApiFailure,
)
from .windows_paths import expected_final_path, path_components
from .windows_projection import ROOT_PARENT_FINGERPRINT, to_host_observation


@dataclass(frozen=True, slots=True, repr=False)
class OpenedComponent:
    native: _NativeObservation
    observation: HostObjectObservationV1


@dataclass(slots=True, repr=False)
class OpenedChain:
    handles: list[int]
    components: list[OpenedComponent]


@contextmanager
def opened_chain(api: _WindowsApi, path: Path) -> Iterator[OpenedChain]:
    chain = _acquire_chain(api, path)
    try:
        yield chain
        _require_stable(api, chain)
    finally:
        _close_chain(api, chain)


def _acquire_chain(api: _WindowsApi, path: Path) -> OpenedChain:
    handles: list[int] = []
    components: list[OpenedComponent] = []
    parent_identity = ROOT_PARENT_FINGERPRINT
    try:
        components_to_open = path_components(path)
        for index, component_path in enumerate(components_to_open):
            handle = api.open_existing(component_path)
            handles.append(handle)
            native = api.observe(handle)
            observed = to_host_observation(native, parent_identity)
            _validate_component(
                native,
                observed,
                component_path,
                expected_directory=index < len(components_to_open) - 1,
            )
            components.append(OpenedComponent(native, observed))
            parent_identity = observed.object_identity_fingerprint
        return OpenedChain(handles, components)
    except Exception:
        _close_handles_best_effort(api, handles)
        raise


def _validate_component(
    native: _NativeObservation,
    observed: HostObjectObservationV1,
    path: Path,
    *,
    expected_directory: bool,
) -> None:
    if native.filesystem_name != "NTFS" or native.drive_type != "fixed":
        _fail("host_object_unavailable")
    if native.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        _fail("host_object_reparse_forbidden")
    if expected_directory and observed.object_kind is not HostObjectKind.DIRECTORY:
        _fail("host_object_kind_mismatch")
    if (
        observed.object_kind is HostObjectKind.FILE
        and native.number_of_links != 1
    ):
        _fail("host_object_alias_forbidden")
    if native.normalized_path.casefold() != expected_final_path(path).casefold():
        _fail("host_object_outside_scope")


def _require_stable(api: _WindowsApi, chain: OpenedChain) -> None:
    for handle, component in zip(chain.handles, chain.components, strict=True):
        if api.observe(handle) != component.native:
            _fail("host_object_identity_changed")


def _close_chain(api: _WindowsApi, chain: OpenedChain) -> None:
    failure = False
    for handle in reversed(chain.handles):
        try:
            api.close(handle)
        except _WindowsApiFailure:
            failure = True
    chain.handles.clear()
    if failure:
        _fail("host_object_unavailable")


def _close_handles_best_effort(api: _WindowsApi, handles: list[int]) -> None:
    for handle in reversed(handles):
        try:
            api.close(handle)
        except _WindowsApiFailure:
            pass


def _fail(code: str) -> None:
    raise RealHostPreflightError(code) from None
