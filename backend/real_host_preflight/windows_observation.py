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
from .sandbox_validation import (
    require_absolute_local_path,
    validate_sandbox_authorization,
)
from .windows_api import (
    _WindowsApi,
    _WindowsApiFailure,
    _text_fingerprint,
)
from .windows_chain import OpenedChain, opened_chain
from .windows_paths import expected_final_path


class TestSandboxScopeV1:
    """One exact temporary Windows directory authorized for test observation."""

    __slots__ = (
        "_root",
        "_root_identity",
        "_root_normalized_path",
        "_root_volume_fingerprint",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("test sandbox scope requires create")

    @classmethod
    def create(
        cls,
        *,
        root: Path,
        authorization: object,
        observed_at_epoch: int,
    ) -> TestSandboxScopeV1:
        try:
            validate_sandbox_authorization(authorization, observed_at_epoch)
            require_absolute_local_path(root)
            api = _WindowsApi()
            with opened_chain(api, root) as chain:
                component = chain.components[-1]
                if component.observation.object_kind is not HostObjectKind.DIRECTORY:
                    _fail("host_scope_invalid")
                value = object.__new__(cls)
                value._root = root
                value._root_identity = component.observation.object_identity_fingerprint
                value._root_normalized_path = component.native.normalized_path
                value._root_volume_fingerprint = (
                    component.observation.volume_fingerprint
                )
                return value
        except RealHostPreflightError:
            raise
        except _WindowsApiFailure:
            _fail("host_scope_invalid")
        except Exception:
            _fail("internal_error")


class WindowsReadOnlyObserver:
    """Observe only objects contained by one validated test sandbox."""

    __slots__ = ("_scope",)

    def __init__(self, scope: TestSandboxScopeV1) -> None:
        if type(scope) is not TestSandboxScopeV1:
            _fail("host_scope_invalid")
        self._scope = scope

    def observe_existing(
        self,
        path: Path,
        *,
        expected_kind: HostObjectKind,
        expected_volume_fingerprint: str | None = None,
    ) -> HostObjectObservationV1:
        try:
            if type(expected_kind) is not HostObjectKind:
                _fail("host_object_kind_mismatch")
            self._require_expected_volume(expected_volume_fingerprint)
            self._validate_target(path)
            api = _WindowsApi()
            with opened_chain(api, path) as chain:
                self._require_scope_binding(chain)
                result = chain.components[-1].observation
                if result.object_kind is not expected_kind:
                    _fail("host_object_kind_mismatch")
                return result
        except RealHostPreflightError:
            raise
        except _WindowsApiFailure:
            _fail("host_object_unavailable")
        except Exception:
            _fail("internal_error")

    def observe_volume(self, path: Path) -> VolumeObservationV1:
        try:
            self._validate_target(path)
            api = _WindowsApi()
            with opened_chain(api, path) as chain:
                self._require_scope_binding(chain)
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
        except _WindowsApiFailure:
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
            self._require_expected_volume(expected_volume_fingerprint)
            self._validate_target(path)
            if path == self._scope._root:
                _fail("host_object_outside_scope")
            api = _WindowsApi()
            with opened_chain(api, path.parent) as chain:
                self._require_scope_binding(chain)
                parent = chain.components[-1].observation
                if parent.object_kind is not HostObjectKind.DIRECTORY:
                    _fail("host_object_kind_mismatch")
                self._require_leaf_absent(api, path)
                return MissingHostObjectObservationV1.create(
                    parent_identity_fingerprint=parent.object_identity_fingerprint,
                    volume_fingerprint=parent.volume_fingerprint,
                    normalized_name_fingerprint=_text_fingerprint(
                        expected_final_path(path)
                    ),
                    filesystem_name=parent.filesystem_name,
                )
        except RealHostPreflightError:
            raise
        except _WindowsApiFailure:
            _fail("host_object_unavailable")
        except Exception:
            _fail("internal_error")

    def _validate_target(self, path: Path) -> None:
        require_absolute_local_path(path)
        if path != self._scope._root and self._scope._root not in path.parents:
            _fail("host_object_outside_scope")

    def _require_scope_binding(self, chain: OpenedChain) -> None:
        root_path = self._scope._root_normalized_path.casefold()
        for index, component in enumerate(chain.components):
            if component.native.normalized_path.casefold() != root_path:
                continue
            if component.observation.object_identity_fingerprint != (
                self._scope._root_identity
            ):
                _fail("host_object_identity_changed")
            if any(
                item.observation.volume_fingerprint
                != self._scope._root_volume_fingerprint
                for item in chain.components[index:]
            ):
                _fail("host_volume_mismatch")
            return
        _fail("host_object_outside_scope")

    def _require_expected_volume(self, expected: object) -> None:
        if expected is None:
            return
        if (
            not is_fingerprint(expected)
            or expected != self._scope._root_volume_fingerprint
        ):
            _fail("host_volume_mismatch")

    @staticmethod
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
