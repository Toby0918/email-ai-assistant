"""Content-free observations for exact Git-object byte verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import is_fingerprint
from ._git_byte_validation_v2 import (
    MODES,
    GitByteStateError,
    blob_oid,
    is_oid,
    safe_relative,
    sha256,
    valid_worktree,
)


class GitCommonStateRoleV2(str, Enum):
    OBJECT_DATABASE = "object_database"
    CONFIG = "config"
    PACKED_REFS = "packed_refs"
    REFS_NAMESPACE = "refs_namespace"
    SHALLOW_REPLACE_NAMESPACE = "shallow_replace_namespace"


@dataclass(frozen=True, slots=True, repr=False)
class SelectedGitByteV2:
    path_fingerprint: str = field(repr=False)
    mode: str
    blob_oid: str = field(repr=False)
    byte_sha256: str = field(repr=False)
    byte_count: int
    index_verified: bool
    checkout_verified: bool

    @classmethod
    def create(cls, **values):
        expected = {
            "relative",
            "mode",
            "blob_oid",
            "git_object_bytes",
            "checkout_bytes",
            "index_oid",
            "index_mode",
            "index_stage",
            "assume_unchanged",
            "skip_worktree",
        }
        try:
            if set(values) != expected:
                raise GitByteStateError()
            relative = values["relative"]
            mode = values["mode"]
            oid = values["blob_oid"]
            source = values["git_object_bytes"]
            checkout = values["checkout_bytes"]
            if (
                not safe_relative(relative)
                or mode not in MODES
                or not is_oid(oid)
                or type(source) is not bytes
                or not 0 <= len(source) <= 67_108_864
                or type(checkout) is not bytes
                or source != checkout
                or blob_oid(source) != oid
                or values["index_oid"] != oid
                or values["index_mode"] != mode
                or values["index_stage"] != 0
                or values["assume_unchanged"] is not False
                or values["skip_worktree"] is not False
            ):
                raise GitByteStateError()
            return cls(
                sha256(relative.encode("utf-8")),
                mode,
                oid,
                sha256(source),
                len(source),
                True,
                True,
            )
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None

    def to_mapping(self):
        return {
            "path_fingerprint": self.path_fingerprint,
            "mode": self.mode,
            "blob_oid": self.blob_oid,
            "byte_sha256": self.byte_sha256,
            "byte_count": self.byte_count,
            "index_verified": self.index_verified,
            "checkout_verified": self.checkout_verified,
        }

    @classmethod
    def from_mapping(cls, value):
        expected = {
            "path_fingerprint",
            "mode",
            "blob_oid",
            "byte_sha256",
            "byte_count",
            "index_verified",
            "checkout_verified",
        }
        try:
            if (
                type(value) is not dict
                or set(value) != expected
                or not is_fingerprint(value["path_fingerprint"])
                or value["mode"] not in MODES
                or not is_oid(value["blob_oid"])
                or not is_fingerprint(value["byte_sha256"])
                or type(value["byte_count"]) is not int
                or not 0 <= value["byte_count"] <= 67_108_864
                or value["index_verified"] is not True
                or value["checkout_verified"] is not True
            ):
                raise GitByteStateError()
            return cls(**value)
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None


@dataclass(frozen=True, slots=True, repr=False)
class GitCommonStateV2:
    role: GitCommonStateRoleV2
    byte_sha256: str = field(repr=False)
    byte_count: int

    @classmethod
    def create(cls, *, role, content_bytes):
        if (
            type(role) is not GitCommonStateRoleV2
            or type(content_bytes) is not bytes
            or not 0 <= len(content_bytes) <= 67_108_864
        ):
            raise GitByteStateError()
        return cls(role, sha256(content_bytes), len(content_bytes))

    def to_mapping(self):
        return {
            "role": self.role.value,
            "byte_sha256": self.byte_sha256,
            "byte_count": self.byte_count,
        }

    @classmethod
    def from_mapping(cls, value):
        try:
            if type(value) is not dict or set(value) != {
                "role",
                "byte_sha256",
                "byte_count",
            }:
                raise GitByteStateError()
            result = cls(
                GitCommonStateRoleV2(value["role"]),
                value["byte_sha256"],
                value["byte_count"],
            )
            if (
                not is_fingerprint(result.byte_sha256)
                or type(result.byte_count) is not int
                or not 0 <= result.byte_count <= 67_108_864
            ):
                raise GitByteStateError()
            return result
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None


@dataclass(frozen=True, slots=True, repr=False)
class GitWorktreeStateV2:
    role: str
    placement: str
    state_kind: str
    ref_fingerprint: str = field(repr=False)
    commit_oid: str = field(repr=False)
    physical_identity_fingerprint: str = field(repr=False)
    admin_identity_fingerprint: str = field(repr=False)
    admin_content_sha256: str = field(repr=False)
    admin_byte_count: int
    checkout_sha256: str = field(repr=False)
    checkout_byte_count: int

    @classmethod
    def create(cls, **values):
        expected = {
            "role",
            "placement",
            "state_kind",
            "branch_ref",
            "commit_oid",
            "physical_identity_fingerprint",
            "admin_identity_fingerprint",
            "admin_content_bytes",
            "checkout_bytes",
        }
        try:
            if set(values) != expected:
                raise GitByteStateError()
            reference = values["branch_ref"]
            admin = values["admin_content_bytes"]
            checkout = values["checkout_bytes"]
            if (
                type(values["role"]) is not str
                or values["placement"] not in {"embedded", "external"}
                or values["state_kind"] not in {"original", "reconstructed"}
                or type(reference) is not str
                or not reference.startswith("refs/heads/")
                or not is_oid(values["commit_oid"])
                or not is_fingerprint(values["physical_identity_fingerprint"])
                or not is_fingerprint(values["admin_identity_fingerprint"])
                or type(admin) is not bytes
                or not 0 <= len(admin) <= 16_777_216
                or type(checkout) is not bytes
                or not 0 <= len(checkout) <= 67_108_864
            ):
                raise GitByteStateError()
            return cls(
                values["role"],
                values["placement"],
                values["state_kind"],
                sha256(reference.encode("utf-8")),
                values["commit_oid"],
                values["physical_identity_fingerprint"],
                values["admin_identity_fingerprint"],
                sha256(admin),
                len(admin),
                sha256(checkout),
                len(checkout),
            )
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None

    def to_mapping(self):
        return {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
        } | {"ref_fingerprint": self.ref_fingerprint}

    @classmethod
    def from_mapping(cls, value):
        try:
            names = set(cls.__dataclass_fields__)
            if type(value) is not dict or set(value) != names:
                raise GitByteStateError()
            result = cls(**value)
            if not valid_worktree(result):
                raise GitByteStateError()
            return result
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None
