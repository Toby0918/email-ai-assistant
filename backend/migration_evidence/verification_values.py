"""Primitive bounded values shared by package schema validators."""

from __future__ import annotations

from .errors import MigrationEvidenceError


def bounded_count(value: object, maximum: int) -> bool:
    return (
        type(value) is int
        and type(value) is not bool
        and 0 <= value <= maximum
    )


def is_ref(value: object) -> bool:
    return (
        type(value) is str
        and value.startswith("refs/heads/")
        and len(value) <= 256
        and all(33 <= ord(character) <= 126 for character in value)
    )


def is_oid(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def fail_verification() -> None:
    raise MigrationEvidenceError("migration_evidence_verify_failed")
