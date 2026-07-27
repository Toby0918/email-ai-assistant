"""Exact reconstruction checks for portable content-free evidence."""

from __future__ import annotations

from .baseline_evidence import (
    AclBaselineObservationV1,
    OperatorSidObservationV1,
)
from .contracts import (
    HostObjectObservationV1,
    MissingHostObjectObservationV1,
)
from .evidence import OpaqueHostCheckV1, VolumeObservationV1


def valid_host_object(value: object) -> bool:
    if type(value) is not HostObjectObservationV1:
        return False
    try:
        rebuilt = HostObjectObservationV1.create(
            volume_fingerprint=value.volume_fingerprint,
            file_id_128=value.file_id_128,
            object_kind=value.object_kind,
            parent_identity_fingerprint=value.parent_identity_fingerprint,
            normalized_name_fingerprint=value.normalized_name_fingerprint,
            filesystem_name=value.filesystem_name,
            file_attributes=value.file_attributes,
            reparse_tag=value.reparse_tag,
            has_reparse_point=value.has_reparse_point,
        )
    except Exception:
        return False
    return value == rebuilt


def valid_missing_host_object(value: object) -> bool:
    if type(value) is not MissingHostObjectObservationV1:
        return False
    try:
        rebuilt = MissingHostObjectObservationV1.create(
            parent_identity_fingerprint=value.parent_identity_fingerprint,
            volume_fingerprint=value.volume_fingerprint,
            normalized_name_fingerprint=value.normalized_name_fingerprint,
            filesystem_name=value.filesystem_name,
        )
    except Exception:
        return False
    return value == rebuilt


def valid_opaque_check(value: object) -> bool:
    if type(value) is not OpaqueHostCheckV1:
        return False
    try:
        rebuilt = OpaqueHostCheckV1.create(
            kind=value.kind,
            fingerprint=value.fingerprint,
            complete=value.complete,
            content_observed=value.content_observed,
        )
    except Exception:
        return False
    return value == rebuilt


def valid_volume(value: object) -> bool:
    if type(value) is not VolumeObservationV1:
        return False
    try:
        rebuilt = VolumeObservationV1.create(
            volume_fingerprint=value.volume_fingerprint,
            filesystem_name=value.filesystem_name,
            drive_type=value.drive_type,
            complete=value.complete,
        )
    except Exception:
        return False
    return value == rebuilt


def valid_acl_baseline(value: object) -> bool:
    if type(value) is not AclBaselineObservationV1:
        return False
    try:
        rebuilt = AclBaselineObservationV1.create(
            role=value.role,
            object_identity_fingerprint=value.object_identity_fingerprint,
            descriptor_fingerprint=value.descriptor_fingerprint,
            entry_count=value.entry_count,
            complete=value.complete,
            content_observed=value.content_observed,
        )
    except Exception:
        return False
    return value == rebuilt


def valid_operator_sid(value: object) -> bool:
    if type(value) is not OperatorSidObservationV1:
        return False
    try:
        rebuilt = OperatorSidObservationV1.create(
            sid_fingerprint=value.sid_fingerprint,
            complete=value.complete,
            content_observed=value.content_observed,
        )
    except Exception:
        return False
    return value == rebuilt
