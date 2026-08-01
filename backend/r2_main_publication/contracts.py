"""Nominal content-free ACL readiness, projection, and receipt values."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import fingerprint, is_fingerprint


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ExpectedInheritedDaclProjectionV1:
    schema_version: int
    root_dacl_fingerprint: str = field(repr=False)
    directory_dacl_fingerprint: str = field(repr=False)
    file_dacl_fingerprint: str = field(repr=False)
    projection_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated DACL projection required")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class PreMoveMainAclReadinessObservationV1:
    schema_version: int
    source_root_identity_fingerprint: str = field(repr=False)
    inventory_fingerprint: str = field(repr=False)
    object_count: int
    observed_at_epoch: int = field(repr=False)
    expires_at_epoch: int = field(repr=False)
    double_stable: bool
    single_use: bool
    content_observed: bool
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated pre-move readiness required")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class PostMoveMainAclConformanceReceiptV1:
    schema_version: int
    status: str
    projection_fingerprint: str = field(repr=False)
    main_identity_fingerprint: str = field(repr=False)
    inventory_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    object_count: int
    owner_group_exact: bool
    dacl_whole_tree_exact: bool
    content_observed: bool
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated post-move receipt required")


def _projection(**values: object) -> ExpectedInheritedDaclProjectionV1:
    fingerprints = tuple(values.get(name) for name in _PROJECTION_FIELDS)
    if any(not is_fingerprint(item) for item in fingerprints):
        raise ValueError("main_acl_projection_invalid")
    body = {"schema_version": 1, **values}
    result = object.__new__(ExpectedInheritedDaclProjectionV1)
    _set(result, body)
    object.__setattr__(
        result,
        "projection_fingerprint",
        fingerprint("expected-inherited-dacl-projection-v1", body),
    )
    return result


def _readiness(**values: object) -> PreMoveMainAclReadinessObservationV1:
    if not _valid_readiness(values):
        raise ValueError("main_acl_readiness_invalid")
    body = {
        "schema_version": 1,
        **values,
        "double_stable": True,
        "single_use": True,
        "content_observed": False,
    }
    result = object.__new__(PreMoveMainAclReadinessObservationV1)
    _set(result, body)
    object.__setattr__(
        result,
        "observation_fingerprint",
        fingerprint("pre-move-main-acl-readiness-v1", body),
    )
    return result


def _receipt(**values: object) -> PostMoveMainAclConformanceReceiptV1:
    if not _valid_receipt(values):
        raise ValueError("main_acl_receipt_invalid")
    body = {
        "schema_version": 1,
        "status": "MAIN_PUBLISHED",
        **values,
        "owner_group_exact": True,
        "dacl_whole_tree_exact": True,
        "content_observed": False,
    }
    result = object.__new__(PostMoveMainAclConformanceReceiptV1)
    _set(result, body)
    object.__setattr__(
        result,
        "receipt_fingerprint",
        fingerprint("post-move-main-acl-conformance-v1", body),
    )
    return result


def _valid_readiness(values: dict[str, object]) -> bool:
    return (
        set(values) == set(_READINESS_FIELDS)
        and is_fingerprint(values["source_root_identity_fingerprint"])
        and is_fingerprint(values["inventory_fingerprint"])
        and type(values["object_count"]) is int
        and 1 <= values["object_count"] <= 100
        and type(values["observed_at_epoch"]) is int
        and type(values["expires_at_epoch"]) is int
        and 0 < values["expires_at_epoch"] - values["observed_at_epoch"] <= 30
    )


def _valid_receipt(values: dict[str, object]) -> bool:
    return (
        set(values) == set(_RECEIPT_FIELDS)
        and all(is_fingerprint(values[name]) for name in _RECEIPT_FP_FIELDS)
        and type(values["object_count"]) is int
        and 1 <= values["object_count"] <= 100
    )


def _set(target: object, values: dict[str, object]) -> None:
    for name, value in values.items():
        object.__setattr__(target, name, value)


_PROJECTION_FIELDS = (
    "root_dacl_fingerprint",
    "directory_dacl_fingerprint",
    "file_dacl_fingerprint",
)
_READINESS_FIELDS = (
    "source_root_identity_fingerprint",
    "inventory_fingerprint",
    "object_count",
    "observed_at_epoch",
    "expires_at_epoch",
)
_RECEIPT_FP_FIELDS = (
    "projection_fingerprint",
    "main_identity_fingerprint",
    "inventory_fingerprint",
    "journal_head_fingerprint",
)
_RECEIPT_FIELDS = (*_RECEIPT_FP_FIELDS, "object_count")
