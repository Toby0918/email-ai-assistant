"""Review and bind one caller-owned synthetic Windows repository sandbox."""

from __future__ import annotations

import hashlib
import json

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)

from .contracts import (
    RepositoryWorktreePlacement,
    ReviewedWorktreeV1,
    SyntheticRepositoryRosterV1,
)
from .errors import RepositoryTransactionError
from .git_inspection import observe_git_topology
from .git_runner import bind_synthetic_git_runner
from .scope_models import (
    _SyntheticRepositoryReview,
    _SyntheticTransactionScope,
    _SyntheticWorktreePaths,
)
from .scope_paths import (
    evidence_roles as _evidence_roles,
    normalized_absent_path as _normalized_absent_path,
    role_selections as _role_selections,
    rollback_roles as _rollback_roles,
    validated_scenario_paths as _validated_scenario_paths,
)
from .windows_identity import directory_identity, file_identity

_MASTER = "96fceda6e85316dd6b17ef516adf96491d28cb6d"


def _review_test_sandbox(scenario: object) -> _SyntheticRepositoryReview:
    paths = _validated_scenario_paths(scenario)
    root_identity = directory_identity(paths["root"])
    marker_identity = file_identity(paths["marker"])
    git_runner = bind_synthetic_git_runner(
        paths["root"], paths["marker"], paths["source"]
    )
    observations, git_selections = observe_git_topology(
        git_runner, paths["source"], paths["worktrees"]
    )
    repository_object_identity = directory_identity(paths["source"])
    common_object_identity = directory_identity(observations[0].common)
    roster = _build_roster(observations)
    roles = _role_selections(paths)
    evidence = _evidence_roles(paths)
    rollback = _rollback_roles(paths)
    operation = _operation_fingerprint(
        root_identity, marker_identity, roster, roles, evidence,
        git_selections, rollback,
    )
    return _SyntheticRepositoryReview(
        scenario=scenario,
        roster=roster,
        observations=observations,
        role_selections=roles,
        evidence_roles=evidence,
        reviewed_git_selections=git_selections,
        rollback_roles=rollback,
        operation_fingerprint=operation,
        root_identity=root_identity,
        marker_identity=marker_identity,
        git_runner=git_runner,
        repository_object_identity=repository_object_identity,
        common_object_identity=common_object_identity,
        volume_identity=_volume_identity(paths["source"]),
    )


def _bind_test_sandbox_transaction(
    *,
    review: object,
    profile: object,
    authorization: object,
    observed_at_epoch: object,
) -> _SyntheticTransactionScope:
    if (
        type(review) is not _SyntheticRepositoryReview
        or type(profile) is not CutoverProfileV1
        or type(authorization) is not TestSandboxAuthorizationV1
        or type(observed_at_epoch) is not int
    ):
        _fail("repository_scope_invalid")
    if not _authorization_matches(
        review, profile, authorization, observed_at_epoch
    ):
        _fail("repository_authorization_invalid")
    try:
        current = _review_test_sandbox(review.scenario)
    except RepositoryTransactionError:
        _fail("repository_scope_drift")
    if not _reviews_match(review, current):
        _fail("repository_scope_drift")
    if not _profile_matches(profile, current):
        _fail("repository_profile_mismatch")
    return _SyntheticTransactionScope(
        review=current,
        profile=profile,
        authorization=authorization,
        roster=current.roster,
    )


def _build_roster(observations):
    worktrees = tuple(
        ReviewedWorktreeV1.create(
            role=item.paths.role,
            placement=RepositoryWorktreePlacement(item.paths.placement),
            selection_fingerprint=_fingerprint(
                "worktree-selection", item.paths.role, item.ref, item.commit,
                item.physical_identity, item.admin_identity,
                item.admin_content,
            ),
            ref_fingerprint=_fingerprint("worktree-ref", item.paths.role, item.ref),
            commit_fingerprint=_fingerprint(
                "worktree-commit", item.paths.role, item.commit
            ),
            common_directory_fingerprint=_fingerprint(
                "worktree-common", str(item.common)
            ),
            physical_identity_fingerprint=_fingerprint(
                "worktree-physical", item.paths.role, item.physical_identity
            ),
            admin_identity_fingerprint=_fingerprint(
                "worktree-admin", item.paths.role, item.admin_identity
            ),
            admin_content_fingerprint=_fingerprint(
                "worktree-admin-content", item.paths.role, item.admin_content
            ),
            target_fingerprint=_fingerprint(
                "worktree-target", item.paths.role,
                _normalized_absent_path(item.paths.target),
            ),
            preservation_fingerprint=_fingerprint(
                "worktree-preservation", item.paths.role,
                _normalized_absent_path(item.paths.preservation),
            ),
            clean=True,
        )
        for item in observations
    )
    return SyntheticRepositoryRosterV1.create(worktrees=worktrees)


def _profile_matches(profile, review):
    mapping = profile.to_mapping()
    roster = [
        {
            "role": item.role,
            "placement": item.placement.value,
            "selection_fingerprint": item.selection_fingerprint,
        }
        for item in review.roster.worktrees
    ]
    return (
        mapping["governing_master_commit"] == _MASTER
        and mapping["role_selections"] == review.role_selections
        and mapping["evidence_roles"] == review.evidence_roles
        and mapping["reviewed_git_selections"]
        == review.reviewed_git_selections
        and mapping["rollback_roles"] == review.rollback_roles
        and mapping["worktree_roster"] == roster
    )


def _authorization_matches(review, profile, authorization, observed):
    return (
        authorization.profile_fingerprint == profile.profile_fingerprint
        and authorization.operation_fingerprint
        == review.operation_fingerprint
        and authorization.phase == "execute"
        and 0 <= observed < authorization.expires_at_epoch
    )


def _reviews_match(left, right):
    return (
        left.roster == right.roster
        and left.role_selections == right.role_selections
        and left.evidence_roles == right.evidence_roles
        and left.reviewed_git_selections == right.reviewed_git_selections
        and left.rollback_roles == right.rollback_roles
        and left.operation_fingerprint == right.operation_fingerprint
        and left.root_identity == right.root_identity
        and left.marker_identity == right.marker_identity
        and left.git_runner.binding_fingerprint
        == right.git_runner.binding_fingerprint
        and left.repository_object_identity
        == right.repository_object_identity
        and left.common_object_identity == right.common_object_identity
    )


def _operation_fingerprint(*values):
    payload = _canonical(
        [
            value.roster_fingerprint
            if type(value) is SyntheticRepositoryRosterV1
            else value
            for value in values
        ]
    )
    return hashlib.sha256(b"issue56-operation-v1\0" + payload).hexdigest()


def _volume_identity(path):
    from .windows_identity import directory_identity_and_volume

    return directory_identity_and_volume(path)[1]


def _fingerprint(domain: str, *values: str) -> str:
    return hashlib.sha256(
        domain.encode("ascii") + b"\0" + _canonical(list(values))
    ).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False,
        sort_keys=True, separators=(",", ":"),
    ).encode("ascii")


def _fail(code: str) -> None:
    raise RepositoryTransactionError(code) from None


__all__ = ["_SyntheticWorktreePaths"]
