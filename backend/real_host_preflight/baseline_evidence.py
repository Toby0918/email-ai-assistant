"""Separate content-free role evidence for HostBaseline collection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .canonical import fingerprint, is_fingerprint
from .contracts import HostObjectObservationV1
from .evidence import VolumeObservationV1


class BaselineAclRole(str, Enum):
    SOURCE_ROOT = "source_root"
    PARENT = "parent"
    FINANCE = "finance"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class AclBaselineObservationV1:
    schema_version: int
    role: BaselineAclRole
    object_identity_fingerprint: str
    descriptor_fingerprint: str
    entry_count: int
    complete: bool
    content_observed: bool
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated ACL observation construction required")

    @classmethod
    def create(
        cls,
        *,
        role: BaselineAclRole,
        object_identity_fingerprint: str,
        descriptor_fingerprint: str,
        entry_count: int,
        complete: bool,
        content_observed: bool,
    ) -> AclBaselineObservationV1:
        if (
            type(role) is not BaselineAclRole
            or not is_fingerprint(object_identity_fingerprint)
            or not is_fingerprint(descriptor_fingerprint)
            or type(entry_count) is not int
            or not 0 <= entry_count <= 4096
            or type(complete) is not bool
            or complete is not True
            or type(content_observed) is not bool
            or content_observed is not False
        ):
            raise ValueError("REAL_HOST_BASELINE_INVALID")
        body = {
            "complete": complete,
            "content_observed": content_observed,
            "descriptor_fingerprint": descriptor_fingerprint,
            "entry_count": entry_count,
            "object_identity_fingerprint": object_identity_fingerprint,
            "role": role.value,
            "schema_version": 1,
        }
        return _construct(
            cls,
            {
                "schema_version": 1,
                "role": role,
                "object_identity_fingerprint": object_identity_fingerprint,
                "descriptor_fingerprint": descriptor_fingerprint,
                "entry_count": entry_count,
                "complete": complete,
                "content_observed": content_observed,
                "observation_fingerprint": fingerprint(
                    "baseline-acl-observation-v1", body
                ),
            },
        )


@dataclass(frozen=True, slots=True, init=False, repr=False)
class OperatorSidObservationV1:
    schema_version: int
    sid_fingerprint: str
    complete: bool
    content_observed: bool
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated SID observation construction required")

    @classmethod
    def create(
        cls,
        *,
        sid_fingerprint: str,
        complete: bool,
        content_observed: bool,
    ) -> OperatorSidObservationV1:
        if (
            not is_fingerprint(sid_fingerprint)
            or type(complete) is not bool
            or complete is not True
            or type(content_observed) is not bool
            or content_observed is not False
        ):
            raise ValueError("REAL_HOST_BASELINE_INVALID")
        body = {
            "complete": complete,
            "content_observed": content_observed,
            "schema_version": 1,
            "sid_fingerprint": sid_fingerprint,
        }
        return _construct(
            cls,
            {
                "schema_version": 1,
                "sid_fingerprint": sid_fingerprint,
                "complete": complete,
                "content_observed": content_observed,
                "observation_fingerprint": fingerprint(
                    "operator-sid-observation-v1", body
                ),
            },
        )


ObjectReader = Callable[[], HostObjectObservationV1]
VolumeReader = Callable[[], VolumeObservationV1]
OperatorSidReader = Callable[[], OperatorSidObservationV1]
AclReader = Callable[[], AclBaselineObservationV1]


@dataclass(frozen=True, slots=True, repr=False)
class RealHostBaselineCallbacks:
    source_root: ObjectReader
    parent: ObjectReader
    finance: ObjectReader
    volume: VolumeReader
    operator_sid: OperatorSidReader
    source_acl: AclReader
    parent_acl: AclReader
    finance_acl: AclReader


def _construct(cls, values: dict[str, object]):
    value = object.__new__(cls)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value
