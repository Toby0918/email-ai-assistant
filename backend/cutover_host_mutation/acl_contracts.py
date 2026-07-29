"""Portable content-free ACL policy and observation contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import (
    canonical_json,
    exact_mapping,
    fingerprint,
    is_fingerprint,
)
from .errors import CutoverHostMutationError
from .roles import AclRole


_ACL_ERROR = "acl_contract_invalid"
_DESCRIPTOR_INPUT_KEYS = (
    "role",
    "object_identity_fingerprint",
    "canonical_sddl_fingerprint",
    "binary_descriptor_fingerprint",
    "owner_fingerprint",
    "group_fingerprint",
    "dacl_fingerprint",
    "dacl_protected",
    "ace_count",
    "inherited_ace_count",
    "complete",
    "content_observed",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class AclCompatibilityPolicyV1:
    schema_version: int
    principal_roles: tuple[str, ...]
    dacl_protected: bool
    recursive_rewrite: bool
    allowed_descriptor_fingerprints: tuple[str, ...] = field(repr=False)
    maximum_objects: int
    policy_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated ACL compatibility policy required")

    @classmethod
    def create(
        cls,
        *,
        allowed_descriptor_fingerprints: tuple[str, ...],
        maximum_objects: int,
    ) -> AclCompatibilityPolicyV1:
        allowed = _allowed_descriptors(allowed_descriptor_fingerprints)
        if (
            type(maximum_objects) is not int
            or not 1 <= maximum_objects <= 100_000
        ):
            _invalid()
        body = {
            "allowed_descriptor_fingerprints": list(allowed),
            "dacl_protected": True,
            "maximum_objects": maximum_objects,
            "principal_roles": [
                "builtin_administrators",
                "operator",
                "system",
            ],
            "recursive_rewrite": False,
            "schema_version": 1,
        }
        value = object.__new__(cls)
        object.__setattr__(value, "schema_version", 1)
        object.__setattr__(value, "principal_roles", tuple(body["principal_roles"]))
        object.__setattr__(value, "dacl_protected", True)
        object.__setattr__(value, "recursive_rewrite", False)
        object.__setattr__(value, "allowed_descriptor_fingerprints", allowed)
        object.__setattr__(value, "maximum_objects", maximum_objects)
        object.__setattr__(
            value,
            "policy_fingerprint",
            fingerprint("acl-compatibility-policy-v1", body, code=_ACL_ERROR),
        )
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            "allowed_descriptor_fingerprints": list(
                self.allowed_descriptor_fingerprints
            ),
            "dacl_protected": self.dacl_protected,
            "maximum_objects": self.maximum_objects,
            "policy_fingerprint": self.policy_fingerprint,
            "principal_roles": list(self.principal_roles),
            "recursive_rewrite": self.recursive_rewrite,
            "schema_version": self.schema_version,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=_ACL_ERROR)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class AclDescriptorObservationV1:
    schema_version: int
    role: AclRole
    object_identity_fingerprint: str = field(repr=False)
    canonical_sddl_fingerprint: str = field(repr=False)
    binary_descriptor_fingerprint: str = field(repr=False)
    owner_fingerprint: str = field(repr=False)
    group_fingerprint: str = field(repr=False)
    dacl_fingerprint: str = field(repr=False)
    dacl_protected: bool
    ace_count: int
    inherited_ace_count: int
    complete: bool
    content_observed: bool
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated ACL descriptor observation required")

    @classmethod
    def create(cls, **values: object) -> AclDescriptorObservationV1:
        source = exact_mapping(
            values,
            _DESCRIPTOR_INPUT_KEYS,
            code=_ACL_ERROR,
        )
        _validate_descriptor(source)
        body = {
            key: (
                source[key].value
                if key == "role"
                else source[key]
            )
            for key in _DESCRIPTOR_INPUT_KEYS
        }
        value = object.__new__(cls)
        object.__setattr__(value, "schema_version", 1)
        for key in _DESCRIPTOR_INPUT_KEYS:
            object.__setattr__(value, key, source[key])
        object.__setattr__(
            value,
            "observation_fingerprint",
            fingerprint("acl-descriptor-observation-v1", body, code=_ACL_ERROR),
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class AclCompatibilityObservationV1:
    schema_version: int
    policy_fingerprint: str = field(repr=False)
    source_root_identity_fingerprint: str = field(repr=False)
    inventory_fingerprint: str = field(repr=False)
    descriptors_observed: int
    complete: bool
    content_observed: bool
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated ACL compatibility observation required")

    @classmethod
    def create(
        cls,
        *,
        policy_fingerprint: str,
        source_root_identity_fingerprint: str,
        inventory_fingerprint: str,
        descriptors_observed: int,
        complete: bool,
        content_observed: bool,
    ) -> AclCompatibilityObservationV1:
        if (
            not is_fingerprint(policy_fingerprint)
            or not is_fingerprint(source_root_identity_fingerprint)
            or not is_fingerprint(inventory_fingerprint)
            or type(descriptors_observed) is not int
            or not 1 <= descriptors_observed <= 100_000
            or complete is not True
            or content_observed is not False
        ):
            _invalid()
        body = {
            "complete": True,
            "content_observed": False,
            "descriptors_observed": descriptors_observed,
            "inventory_fingerprint": inventory_fingerprint,
            "policy_fingerprint": policy_fingerprint,
            "schema_version": 1,
            "source_root_identity_fingerprint": (
                source_root_identity_fingerprint
            ),
        }
        value = object.__new__(cls)
        for key, item in body.items():
            object.__setattr__(value, key, item)
        object.__setattr__(
            value,
            "observation_fingerprint",
            fingerprint(
                "acl-compatibility-observation-v1",
                body,
                code=_ACL_ERROR,
            ),
        )
        return value


def _allowed_descriptors(value: object) -> tuple[str, ...]:
    if type(value) is not tuple or not value:
        _invalid()
    if (
        any(not is_fingerprint(item) for item in value)
        or len(set(value)) != len(value)
    ):
        _invalid()
    return tuple(sorted(value))


def _validate_descriptor(source: dict[str, object]) -> None:
    fingerprints = _DESCRIPTOR_INPUT_KEYS[1:7]
    ace_count = source["ace_count"]
    inherited = source["inherited_ace_count"]
    if (
        type(source["role"]) is not AclRole
        or any(not is_fingerprint(source[key]) for key in fingerprints)
        or type(source["dacl_protected"]) is not bool
        or type(ace_count) is not int
        or type(inherited) is not int
        or not 0 <= inherited <= ace_count <= 4096
        or source["complete"] is not True
        or source["content_observed"] is not False
    ):
        _invalid()


def _invalid() -> None:
    raise CutoverHostMutationError(_ACL_ERROR)
