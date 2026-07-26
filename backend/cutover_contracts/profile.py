"""Immutable canonical Project Container Cutover Profile."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ._canonical import canonical_json, strict_json_object
from .errors import CutoverContractError
from .profile_schema import (
    PROFILE_BODY_KEYS,
    PROFILE_ERROR,
    PROFILE_TYPE,
    _exact_dict,
    _is_fingerprint,
    validate_profile_body,
)


@dataclass(frozen=True, slots=True, repr=False)
class _FrozenObject:
    items: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True, repr=False)
class _FrozenArray:
    items: tuple[object, ...]


@dataclass(frozen=True, slots=True, init=False)
class CutoverProfileV1:
    """One reviewed, pathless, immutable cutover selection."""

    governing_master_commit: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    role_selections: _FrozenObject = field(repr=False)
    evidence_roles: _FrozenObject = field(repr=False)
    reviewed_git_selections: _FrozenObject = field(repr=False)
    worktree_roster: _FrozenArray = field(repr=False)
    runtime_inputs: _FrozenObject = field(repr=False)
    sqlite_source: _FrozenObject = field(repr=False)
    crx: _FrozenObject = field(repr=False)
    config: _FrozenObject = field(repr=False)
    acl_policy: _FrozenObject = field(repr=False)
    maintenance_rules: _FrozenObject = field(repr=False)
    rollback_roles: _FrozenObject = field(repr=False)
    profile_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CutoverProfileV1 requires validated construction")

    @classmethod
    def create(cls, value: object) -> CutoverProfileV1:
        body = validate_profile_body(value)
        fingerprint = hashlib.sha256(
            canonical_json(body, code=PROFILE_ERROR)
        ).hexdigest()
        return cls.from_mapping(
            {**body, "profile_fingerprint": fingerprint}
        )

    @classmethod
    def from_mapping(cls, value: object) -> CutoverProfileV1:
        source = _exact_dict(
            value,
            (*PROFILE_BODY_KEYS, "profile_fingerprint"),
        )
        fingerprint = source["profile_fingerprint"]
        if not _is_fingerprint(fingerprint):
            raise CutoverContractError(PROFILE_ERROR)
        body = {key: source[key] for key in PROFILE_BODY_KEYS}
        normalized = validate_profile_body(body)
        expected_fingerprint = hashlib.sha256(
            canonical_json(normalized, code=PROFILE_ERROR)
        ).hexdigest()
        if fingerprint != expected_fingerprint:
            raise CutoverContractError(PROFILE_ERROR)
        profile = object.__new__(cls)
        object.__setattr__(
            profile,
            "governing_master_commit",
            normalized["governing_master_commit"],
        )
        object.__setattr__(
            profile, "operator_fingerprint", normalized["operator_fingerprint"]
        )
        for name in PROFILE_BODY_KEYS[3:]:
            object.__setattr__(profile, name, _freeze(normalized[name]))
        object.__setattr__(
            profile, "profile_fingerprint", expected_fingerprint
        )
        return profile

    @classmethod
    def from_json(cls, payload: object) -> CutoverProfileV1:
        value = strict_json_object(payload, code=PROFILE_ERROR)
        if canonical_json(value, code=PROFILE_ERROR) != payload:
            raise CutoverContractError(PROFILE_ERROR)
        return cls.from_mapping(value)

    def to_mapping(self) -> dict[str, object]:
        return {
            "profile_type": PROFILE_TYPE,
            "governing_master_commit": self.governing_master_commit,
            "operator_fingerprint": self.operator_fingerprint,
            "role_selections": _thaw(self.role_selections),
            "evidence_roles": _thaw(self.evidence_roles),
            "reviewed_git_selections": _thaw(self.reviewed_git_selections),
            "worktree_roster": _thaw(self.worktree_roster),
            "runtime_inputs": _thaw(self.runtime_inputs),
            "sqlite_source": _thaw(self.sqlite_source),
            "crx": _thaw(self.crx),
            "config": _thaw(self.config),
            "acl_policy": _thaw(self.acl_policy),
            "maintenance_rules": _thaw(self.maintenance_rules),
            "rollback_roles": _thaw(self.rollback_roles),
            "profile_fingerprint": self.profile_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping(), code=PROFILE_ERROR)


def _freeze(value: object) -> object:
    if type(value) is dict:
        return _FrozenObject(
            tuple((key, _freeze(value[key])) for key in sorted(value))
        )
    if type(value) is list:
        return _FrozenArray(tuple(_freeze(item) for item in value))
    return value


def _thaw(value: object) -> object:
    if type(value) is _FrozenObject:
        return {key: _thaw(item) for key, item in value.items}
    if type(value) is _FrozenArray:
        return [_thaw(item) for item in value.items]
    return value
