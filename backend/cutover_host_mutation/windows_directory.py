"""Journal-gated create-only Windows directory primitive."""

from __future__ import annotations

import threading

from .errors import CutoverHostMutationError
from .filesystem_contracts import (
    FilesystemMutationExpectationV1,
    FilesystemMutationObservationV1,
)
from .filesystem_state import (
    DirectoryPrimitiveState,
    NewDirectoryClaim,
    directory_primitive_state,
    register_new_directory,
)
from .journal_intent import consumed_filesystem_intent
from .roles import FilesystemMutationKind
from .windows_filesystem_common import (
    ZERO_FINGERPRINT,
    close_handles,
    fail,
    map_native_failure,
    open_bound_scope,
    require_absent,
)
from .windows_construction_acl import guarded_descriptor
from .windows_directory_native import create_directory_relative
from .windows_directory_resources import GuardedDirectoryHandles
from .windows_handles import (
    FILE_ATTRIBUTE_REPARSE_POINT,
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
    _NativeWindowsFailure,
)

_FILE_TRAVERSE = 0x00000020
_FILE_ADD_SUBDIRECTORY = 0x00000004


class CreateOnlyDirectoryPrimitive:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("directory primitive requires validated construction")

    @property
    def expectation(self) -> FilesystemMutationExpectationV1:
        return _state(self).expectation

    def create_directory(
        self,
        *,
        intent: object,
        durable_permit: object,
    ) -> FilesystemMutationObservationV1:
        state = _state(self)
        api = WindowsHandleApi()
        handles: list[int] = []
        transferred = False
        try:
            root_handle, marker_handle = open_bound_scope(
                api,
                root=state.root,
                marker=state.marker,
                root_identity=state.root_identity,
                marker_identity=state.marker_identity,
            )
            handles.extend((root_handle, marker_handle))
            parent_handle, parent = _open_parent(api, state)
            handles.append(parent_handle)
            target_handle, target = _effect(
                api, state, parent_handle, parent, intent, durable_permit
            )
            handles.append(target_handle)
            observation = _observation(state, target, intent)
            resource = _guarded_resource(api, state, handles)
            _register_claim(state, observation, target, resource)
            transferred = resource is not None
            return observation
        except CutoverHostMutationError:
            raise
        except _NativeWindowsFailure as error:
            map_native_failure(error)
        except Exception:
            fail("internal_error")
        finally:
            if not transferred:
                close_handles(api, *reversed(handles))


def _open_parent(api, state: DirectoryPrimitiveState):
    handle = api.open_existing(
        state.parent,
        access=(
            FILE_READ_ATTRIBUTES
            | _FILE_TRAVERSE
            | _FILE_ADD_SUBDIRECTORY
        ),
    )
    try:
        parent = api.observe(handle)
        if parent.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            fail("filesystem_reparse_rejected")
        if (
            parent.object_identity_fingerprint != state.parent_identity
            or parent.volume_fingerprint != state.volume_fingerprint
        ):
            fail("filesystem_identity_changed")
        api.require_stable(handle, parent, state.parent)
        return handle, parent
    except Exception:
        close_handles(api, handle)
        raise


def _effect(api, state, handle, parent, intent, permit):
    require_absent(api, state.target)
    descriptor = (
        guarded_descriptor(state.operator_fingerprint)
        if state.guarded_container
        else None
    )
    target_handle = None
    try:
        with consumed_filesystem_intent(
            intent=intent,
            durable_permit=permit,
            expectation=state.expectation,
        ):
            api.require_stable(handle, parent, state.parent)
            _run_target_race_barrier(state.target_race_barrier)
            target_handle = create_directory_relative(
                parent_handle=handle,
                target_name=state.target.name,
                security_descriptor=(
                    descriptor.pointer if descriptor is not None else None
                ),
                guarded=state.guarded_container,
            )
            target = api.observe(target_handle)
            _validate_target(api, state, target_handle, target)
            api.require_stable(handle, parent, state.parent)
            return target_handle, target
    except Exception:
        if target_handle is not None:
            close_handles(api, target_handle)
        raise


def _validate_target(api, state, handle, target) -> None:
    if target.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        fail("filesystem_reparse_rejected")
    if target.volume_fingerprint != state.volume_fingerprint:
        fail("filesystem_volume_mismatch")
    api.require_stable(handle, target, state.target)


def _run_target_race_barrier(barrier) -> None:
    if barrier is None:
        return
    try:
        barrier.wait(timeout=5)
        barrier.wait(timeout=5)
    except threading.BrokenBarrierError:
        fail("filesystem_scope_invalid")


def _observation(state, target, intent):
    return FilesystemMutationObservationV1.create(
        kind=FilesystemMutationKind.CREATE_DIRECTORY,
        journal_intent_fingerprint=intent.record_hash,
        journal_effect_fingerprint=(
            state.expectation.expected_after_fingerprint
        ),
        source_identity_fingerprint=ZERO_FINGERPRINT,
        target_identity_fingerprint=target.object_identity_fingerprint,
        parent_identity_fingerprint=state.parent_identity,
        volume_fingerprint=state.volume_fingerprint,
        same_identity=False,
        no_replace=True,
        reparse_free=True,
    )


def _guarded_resource(api, state, handles):
    if not state.guarded_container:
        return None
    return GuardedDirectoryHandles(
        api,
        root_handle=handles[0],
        marker_handle=handles[1],
        parent_handle=handles[2],
        target_handle=handles[3],
    )


def _register_claim(state, observation, target, resource) -> None:
    register_new_directory(
        observation,
        NewDirectoryClaim(
            target=state.target,
            object_identity=target.object_identity_fingerprint,
            parent_identity=state.parent_identity,
            volume_fingerprint=state.volume_fingerprint,
            profile_fingerprint=state.profile_fingerprint,
            guarded_container=state.guarded_container,
            resource=resource,
        ),
    )


def _state(primitive) -> DirectoryPrimitiveState:
    try:
        return directory_primitive_state(primitive)
    except LookupError:
        fail("filesystem_authorization_rejected")
