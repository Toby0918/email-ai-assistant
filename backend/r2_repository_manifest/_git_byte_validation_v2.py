"""Closed scalar validation for Git-byte V2 observations."""

import hashlib

from .canonical import is_fingerprint


MODES = {"100644", "100755", "120000"}


class GitByteStateError(ValueError):
    def __init__(self):
        super().__init__("R2_GIT_BYTE_STATE_INVALID")


def valid_worktree(value):
    return (
        type(value.role) is str
        and value.placement in {"embedded", "external"}
        and value.state_kind in {"original", "reconstructed"}
        and is_fingerprint(value.ref_fingerprint)
        and is_oid(value.commit_oid)
        and is_fingerprint(value.physical_identity_fingerprint)
        and is_fingerprint(value.admin_identity_fingerprint)
        and is_fingerprint(value.admin_content_sha256)
        and type(value.admin_byte_count) is int
        and 0 <= value.admin_byte_count <= 16_777_216
        and is_fingerprint(value.checkout_sha256)
        and type(value.checkout_byte_count) is int
        and 0 <= value.checkout_byte_count <= 67_108_864
    )


def safe_relative(value):
    return (
        type(value) is str
        and value
        and not value.startswith("/")
        and "\\" not in value
        and "\0" not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
        and all(ord(character) >= 32 for character in value)
    )


def is_oid(value):
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def blob_oid(value):
    header = f"blob {len(value)}\0".encode("ascii")
    return hashlib.sha1(header + value).hexdigest()


def sha256(value):
    return hashlib.sha256(value).hexdigest()
