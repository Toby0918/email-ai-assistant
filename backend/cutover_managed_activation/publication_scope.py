"""Held synthetic scope and target-parent window for one publication."""

from __future__ import annotations

from .canonical import fail
from .errors import ManagedActivationError
from .scope_models import _SyntheticActivationScope
from .scope_paths import MARKER_BYTES, identity, require_no_reparse_chain
from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)
from .windows_publication_io import WindowsCreateOnlyApi

_ROLE_FIELDS = {
    "runtime": (
        "runtime_target",
        "runtime_parent_fingerprint",
        True,
    ),
    "database": (
        "database_target",
        "database_parent_fingerprint",
        False,
    ),
    "artifact": (
        "crx_target",
        "artifact_parent_fingerprint",
        False,
    ),
    "config": (
        "config_target",
        "config_parent_fingerprint",
        False,
    ),
}
_COLLISION_CODES = {
    "runtime": "runtime_publication_failed",
    "database": "database_target_collision",
    "artifact": "crx_target_collision",
    "config": "config_target_collision",
}


class PublicationScopeWindow:
    """Keep root, marker, parent, and created target identities held."""

    __slots__ = (
        "_scope",
        "_role",
        "_read_api",
        "_create_api",
        "_handles",
        "_observed",
        "_target",
        "_directory",
        "_target_handle",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("PublicationScopeWindow requires open()")

    @classmethod
    def open(cls, *, scope: object, role: object):
        if (
            type(scope) is not _SyntheticActivationScope
            or type(role) is not str
            or role not in _ROLE_FIELDS
        ):
            fail("managed_activation_scope_invalid")
        window = object.__new__(cls)
        window._scope = scope
        window._role = role
        window._read_api = WindowsReadHandleApi()
        window._create_api = WindowsCreateOnlyApi()
        window._handles = []
        window._observed = {}
        window._target_handle = None
        window._open_bound_handles()
        return window

    def _open_bound_handles(self) -> None:
        scenario = self._scope.review.scenario
        target_field, parent_field, directory = _ROLE_FIELDS[self._role]
        self._target = getattr(scenario, target_field)
        self._directory = directory
        paths = {
            "root": scenario.root,
            "marker": scenario.marker,
            "parent": self._target.parent,
        }
        try:
            for name, path in paths.items():
                handle = self._read_api.open_existing(
                    path, deny_write=name == "marker"
                )
                self._handles.append(handle)
                self._observed[name] = self._read_api.observe(handle)
            self._validate_bound(parent_field)
        except Exception:
            self._close_all(active_error=True)
            raise

    def _validate_bound(self, parent_field: str) -> None:
        review = self._scope.review
        root = self._observed["root"]
        marker = self._observed["marker"]
        parent = self._observed["parent"]
        expected_parent = getattr(review, parent_field)
        if (
            not _directory_observation(root)
            or _directory_observation(marker)
            or not _directory_observation(parent)
            or review.scenario.marker.read_bytes() != MARKER_BYTES
            or identity(review.scenario.root) != review.root_identity
            or identity(review.scenario.marker) != review.marker_identity
        ):
            fail("managed_activation_scope_drift")
        require_no_reparse_chain(
            self._target.parent, review.scenario.root
        )
        if identity(self._target.parent) != expected_parent:
            fail("managed_activation_scope_drift")
        _require_absent(
            self._target, code=_COLLISION_CODES[self._role]
        )
        self._require_held_scope()

    def create_target(self) -> int:
        if self._target_handle is not None:
            fail("managed_activation_target_collision")
        parent_handle = self._handles[2]
        try:
            if self._directory:
                handle = self._create_api.create_directory(
                    parent_handle, self._target.name
                )
            else:
                handle = self._create_api.create_file(
                    parent_handle, self._target.name
                )
        except ManagedActivationError as error:
            if str(error) == "managed_activation_target_collision":
                fail(_COLLISION_CODES[self._role])
            raise
        self._target_handle = handle
        self._handles.append(handle)
        return handle

    def write_all(self, payload: bytes) -> None:
        self._require_target()
        self._create_api.write_all(self._target_handle, payload)

    def copy_from_path(self, source) -> None:
        self._require_target()
        self._create_api.copy_from_path(self._target_handle, source)

    def flush(self) -> None:
        self._require_target()
        self._create_api.flush(self._target_handle)

    def read_all(self) -> bytes:
        self._require_target()
        return self._create_api.read_all(self._target_handle)

    def _require_target(self) -> None:
        if self._target_handle is None:
            fail("managed_activation_target_invalid")

    def verify_target(self) -> None:
        if self._target_handle is None:
            fail("managed_activation_target_invalid")
        observed = self._read_api.observe(self._target_handle)
        is_directory = bool(
            observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        )
        if (
            is_directory != self._directory
            or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        ):
            fail("managed_activation_target_invalid")
        self._read_api.require_stable(
            self._target_handle, observed, self._target
        )
        self._require_held_scope()

    def _require_held_scope(self) -> None:
        scenario = self._scope.review.scenario
        for index, name in enumerate(("root", "marker", "parent")):
            self._read_api.require_stable(
                self._handles[index],
                self._observed[name],
                (
                    scenario.root
                    if name == "root"
                    else scenario.marker
                    if name == "marker"
                    else self._target.parent
                ),
            )

    def close(self, *, active_error: bool) -> None:
        self._close_all(active_error=active_error)

    def _close_all(self, *, active_error: bool) -> None:
        failed = False
        while self._handles:
            handle = self._handles.pop()
            try:
                self._read_api.close(handle)
            except Exception:
                failed = True
        if failed and not active_error:
            fail("managed_activation_scope_close_failed")


def _directory_observation(value) -> bool:
    return (
        bool(value.file_attributes & FILE_ATTRIBUTE_DIRECTORY)
        and not value.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        and value.filesystem_name == "NTFS"
        and value.fixed_drive
    )


def _require_absent(path, *, code: str) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        fail("managed_activation_scope_drift")
    fail(code)
