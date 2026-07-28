"""Validated test-sandbox construction for no-replace primitives."""

from __future__ import annotations

import threading
from pathlib import Path

from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .filesystem_contracts import FilesystemMutationExpectationV1
from .filesystem_state import (
    NoReplacePrimitiveState,
    register_no_replace_primitive,
)
from .roles import FilesystemMutationKind
from .windows_filesystem_common import (
    authorization_fingerprint,
    binding_target_name,
    fail,
    observe_existing,
    validate_scope,
)
from .windows_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    WindowsHandleApi,
)
from .windows_no_replace import (
    CreateOnlyFilePublicationPrimitive,
    SameIdentityMovePrimitive,
)


def _create_test_file_publication_primitive(**values):
    return _create_test_no_replace_primitive(
        primitive_type=CreateOnlyFilePublicationPrimitive,
        kind=FilesystemMutationKind.PUBLISH_FILE,
        **values,
    )


def _create_test_move_primitive(**values):
    return _create_test_no_replace_primitive(
        primitive_type=SameIdentityMovePrimitive,
        kind=FilesystemMutationKind.MOVE_OBJECT,
        **values,
    )


def _create_test_no_replace_primitive(
    *,
    primitive_type,
    kind,
    root,
    marker,
    authorization,
    profile,
    source,
    target_parent,
    target,
    observed_at_epoch,
    _source_volume_override=None,
    _target_race_barrier=None,
):
    _validate_factory(
        root, marker, authorization, profile, source, target_parent,
        target, observed_at_epoch, _target_race_barrier,
    )
    try:
        state = _build_state(
            kind, root, marker, authorization, profile, source,
            target_parent, target, _source_volume_override,
            _target_race_barrier,
        )
        primitive = object.__new__(primitive_type)
        register_no_replace_primitive(primitive, state)
        return primitive
    except CutoverHostMutationError:
        raise
    except Exception:
        fail("filesystem_scope_invalid")


def _validate_factory(
    root, marker, authorization, profile, source, parent,
    target, observed_at, barrier,
) -> None:
    validate_scope(
        root=root, marker=marker, authorization=authorization,
        profile=profile, parent=parent, target=target,
        observed_at_epoch=observed_at,
    )
    if (
        type(source) is not type(Path())
        or root not in source.parents
        or source == marker
        or source == target
        or (
            barrier is not None
            and type(barrier) is not threading.Barrier
        )
    ):
        fail("filesystem_authorization_rejected")


def _build_state(
    kind, root, marker, authorization, profile, source,
    parent, target, source_volume_override, barrier,
) -> NoReplacePrimitiveState:
    api = WindowsHandleApi()
    values = tuple(
        observe_existing(api, path)
        for path in (root, marker, source, parent)
    )
    _validate_values(kind, values, source_volume_override)
    auth = authorization_fingerprint(authorization)
    body = _binding_body(kind, profile, values[2], values[3], target, auth)
    return _state_value(
        root, marker, source, parent, target, profile, auth,
        *values, _expectation(kind, body), barrier,
    )


def _validate_values(kind, values, override) -> None:
    root, _marker, source, parent = values
    source_volume = (
        override if override is not None else source.volume_fingerprint
    )
    if (
        source_volume != parent.volume_fingerprint
        or root.volume_fingerprint != parent.volume_fingerprint
    ):
        fail("filesystem_volume_mismatch")
    if (
        kind is FilesystemMutationKind.PUBLISH_FILE
        and source.file_attributes & FILE_ATTRIBUTE_DIRECTORY
    ):
        fail("filesystem_authorization_rejected")


def _binding_body(kind, profile, source, parent, target, auth):
    return {
        "authorization_fingerprint": auth,
        "kind": kind.value,
        "parent_identity_fingerprint": parent.object_identity_fingerprint,
        "profile_fingerprint": profile.profile_fingerprint,
        "source_identity_fingerprint": source.object_identity_fingerprint,
        "target_name_fingerprint": binding_target_name(target),
        "volume_fingerprint": parent.volume_fingerprint,
    }


def _expectation(kind, body):
    binding = fingerprint(
        "filesystem-mutation-binding-v1", body,
        code="filesystem_contract_invalid",
    )
    return FilesystemMutationExpectationV1.create(
        kind=kind,
        binding_fingerprint=binding,
        before_fingerprint=fingerprint(
            "no-replace-source-present-target-absent-v1", body,
            code="filesystem_contract_invalid",
        ),
        expected_after_fingerprint=fingerprint(
            "no-replace-source-absent-target-present-v1", body,
            code="filesystem_contract_invalid",
        ),
    )


def _state_value(
    root, marker, source, parent, target, profile, auth,
    root_value, marker_value, source_value, parent_value,
    expectation, barrier,
):
    return NoReplacePrimitiveState(
        root, marker, source, parent, target,
        profile.profile_fingerprint, auth,
        root_value.object_identity_fingerprint,
        marker_value.object_identity_fingerprint,
        source_value.object_identity_fingerprint,
        parent_value.object_identity_fingerprint,
        parent_value.volume_fingerprint, expectation, barrier,
    )
