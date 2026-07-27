"""Content-free Windows observations confined to a test-owned sandbox."""

from __future__ import annotations

from pathlib import Path

from .canonical import is_fingerprint
from .contracts import (
    HostObjectKind,
    HostObjectObservationV1,
    MissingHostObjectObservationV1,
)
from .errors import RealHostPreflightError
from .evidence import VolumeObservationV1
from .sandbox_lease import active_sandbox_lease, capture_sandbox_state
from .sandbox_state import (
    SandboxStateV1,
    _claim_permit,
    _observer_state,
    _register_observer,
    _register_permit,
    _register_scope,
    _scope_state,
)
from .sandbox_validation import (
    require_absolute_local_path,
    validate_sandbox_authorization,
)
from .windows_api import _WindowsApi, _WindowsApiFailure, _text_fingerprint
from .windows_chain import OpenedChain, opened_chain
from .windows_paths import expected_final_path


_SANDBOX_MARKER_NAME = ".codex-preflight-test-sandbox"


class _TestSandboxPermitV1:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("test sandbox permit requires internal issuance")


class TestSandboxScopeV1:
    """One exact temporary Windows directory authorized for test observation."""

    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("test sandbox scope requires permit")

    @classmethod
    def create(cls, *, permit: object) -> TestSandboxScopeV1:
        if type(permit) is not _TestSandboxPermitV1:
            _fail("host_scope_invalid")
        try:
            expected = _claim_permit(permit)
            observed = capture_sandbox_state(expected.root, expected.marker)
            if observed != expected:
                _fail("host_object_identity_changed")
            value = object.__new__(cls)
            _register_scope(value, observed)
            return value
        except RealHostPreflightError:
            raise
        except (_WindowsApiFailure, LookupError):
            _fail("host_scope_invalid")
        except Exception:
            _fail("internal_error")


class WindowsReadOnlyObserver:
    """Observe only objects contained by one validated test sandbox."""

    __slots__ = ("__weakref__",)

    def __init__(self, scope: TestSandboxScopeV1) -> None:
        if type(scope) is not TestSandboxScopeV1:
            _fail("host_scope_invalid")
        try:
            _register_observer(self, _scope_state(scope))
        except LookupError:
            _fail("host_scope_invalid")

    def observe_existing(
        self,
        path: Path,
        *,
        expected_kind: HostObjectKind,
        expected_volume_fingerprint: str | None = None,
    ) -> HostObjectObservationV1:
        try:
            state = _observer_state(self)
            if type(expected_kind) is not HostObjectKind:
                _fail("host_object_kind_mismatch")
            _require_expected_volume(state, expected_volume_fingerprint)
            _validate_target(state, path)
            with active_sandbox_lease(state):
                api = _WindowsApi()
                with opened_chain(api, path) as chain:
                    _require_scope_binding(state, chain)
                    result = chain.components[-1].observation
                    if result.object_kind is not expected_kind:
                        _fail("host_object_kind_mismatch")
                    return result
        except RealHostPreflightError:
            raise
        except (_WindowsApiFailure, LookupError):
            _fail("host_object_unavailable")
        except Exception:
            _fail("internal_error")

    def observe_volume(self, path: Path) -> VolumeObservationV1:
        try:
            state = _observer_state(self)
            _validate_target(state, path)
            with active_sandbox_lease(state):
                api = _WindowsApi()
                with opened_chain(api, path) as chain:
                    _require_scope_binding(state, chain)
                    component = chain.components[-1]
                    return VolumeObservationV1.create(
                        volume_fingerprint=(
                            component.observation.volume_fingerprint
                        ),
                        filesystem_name=component.native.filesystem_name,
                        drive_type=component.native.drive_type,
                        complete=True,
                    )
        except RealHostPreflightError:
            raise
        except (_WindowsApiFailure, LookupError):
            _fail("host_object_unavailable")
        except Exception:
            _fail("internal_error")

    def observe_absent(
        self,
        path: Path,
        *,
        expected_volume_fingerprint: str | None = None,
    ) -> MissingHostObjectObservationV1:
        try:
            state = _observer_state(self)
            _require_expected_volume(state, expected_volume_fingerprint)
            _validate_target(state, path)
            if path == state.root:
                _fail("host_object_outside_scope")
            with active_sandbox_lease(state):
                api = _WindowsApi()
                with opened_chain(api, path.parent) as chain:
                    _require_scope_binding(state, chain)
                    parent = chain.components[-1].observation
                    if parent.object_kind is not HostObjectKind.DIRECTORY:
                        _fail("host_object_kind_mismatch")
                    _require_leaf_absent(api, path)
                    return MissingHostObjectObservationV1.create(
                        parent_identity_fingerprint=(
                            parent.object_identity_fingerprint
                        ),
                        volume_fingerprint=parent.volume_fingerprint,
                        normalized_name_fingerprint=_text_fingerprint(
                            expected_final_path(path)
                        ),
                        filesystem_name=parent.filesystem_name,
                    )
        except RealHostPreflightError:
            raise
        except (_WindowsApiFailure, LookupError):
            _fail("host_object_unavailable")
        except Exception:
            _fail("internal_error")


def _issue_test_sandbox_permit(
    *,
    root: Path,
    marker: Path,
    authorization: object,
    observed_at_epoch: int,
) -> _TestSandboxPermitV1:
    try:
        validate_sandbox_authorization(authorization, observed_at_epoch)
        require_absolute_local_path(root)
        require_absolute_local_path(marker)
        if marker.parent != root or marker.name != _SANDBOX_MARKER_NAME:
            _fail("host_scope_invalid")
        state = capture_sandbox_state(root, marker)
        value = object.__new__(_TestSandboxPermitV1)
        _register_permit(value, state)
        return value
    except RealHostPreflightError:
        raise
    except _WindowsApiFailure:
        _fail("host_scope_invalid")
    except Exception:
        _fail("internal_error")


def _validate_target(state: SandboxStateV1, path: Path) -> None:
    require_absolute_local_path(path)
    if path != state.root and state.root not in path.parents:
        _fail("host_object_outside_scope")


def _require_scope_binding(
    state: SandboxStateV1,
    chain: OpenedChain,
) -> None:
    root_path = state.root_normalized_path.casefold()
    for index, component in enumerate(chain.components):
        if component.native.normalized_path.casefold() != root_path:
            continue
        if component.observation.object_identity_fingerprint != state.root_identity:
            _fail("host_object_identity_changed")
        if any(
            item.observation.volume_fingerprint != state.root_volume_fingerprint
            for item in chain.components[index:]
        ):
            _fail("host_volume_mismatch")
        return
    _fail("host_object_outside_scope")


def _require_expected_volume(
    state: SandboxStateV1,
    expected: object,
) -> None:
    if expected is None:
        return
    if not is_fingerprint(expected) or expected != state.root_volume_fingerprint:
        _fail("host_volume_mismatch")


def _require_leaf_absent(api: _WindowsApi, path: Path) -> None:
    try:
        handle = api.open_existing(path)
    except _WindowsApiFailure as error:
        if error.is_file_not_found:
            return
        raise
    try:
        api.close(handle)
    except _WindowsApiFailure:
        raise
    _fail("host_object_already_present")


def _fail(code: str) -> None:
    raise RealHostPreflightError(code) from None
