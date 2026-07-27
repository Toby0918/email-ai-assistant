"""Portable content-free contracts for Issue #53 host observations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum


_FINGERPRINT_LENGTH = 64
_FILE_ID_LENGTH = 32
_DWORD_MAX = (1 << 32) - 1
_FILE_ATTRIBUTE_DIRECTORY = 0x10
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class HostObjectKind(str, Enum):
    """The complete object-type allowlist for controlled host objects."""

    FILE = "file"
    DIRECTORY = "directory"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class HostObjectObservationV1:
    """One opened-handle observation with no caller path or host name."""

    schema_version: int
    volume_fingerprint: str
    file_id_128: str
    object_kind: HostObjectKind
    parent_identity_fingerprint: str
    normalized_name_fingerprint: str
    filesystem_name: str
    file_attributes: int
    reparse_tag: int
    has_reparse_point: bool
    object_identity_fingerprint: str
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated host observation construction required")

    @classmethod
    def create(
        cls,
        *,
        volume_fingerprint: str,
        file_id_128: str,
        object_kind: HostObjectKind,
        parent_identity_fingerprint: str,
        normalized_name_fingerprint: str,
        filesystem_name: str,
        file_attributes: int,
        reparse_tag: int,
        has_reparse_point: bool,
    ) -> HostObjectObservationV1:
        values = _validated_object_values(
            volume_fingerprint=volume_fingerprint,
            file_id_128=file_id_128,
            object_kind=object_kind,
            parent_identity_fingerprint=parent_identity_fingerprint,
            normalized_name_fingerprint=normalized_name_fingerprint,
            filesystem_name=filesystem_name,
            file_attributes=file_attributes,
            reparse_tag=reparse_tag,
            has_reparse_point=has_reparse_point,
        )
        return _construct(cls, values)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MissingHostObjectObservationV1:
    """One exact leaf-absence observation bound to an opened parent."""

    schema_version: int
    parent_identity_fingerprint: str
    volume_fingerprint: str
    normalized_name_fingerprint: str
    filesystem_name: str
    present: bool
    observation_fingerprint: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated absence observation construction required")

    @classmethod
    def create(
        cls,
        *,
        parent_identity_fingerprint: str,
        volume_fingerprint: str,
        normalized_name_fingerprint: str,
        filesystem_name: str,
    ) -> MissingHostObjectObservationV1:
        """Validate and bind one content-free absence observation."""

        _require_fingerprint(parent_identity_fingerprint)
        _require_fingerprint(volume_fingerprint)
        _require_fingerprint(normalized_name_fingerprint)
        if type(filesystem_name) is not str or filesystem_name != "NTFS":
            raise ValueError("REAL_HOST_OBSERVATION_INVALID")
        body = {
            "filesystem_name": filesystem_name,
            "normalized_name_fingerprint": normalized_name_fingerprint,
            "parent_identity_fingerprint": parent_identity_fingerprint,
            "present": False,
            "schema_version": 1,
            "volume_fingerprint": volume_fingerprint,
        }
        return _construct(
            cls,
            {
                **body,
                "observation_fingerprint": _fingerprint(body),
            },
        )


def _require_fingerprint(value: object) -> None:
    _require_lower_hex(value, _FINGERPRINT_LENGTH)


def _require_lower_hex(value: object, length: int) -> None:
    if (
        type(value) is not str
        or len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("REAL_HOST_OBSERVATION_INVALID")


def _require_dword(value: object) -> None:
    if type(value) is not int or not 0 <= value <= _DWORD_MAX:
        raise ValueError("REAL_HOST_OBSERVATION_INVALID")


def _validate_object_inputs(
    volume: object,
    file_id: object,
    kind: object,
    parent: object,
    name: object,
    filesystem: object,
    attributes: object,
    reparse_tag: object,
    has_reparse: object,
) -> None:
    _require_fingerprint(volume)
    _require_lower_hex(file_id, _FILE_ID_LENGTH)
    _require_fingerprint(parent)
    _require_fingerprint(name)
    _require_dword(attributes)
    _require_dword(reparse_tag)
    if (
        type(kind) is not HostObjectKind
        or type(filesystem) is not str
        or filesystem != "NTFS"
        or type(has_reparse) is not bool
    ):
        raise ValueError("REAL_HOST_OBSERVATION_INVALID")
    _validate_attribute_relationships(
        kind,
        attributes,
        reparse_tag,
        has_reparse,
    )


def _validate_attribute_relationships(
    kind: HostObjectKind,
    attributes: int,
    reparse_tag: int,
    has_reparse: bool,
) -> None:
    directory_bit = bool(attributes & _FILE_ATTRIBUTE_DIRECTORY)
    reparse_bit = bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)
    if (
        directory_bit != (kind is HostObjectKind.DIRECTORY)
        or reparse_bit != has_reparse
        or (has_reparse and reparse_tag == 0)
        or (not has_reparse and reparse_tag != 0)
    ):
        raise ValueError("REAL_HOST_OBSERVATION_INVALID")


def _validated_object_values(**values: object) -> dict[str, object]:
    _validate_object_inputs(
        values["volume_fingerprint"],
        values["file_id_128"],
        values["object_kind"],
        values["parent_identity_fingerprint"],
        values["normalized_name_fingerprint"],
        values["filesystem_name"],
        values["file_attributes"],
        values["reparse_tag"],
        values["has_reparse_point"],
    )
    identity, observation = _object_fingerprints(**values)
    return _object_values(
        values["volume_fingerprint"],
        values["file_id_128"],
        values["object_kind"],
        values["parent_identity_fingerprint"],
        values["normalized_name_fingerprint"],
        values["filesystem_name"],
        values["file_attributes"],
        values["reparse_tag"],
        values["has_reparse_point"],
        identity,
        observation,
    )


def _object_fingerprints(**values: object) -> tuple[str, str]:
    identity = _fingerprint(
        {
            "file_id_128": values["file_id_128"],
            "object_kind": values["object_kind"].value,
            "volume_fingerprint": values["volume_fingerprint"],
        }
    )
    observation = _fingerprint(
        {
            "file_attributes": values["file_attributes"],
            "filesystem_name": values["filesystem_name"],
            "has_reparse_point": values["has_reparse_point"],
            "normalized_name_fingerprint": values[
                "normalized_name_fingerprint"
            ],
            "object_identity_fingerprint": identity,
            "parent_identity_fingerprint": values[
                "parent_identity_fingerprint"
            ],
            "reparse_tag": values["reparse_tag"],
            "schema_version": 1,
        }
    )
    return identity, observation


def _object_values(
    volume,
    file_id,
    kind,
    parent,
    name,
    filesystem,
    attributes,
    reparse_tag,
    has_reparse,
    identity,
    observation,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "volume_fingerprint": volume,
        "file_id_128": file_id,
        "object_kind": kind,
        "parent_identity_fingerprint": parent,
        "normalized_name_fingerprint": name,
        "filesystem_name": filesystem,
        "file_attributes": attributes,
        "reparse_tag": reparse_tag,
        "has_reparse_point": has_reparse,
        "object_identity_fingerprint": identity,
        "observation_fingerprint": observation,
    }


def _fingerprint(value: dict[str, object]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _construct(cls, values: dict[str, object]):
    value = object.__new__(cls)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value
