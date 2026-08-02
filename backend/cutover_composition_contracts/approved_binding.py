"""Immutable reviewed binding for every R2 cutover surface."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.cutover_contracts import CutoverProfileV1

from .authorization_sequence import AuthorizationSequenceV1
from .canonical import (
    canonical_json,
    fingerprint,
    is_fingerprint,
    strict_json_object,
)
from .errors import CompositionContractError


_ERROR = "R2_APPROVED_CUTOVER_BINDING_INVALID"
_TYPE = "ApprovedCutoverBindingV1"
_BODY_KEYS = (
    "binding_type",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_fingerprint",
    "operator_fingerprint",
    "authorization_sequence_fingerprint",
    "authorization_expires_at_epoch",
    "legacy_source_anchor_fingerprint",
    "managed_main_root_fingerprint",
    "expected_inherited_dacl_projection_fingerprint",
    "repository_manifest_fingerprint",
    "worktree_topology_fingerprint",
    "managed_units_fingerprint",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ApprovedCutoverBindingV1:
    binding_type: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    governing_master_fingerprint: str = field(repr=False)
    operator_fingerprint: str = field(repr=False)
    authorization_sequence_fingerprint: str = field(repr=False)
    authorization_expires_at_epoch: int = field(repr=False)
    legacy_source_anchor_fingerprint: str = field(repr=False)
    managed_main_root_fingerprint: str = field(repr=False)
    expected_inherited_dacl_projection_fingerprint: str = field(repr=False)
    repository_manifest_fingerprint: str = field(repr=False)
    worktree_topology_fingerprint: str = field(repr=False)
    managed_units_fingerprint: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ApprovedCutoverBindingV1 requires reviewed input")

    @classmethod
    def create(
        cls,
        *,
        profile: CutoverProfileV1,
        operation_fingerprint: str,
        authorization_sequence: AuthorizationSequenceV1,
    ) -> ApprovedCutoverBindingV1:
        body = _derive_body(profile, operation_fingerprint, authorization_sequence)
        return _construct(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        profile: CutoverProfileV1,
        authorization_sequence: AuthorizationSequenceV1,
    ) -> ApprovedCutoverBindingV1:
        try:
            value = strict_json_object(payload, code=_ERROR)
            if canonical_json(value) != payload:
                raise CompositionContractError(_ERROR)
            source = _exact_mapping(value, (*_BODY_KEYS, "binding_fingerprint"))
            operation = source["operation_fingerprint"]
            expected = _derive_body(profile, operation, authorization_sequence)
            expected_fingerprint = fingerprint(
                "r2-approved-cutover-binding-v1", expected
            )
            if (
                {key: source[key] for key in _BODY_KEYS} != expected
                or source["binding_fingerprint"] != expected_fingerprint
            ):
                raise CompositionContractError(_ERROR)
            return _construct(expected)
        except CompositionContractError:
            raise
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def to_mapping(self) -> dict[str, object]:
        return {
            **{name: getattr(self, name) for name in _BODY_KEYS},
            "binding_fingerprint": self.binding_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _derive_body(profile, operation, sequence) -> dict[str, object]:
    try:
        profile_body, master = _validated_inputs(
            profile, operation, sequence
        )
        return _derived_mapping(
            profile, operation, sequence, profile_body, master
        )
    except Exception:
        raise CompositionContractError(_ERROR) from None


def _validated_inputs(profile, operation, sequence):
    if (
        type(profile) is not CutoverProfileV1
        or CutoverProfileV1.from_mapping(profile.to_mapping()) != profile
        or not is_fingerprint(operation)
        or type(sequence) is not AuthorizationSequenceV1
    ):
        raise ValueError
    profile_body = profile.to_mapping()
    master = fingerprint(
        "project-container-governing-master-v1",
        profile.governing_master_commit,
    )
    actual = (
        sequence.profile_fingerprint,
        sequence.governing_master_fingerprint,
        sequence.operator_fingerprint,
        sequence.operation_fingerprint,
    )
    expected = (
        profile.profile_fingerprint,
        master,
        profile.operator_fingerprint,
        operation,
    )
    if actual != expected:
        raise ValueError
    return profile_body, master


def _derived_mapping(profile, operation, sequence, profile_body, master):
    roles = profile_body["role_selections"]
    git = profile_body["reviewed_git_selections"]
    managed_units = {
        "runtime": profile_body["runtime_inputs"],
        "database": profile_body["sqlite_source"],
        "crx": profile_body["crx"],
        "config": profile_body["config"],
    }
    return {
        "binding_type": _TYPE,
        "operation_fingerprint": operation,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_fingerprint": master,
        "operator_fingerprint": profile.operator_fingerprint,
        "authorization_sequence_fingerprint": sequence.sequence_fingerprint,
        "authorization_expires_at_epoch": sequence.expires_at_epoch,
        "legacy_source_anchor_fingerprint": roles["legacy_source"],
        "managed_main_root_fingerprint": roles["repository_root"],
        "expected_inherited_dacl_projection_fingerprint": (
            profile_body["acl_policy"]["policy_fingerprint"]
        ),
        "repository_manifest_fingerprint": fingerprint(
            "r2-repository-content-manifest-v1", git
        ),
        "worktree_topology_fingerprint": git["worktree_topology"],
        "managed_units_fingerprint": fingerprint(
            "r2-managed-publication-units-v1", managed_units
        ),
    }


def _construct(body: dict[str, object]) -> ApprovedCutoverBindingV1:
    value = object.__new__(ApprovedCutoverBindingV1)
    for name in _BODY_KEYS:
        object.__setattr__(value, name, body[name])
    object.__setattr__(
        value,
        "binding_fingerprint",
        fingerprint("r2-approved-cutover-binding-v1", body),
    )
    return value


def _exact_mapping(value, expected_keys):
    if (
        type(value) is not dict
        or any(type(key) is not str for key in value)
        or set(value) != set(expected_keys)
    ):
        raise CompositionContractError(_ERROR)
    return value
