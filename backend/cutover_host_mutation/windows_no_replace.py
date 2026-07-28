"""Handle-relative, same-identity, no-replace Windows publication."""

from __future__ import annotations

import threading
from backend.real_host_preflight.windows_paths import expected_final_path

from .errors import CutoverHostMutationError
from .filesystem_contracts import (
    FilesystemMutationExpectationV1,
    FilesystemMutationObservationV1,
)
from .filesystem_state import (
    NoReplacePrimitiveState,
    no_replace_primitive_state,
)
from .journal_intent import consumed_filesystem_intent
from .roles import FilesystemMutationKind
from .windows_filesystem_common import (
    close_handles,
    fail,
    map_native_failure,
    observe_existing,
    open_bound_scope,
    require_absent,
)
from .windows_handles import (
    DELETE_ACCESS,
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
    _NativeWindowsFailure,
)


class _NoReplacePrimitive:
    __slots__ = ("__weakref__",)
    _kind: FilesystemMutationKind

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("no-replace primitive requires validated construction")

    @property
    def expectation(self) -> FilesystemMutationExpectationV1:
        return _state(self).expectation

    def _mutate(self, *, intent, durable_permit):
        state = _state(self)
        api = WindowsHandleApi()
        handles: list[int] = []
        try:
            root_handle, marker_handle = open_bound_scope(
                api,
                root=state.root,
                marker=state.marker,
                root_identity=state.root_identity,
                marker_identity=state.marker_identity,
            )
            handles.extend((root_handle, marker_handle))
            source_handle, parent_handle, source, parent = _open_handles(
                api, state
            )
            handles.extend((source_handle, parent_handle))
            target = _effect(
                api, state, source_handle, parent_handle,
                source, parent, intent, durable_permit,
            )
            _require_held_scope(
                api, state, root_handle, marker_handle
            )
            return _observation(self._kind, state, target, intent)
        except CutoverHostMutationError:
            raise
        except _NativeWindowsFailure as error:
            map_native_failure(error)
        except Exception:
            fail("internal_error")
        finally:
            close_handles(api, *reversed(handles))


class CreateOnlyFilePublicationPrimitive(_NoReplacePrimitive):
    _kind = FilesystemMutationKind.PUBLISH_FILE

    def publish_file(self, *, intent, durable_permit):
        return self._mutate(intent=intent, durable_permit=durable_permit)


class SameIdentityMovePrimitive(_NoReplacePrimitive):
    _kind = FilesystemMutationKind.MOVE_OBJECT

    def move_object(self, *, intent, durable_permit):
        return self._mutate(intent=intent, durable_permit=durable_permit)


def _require_held_scope(api, state, root_handle, marker_handle) -> None:
    root = api.observe(root_handle)
    marker = api.observe(marker_handle)
    if (
        root.object_identity_fingerprint != state.root_identity
        or marker.object_identity_fingerprint != state.marker_identity
    ):
        fail("filesystem_identity_changed")
    api.require_stable(root_handle, root, state.root)
    api.require_stable(marker_handle, marker, state.marker)


def _open_handles(api, state):
    source_handle = api.open_existing(
        state.source,
        access=DELETE_ACCESS | FILE_READ_ATTRIBUTES,
        share_delete=True,
    )
    parent_handle = None
    try:
        parent_handle = api.open_existing(
            state.target_parent,
            access=FILE_READ_ATTRIBUTES,
        )
        source = api.observe(source_handle)
        parent = api.observe(parent_handle)
        _validate_opened(
            api, state, source_handle, parent_handle, source, parent
        )
        return source_handle, parent_handle, source, parent
    except Exception:
        if parent_handle is None:
            close_handles(api, source_handle)
        else:
            close_handles(api, parent_handle, source_handle)
        raise


def _validate_opened(api, state, source_handle, parent_handle, source, parent):
    if (
        source.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or parent.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
    ):
        fail("filesystem_reparse_rejected")
    if (
        source.object_identity_fingerprint != state.source_identity
        or parent.object_identity_fingerprint != state.parent_identity
        or source.volume_fingerprint != state.volume_fingerprint
        or parent.volume_fingerprint != state.volume_fingerprint
    ):
        fail("filesystem_identity_changed")
    api.require_stable(source_handle, source, state.source)
    api.require_stable(parent_handle, parent, state.target_parent)


def _effect(api, state, sh, ph, source, parent, intent, permit):
    require_absent(api, state.target)
    with consumed_filesystem_intent(
        intent=intent, durable_permit=permit, expectation=state.expectation
    ):
        api.require_stable(sh, source, state.source)
        api.require_stable(ph, parent, state.target_parent)
        _run_race_barrier(state.target_race_barrier)
        require_absent(api, state.target)
        api.rename_no_replace(sh, ph, state.target.name)
        return _observe_relocated(api, state, sh, ph, source, parent)


def _run_race_barrier(barrier) -> None:
    if barrier is None:
        return
    try:
        barrier.wait(timeout=5)
        barrier.wait(timeout=5)
    except threading.BrokenBarrierError:
        fail("filesystem_scope_invalid")


def _observe_relocated(api, state, sh, ph, source, parent):
    api.require_stable(ph, parent, state.target_parent)
    moved = api.observe(sh)
    target = observe_existing(api, state.target)
    if not _same_relocated_object(state, source, moved, target):
        fail("filesystem_identity_changed")
    if moved.normalized_path.casefold() != expected_final_path(
        state.target
    ).casefold():
        fail("filesystem_identity_changed")
    require_absent(api, state.source)
    api.require_stable(ph, parent, state.target_parent)
    return target


def _same_relocated_object(state, source, moved, target) -> bool:
    return (
        moved.object_identity_fingerprint == state.source_identity
        and target.object_identity_fingerprint == state.source_identity
        and target.volume_fingerprint == state.volume_fingerprint
        and moved.volume_fingerprint == state.volume_fingerprint
        and moved.file_attributes == source.file_attributes
        and moved.reparse_tag == 0
    )


def _observation(kind, state, target, intent):
    return FilesystemMutationObservationV1.create(
        kind=kind,
        journal_intent_fingerprint=intent.record_hash,
        journal_effect_fingerprint=state.expectation.expected_after_fingerprint,
        source_identity_fingerprint=state.source_identity,
        target_identity_fingerprint=target.object_identity_fingerprint,
        parent_identity_fingerprint=state.parent_identity,
        volume_fingerprint=state.volume_fingerprint,
        same_identity=True,
        no_replace=True,
        reparse_free=True,
    )


def _state(primitive) -> NoReplacePrimitiveState:
    try:
        return no_replace_primitive_state(primitive)
    except LookupError:
        fail("filesystem_authorization_rejected")
