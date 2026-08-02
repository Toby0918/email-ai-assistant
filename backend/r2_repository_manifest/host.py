"""Fixed host and Git effects for the synthetic Issue #75 transaction."""

from __future__ import annotations

from pathlib import Path

from backend.cutover_host_mutation.acl_paths import AclRolePaths
from backend.cutover_host_mutation.filesystem_contracts import (
    FilesystemMutationExpectationV1,
)
from backend.cutover_host_mutation.roles import FilesystemMutationKind
from backend.cutover_host_mutation.windows_acl import (
    _create_test_windows_acl_adapter,
)
from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_directory_primitive,
    _create_test_guarded_container_primitive,
)
from backend.cutover_repository_transaction.git_recreation import (
    add_reviewed_worktree,
)
from backend.r2_main_publication.host_effects import (
    build_projection,
    move_object,
)
from backend.r2_main_publication.permit import issue_host_effect_permit
from backend.r2_main_publication.windows_dacl import (
    apply_projection,
    capture_tree,
)

from .canonical import fingerprint

_ZONES = (
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)


def build_acl_adapter(state):
    source = state.scope.review.scenario.source
    container = Path(source)
    paths = AclRolePaths(
        source_tree=container,
        parent=state.root,
        finance=state.root / "finance-synthetic",
        project_container=container,
        runtimes=container / "Runtimes",
        local_data=container / "LocalData",
        runtime_temp=container / "RuntimeTemp",
        logs=container / "Logs",
        artifacts=container / "Artifacts",
        worktrees=container / "Worktrees",
        config=container / "Config",
        operator_private=container / "OperatorPrivate",
    )
    return _create_test_windows_acl_adapter(
        root=state.root,
        marker=state.marker,
        authorization=state.authorization,
        profile=state.profile,
        compatibility_policy=state.policy,
        role_paths=paths,
        observed_at_epoch=state.observed_at_epoch,
    )


def preserve_originals(state) -> tuple[object, ...]:
    scenario = state.scope.review.scenario
    values = []
    for item in state.scope.review.observations:
        values.append(
            move_object(
                state,
                item.paths.original,
                Path(scenario.worktree_preservation) / item.paths.role,
            )
        )
    for item in state.scope.review.observations:
        values.append(
            move_object(
                state,
                item.admin,
                Path(scenario.admin_preservation) / item.paths.role,
            )
        )
    return tuple(values)


def publish_container(state, adapter):
    primitive = _create_test_guarded_container_primitive(
        root=state.root,
        marker=state.marker,
        authorization=state.authorization,
        profile=state.profile,
        parent=state.root,
        target=state.container,
        observed_at_epoch=state.observed_at_epoch,
    )
    created = _run_primitive(state, primitive, "create_directory")
    expectation = FilesystemMutationExpectationV1.create(
        kind=FilesystemMutationKind.CREATE_DIRECTORY,
        binding_fingerprint=fingerprint(
            "manifest-acl-binding-v1", created.observation_fingerprint
        ),
        before_fingerprint=created.observation_fingerprint,
        expected_after_fingerprint=state.policy.policy_fingerprint,
    )
    permit = _permit(state, expectation)
    try:
        adapter.apply_new_container_policy(
            created_container=created,
            intent=permit.intent,
            durable_permit=permit.permit,
        )
    finally:
        permit.close()
    for name in _ZONES:
        create_directory(state, state.container / name)
    adapter.verify_fixed_zone_inheritance()
    return created


def create_directory(state, target: Path):
    primitive = _create_test_directory_primitive(
        root=state.root,
        marker=state.marker,
        authorization=state.authorization,
        profile=state.profile,
        parent=target.parent,
        target=target,
        observed_at_epoch=state.observed_at_epoch,
    )
    return _run_primitive(state, primitive, "create_directory")


def build_main(state):
    create_directory(state, state.main)
    projection = build_projection(state)
    return projection


def conform_main(state, projection) -> None:
    apply_projection(capture_tree(state.main), projection)


def reconstruct_worktree(state, reviewed, expected_admins):
    reservation = create_directory(state, reviewed.paths.target)
    return add_reviewed_worktree(
        state.scope,
        reviewed,
        state.main,
        reservation.target_identity_fingerprint,
        frozenset(expected_admins),
    )


def _run_primitive(state, primitive, method):
    permit = _permit(state, primitive.expectation)
    try:
        return getattr(primitive, method)(
            intent=permit.intent,
            durable_permit=permit.permit,
        )
    finally:
        permit.close()


def _permit(state, expectation):
    return issue_host_effect_permit(
        profile=state.profile,
        authorization=state.authorization,
        owner_fingerprint=state.scope.review.marker_identity,
        expectation=expectation,
    )


def zones() -> tuple[str, ...]:
    return _ZONES
