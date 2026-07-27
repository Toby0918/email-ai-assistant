"""Opened-handle capture and lease for one test-owned Windows sandbox."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator

from .contracts import HostObjectKind
from .errors import RealHostPreflightError
from .sandbox_state import SandboxStateV1
from .windows_api import _WindowsApi, _WindowsApiFailure
from .windows_chain import OpenedChain, OpenedComponent, opened_chain


def capture_sandbox_state(root: Path, marker: Path) -> SandboxStateV1:
    api = _WindowsApi()
    with opened_chain(api, root) as root_chain:
        with opened_chain(api, marker) as marker_chain:
            return _state_from_chains(root, marker, root_chain, marker_chain)


@contextmanager
def active_sandbox_lease(
    expected: SandboxStateV1,
) -> Iterator[None]:
    if type(expected) is not SandboxStateV1:
        _fail("host_object_identity_changed")
    stack = ExitStack()
    try:
        api = _WindowsApi()
        root_chain = stack.enter_context(opened_chain(api, expected.root))
        marker_chain = stack.enter_context(opened_chain(api, expected.marker))
        observed = _state_from_chains(
            expected.root,
            expected.marker,
            root_chain,
            marker_chain,
        )
        if observed != expected:
            _fail("host_object_identity_changed")
    except Exception:
        _close_as_identity_failure(stack)
        _fail("host_object_identity_changed")
    try:
        yield
    finally:
        _close_as_identity_failure(stack)


def _state_from_chains(
    root: Path,
    marker: Path,
    root_chain: OpenedChain,
    marker_chain: OpenedChain,
) -> SandboxStateV1:
    root_component = root_chain.components[-1]
    marker_component = marker_chain.components[-1]
    if (
        root_component.observation.object_kind is not HostObjectKind.DIRECTORY
        or marker_component.observation.object_kind is not HostObjectKind.FILE
    ):
        _fail("host_scope_invalid")
    _require_captured_root(root_component, marker_chain)
    return _sandbox_state(root, marker, root_component, marker_component)


def _sandbox_state(
    root: Path,
    marker: Path,
    root_component: OpenedComponent,
    marker_component: OpenedComponent,
) -> SandboxStateV1:
    root_observation = root_component.observation
    marker_observation = marker_component.observation
    return SandboxStateV1(
        root=root,
        marker=marker,
        root_identity=root_observation.object_identity_fingerprint,
        root_normalized_path=root_component.native.normalized_path,
        root_volume_fingerprint=root_observation.volume_fingerprint,
        marker_identity=marker_observation.object_identity_fingerprint,
        marker_name_fingerprint=marker_observation.normalized_name_fingerprint,
    )


def _require_captured_root(
    expected: OpenedComponent,
    chain: OpenedChain,
) -> None:
    normalized = expected.native.normalized_path.casefold()
    for component in chain.components:
        if component.native.normalized_path.casefold() != normalized:
            continue
        if component.observation != expected.observation:
            _fail("host_object_identity_changed")
        return
    _fail("host_object_outside_scope")


def _close_as_identity_failure(stack: ExitStack) -> None:
    try:
        stack.close()
    except (RealHostPreflightError, _WindowsApiFailure):
        _fail("host_object_identity_changed")


def _fail(code: str) -> None:
    raise RealHostPreflightError(code) from None
