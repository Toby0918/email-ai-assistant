"""Closed reviewed worktree roster values."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from .errors import RepositoryTransactionError


class RepositoryWorktreePlacement(str, Enum):
    EMBEDDED = "embedded"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ReviewedWorktreeV1:
    role: str
    placement: RepositoryWorktreePlacement
    selection_fingerprint: str = field(repr=False)
    ref_fingerprint: str = field(repr=False)
    commit_fingerprint: str = field(repr=False)
    common_directory_fingerprint: str = field(repr=False)
    physical_identity_fingerprint: str = field(repr=False)
    admin_identity_fingerprint: str = field(repr=False)
    admin_content_fingerprint: str = field(repr=False)
    target_fingerprint: str = field(repr=False)
    preservation_fingerprint: str = field(repr=False)
    clean: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated reviewed worktree required")

    @classmethod
    def create(cls, **values: object) -> ReviewedWorktreeV1:
        if not _valid_worktree(values):
            raise RepositoryTransactionError("repository_worktree_invalid")
        result = object.__new__(cls)
        for name in _WORKTREE_FIELDS:
            object.__setattr__(result, name, values[name])
        return result


@dataclass(frozen=True, slots=True, init=False, repr=False)
class SyntheticRepositoryRosterV1:
    worktrees: tuple[ReviewedWorktreeV1, ...] = field(repr=False)
    worktree_count: int
    embedded_count: int
    external_count: int
    roster_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated synthetic roster required")

    @classmethod
    def create(
        cls, *, worktrees: tuple[ReviewedWorktreeV1, ...]
    ) -> SyntheticRepositoryRosterV1:
        if not _valid_roster(worktrees):
            raise RepositoryTransactionError("repository_roster_invalid")
        result = object.__new__(cls)
        object.__setattr__(result, "worktrees", worktrees)
        object.__setattr__(result, "worktree_count", 11)
        object.__setattr__(result, "embedded_count", 8)
        object.__setattr__(result, "external_count", 3)
        object.__setattr__(
            result, "roster_fingerprint", _roster_fingerprint(worktrees)
        )
        return result


_FINGERPRINT_FIELDS = (
    "selection_fingerprint",
    "ref_fingerprint",
    "commit_fingerprint",
    "common_directory_fingerprint",
    "physical_identity_fingerprint",
    "admin_identity_fingerprint",
    "admin_content_fingerprint",
    "target_fingerprint",
    "preservation_fingerprint",
)
_WORKTREE_FIELDS = (
    "role",
    "placement",
    *_FINGERPRINT_FIELDS,
    "clean",
)


def _valid_worktree(values: dict[str, object]) -> bool:
    if set(values) != set(_WORKTREE_FIELDS):
        return False
    role = values["role"]
    return (
        type(role) is str
        and role in {f"worktree_{index:02d}" for index in range(1, 12)}
        and type(values["placement"]) is RepositoryWorktreePlacement
        and values["clean"] is True
        and all(_is_fingerprint(values[name]) for name in _FINGERPRINT_FIELDS)
        and len({values[name] for name in _FINGERPRINT_FIELDS})
        == len(_FINGERPRINT_FIELDS)
    )


def _valid_roster(worktrees: object) -> bool:
    if type(worktrees) is not tuple or len(worktrees) != 11:
        return False
    unique_fields = (
        "selection_fingerprint",
        "ref_fingerprint",
        "physical_identity_fingerprint",
        "admin_identity_fingerprint",
        "admin_content_fingerprint",
        "target_fingerprint",
        "preservation_fingerprint",
    )
    fingerprints: dict[str, set[str]] = {
        name: set() for name in unique_fields
    }
    common = worktrees[0].common_directory_fingerprint
    for index, worktree in enumerate(worktrees, start=1):
        placement = (
            RepositoryWorktreePlacement.EMBEDDED
            if index <= 8
            else RepositoryWorktreePlacement.EXTERNAL
        )
        if (
            type(worktree) is not ReviewedWorktreeV1
            or worktree.role != f"worktree_{index:02d}"
            or worktree.placement is not placement
            or worktree.common_directory_fingerprint != common
        ):
            return False
        for name in unique_fields:
            value = getattr(worktree, name)
            if value in fingerprints[name]:
                return False
            fingerprints[name].add(value)
    return True


def _roster_fingerprint(
    worktrees: tuple[ReviewedWorktreeV1, ...],
) -> str:
    body = [
        {
            name: (
                getattr(worktree, name).value
                if name == "placement"
                else getattr(worktree, name)
            )
            for name in _WORKTREE_FIELDS
        }
        for worktree in worktrees
    ]
    payload = json.dumps(
        body,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
