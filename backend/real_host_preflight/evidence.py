"""Portable fixed-role evidence used by read-only preflight callbacks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .canonical import fingerprint, is_fingerprint


class HostCheckKind(str, Enum):
    """The non-filesystem checks repeated at each topology gate."""

    GIT = "git"
    ACL = "acl"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class OpaqueHostCheckV1:
    """One complete content-free Git or ACL observation."""

    schema_version: int
    kind: HostCheckKind
    fingerprint: str
    complete: bool
    content_observed: bool
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated host check construction required")

    @classmethod
    def create(
        cls,
        *,
        kind: HostCheckKind,
        fingerprint: str,
        complete: bool,
        content_observed: bool,
    ) -> OpaqueHostCheckV1:
        if (
            type(kind) is not HostCheckKind
            or not is_fingerprint(fingerprint)
            or type(complete) is not bool
            or complete is not True
            or type(content_observed) is not bool
            or content_observed is not False
        ):
            raise ValueError("REAL_HOST_CHECK_INVALID")
        body = {
            "complete": complete,
            "content_observed": content_observed,
            "fingerprint": fingerprint,
            "kind": kind.value,
            "schema_version": 1,
        }
        return _construct(
            cls,
            {
                "schema_version": 1,
                "kind": kind,
                "fingerprint": fingerprint,
                "complete": complete,
                "content_observed": content_observed,
                "observation_fingerprint": fingerprint_value(body),
            },
        )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class VolumeObservationV1:
    """One complete local fixed-NTFS volume observation."""

    schema_version: int
    volume_fingerprint: str
    filesystem_name: str
    drive_type: str
    complete: bool
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated volume observation construction required")

    @classmethod
    def create(
        cls,
        *,
        volume_fingerprint: str,
        filesystem_name: str,
        drive_type: str,
        complete: bool,
    ) -> VolumeObservationV1:
        if (
            not is_fingerprint(volume_fingerprint)
            or type(filesystem_name) is not str
            or filesystem_name != "NTFS"
            or type(drive_type) is not str
            or drive_type != "fixed"
            or type(complete) is not bool
            or complete is not True
        ):
            raise ValueError("REAL_HOST_VOLUME_INVALID")
        body = {
            "complete": complete,
            "drive_type": drive_type,
            "filesystem_name": filesystem_name,
            "schema_version": 1,
            "volume_fingerprint": volume_fingerprint,
        }
        return _construct(
            cls,
            {
                "schema_version": 1,
                "volume_fingerprint": volume_fingerprint,
                "filesystem_name": filesystem_name,
                "drive_type": drive_type,
                "complete": complete,
                "observation_fingerprint": fingerprint_value(body),
            },
        )


def fingerprint_value(body: dict[str, object]) -> str:
    return fingerprint("real-host-evidence-v1", body)


def _construct(cls, values: dict[str, object]):
    value = object.__new__(cls)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value
