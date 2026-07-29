"""Issue #56 read-only composition of unchanged ContainerAudit policy seams."""

from __future__ import annotations

from pathlib import Path

from backend.container_audit import (
    AuditObject,
    AuditObjectKind,
    BoundedMetadataInventory,
    ConfigMetadata,
    ExternalPrivateState,
    FilesystemEvidence,
    GitEvidence,
    OperatorPrivateState,
    SqliteExpectation,
    TopLevelEntry,
    TrustedAuditPolicy,
    WorktreeEvidence,
    WorktreeRelationship,
)
from backend.container_audit.filesystem_checks import (
    valid_filesystem,
    valid_object,
)
from backend.container_audit.policy import (
    AUDIT_SCHEMA_VERSION,
    NORMAL_CONFIG_FILENAME,
    TOP_LEVEL_NAMES,
    is_valid_policy,
)
from backend.container_audit.system_checks import (
    valid_git,
    valid_worktrees,
)

from .errors import RepositoryTransactionError
from .git_recreation import observe_all_recreated
from .journal_identity import journaled_container_identity
from .windows_identity import directory_identity_and_volume

_EMPTY_ZONES = (
    "Runtimes", "LocalData", "RuntimeTemp", "Logs", "Artifacts", "Config",
    "OperatorPrivate",
)


def require_container_audit_policy_seams(scope, recreated) -> None:
    container = Path(scope.review.scenario.source)
    _require_forward_inventory(scope, container)
    objects = _topology_objects(container)
    filesystem = _filesystem_evidence(objects)
    policy = _policy(scope)
    git = _git_evidence(objects)
    observed = observe_all_recreated(scope, container / "main")
    if not _same_recreated(observed, recreated):
        _fail()
    worktrees = _worktree_evidence(scope, observed, objects)
    if not (
        is_valid_policy(policy)
        and objects["container"].identity == policy.container_identity
        and objects["container"].volume_identity == policy.volume_identity
        and valid_filesystem(filesystem)
        and valid_git(filesystem, git)
        and valid_worktrees(policy, filesystem, git, worktrees)
    ):
        raise RepositoryTransactionError(
            "repository_container_audit_policy_failed"
        ) from None


def require_reverse_failed_policy_seam(
    scope,
    *,
    main_extracted: bool = True,
) -> None:
    failed = Path(scope.review.scenario.failed_container)
    expected = set(TOP_LEVEL_NAMES) - {"main"}
    if not main_extracted:
        expected.add("main")
    _require_exact_children(failed, expected)
    for name in _EMPTY_ZONES:
        _require_exact_children(failed / name, set())
    embedded = {
        item.paths.target.name for item in scope.review.observations[:8]
    }
    _require_exact_children(failed / "Worktrees", embedded)
    objects = (
        _audit_object(failed),
        *(_audit_object(failed / name) for name in sorted(expected)),
        *(
            _audit_object(failed / "Worktrees" / name)
            for name in sorted(embedded)
        ),
    )
    if (
        _audit_object(failed).identity != journaled_container_identity(scope)
        or
        any(
            not valid_object(item, kind=AuditObjectKind.DIRECTORY)
            for item in objects
        )
        or {item.volume_identity for item in objects}
        != {scope.review.volume_identity}
    ):
        _fail()


def _topology_objects(container: Path) -> dict[str, AuditObject]:
    paths = {"container": container}
    paths.update({name: container / name for name in TOP_LEVEL_NAMES})
    paths["common"] = container / "main" / ".git"
    objects = {name: _audit_object(path) for name, path in paths.items()}
    volumes = {value.volume_identity for value in objects.values()}
    if len(volumes) != 1 or len(
        {value.identity for value in objects.values()}
    ) != len(objects):
        _fail()
    return objects


def _filesystem_evidence(objects) -> FilesystemEvidence:
    entries = tuple(
        TopLevelEntry(
            name=name,
            object=objects[name],
            direct_child_of_container=True,
        )
        for name in sorted(TOP_LEVEL_NAMES)
    )
    return FilesystemEvidence(
        schema_version=AUDIT_SCHEMA_VERSION,
        container=objects["container"],
        entries=entries,
        inventory_complete=True,
        config=_empty_config(objects["Config"]),
        logs=_empty_inventory(objects["Logs"]),
        artifacts=_empty_inventory(objects["Artifacts"]),
        operator_private_state=OperatorPrivateState.DISABLED,
        operator_private_content_observed=False,
        raw_vault_state=ExternalPrivateState.NOT_PROVISIONED,
        recovery_state=ExternalPrivateState.NOT_PROVISIONED,
    )


def _policy(scope) -> TrustedAuditPolicy:
    profile = scope.profile.to_mapping()
    acl = profile["acl_policy"]["policy_fingerprint"]
    approvals = tuple(
        sorted(
            item.selection_fingerprint
            for item in scope.roster.worktrees[:8]
        )
    )
    return TrustedAuditPolicy(
        schema_version=AUDIT_SCHEMA_VERSION,
        container_identity=journaled_container_identity(scope),
        container_acl_fingerprint=acl,
        operator_private_acl_fingerprint=acl,
        volume_identity=scope.review.volume_identity,
        approved_worktrees=approvals,
        require_clean_worktrees=True,
        sqlite_expectation=SqliteExpectation.ABSENT_EXPECTED,
    )


def _git_evidence(objects) -> GitEvidence:
    return GitEvidence(
        schema_version=AUDIT_SCHEMA_VERSION,
        inventory_complete=True,
        repository_count=1,
        common_directory_count=1,
        repository=objects["main"],
        common_directory=objects["common"],
        repository_name="main",
        common_directory_name=".git",
        common_directory_inside_repository=True,
        common_directory_direct_child_of_repository=True,
        content_observed=False,
    )


def _worktree_evidence(scope, recreated, objects) -> WorktreeEvidence:
    embedded = tuple(recreated[:8])
    root = Path(scope.review.scenario.source) / "Worktrees"
    if (
        len(recreated) != 11
        or any(item.physical.parent != root for item in embedded)
        or any(
            item.reviewed.paths.placement != "external"
            for item in recreated[8:]
        )
    ):
        _fail()
    relationships = tuple(
        WorktreeRelationship(
            approval_id=scope.roster.worktrees[index].selection_fingerprint,
            worktree=_audit_object(item.physical),
            common_directory_identity=objects["common"].identity,
            direct_child_of_worktrees=True,
            linked=True,
            branch_attached=True,
            clean=True,
            content_observed=False,
        )
        for index, item in enumerate(embedded)
    )
    if any(
        item.worktree.volume_identity
        != objects["container"].volume_identity
        for item in relationships
    ):
        _fail()
    return WorktreeEvidence(
        schema_version=AUDIT_SCHEMA_VERSION,
        inventory_complete=True,
        main_worktree_count=1,
        worktrees_root_identity=objects["Worktrees"].identity,
        relationships=relationships,
    )


def _require_forward_inventory(scope, container: Path) -> None:
    for name in _EMPTY_ZONES:
        _require_exact_children(container / name, set())
    embedded = {
        item.paths.target.name for item in scope.review.observations[:8]
    }
    external = {
        item.paths.target.name for item in scope.review.observations[8:]
    }
    _require_exact_children(container / "Worktrees", embedded)
    _require_exact_children(
        Path(scope.review.scenario.external_target_parent), external
    )


def _require_exact_children(parent: Path, expected: set[str]) -> None:
    if not parent.is_dir() or parent.is_symlink():
        _fail()
    children = tuple(parent.iterdir())
    if (
        {item.name for item in children} != expected
        or any(not item.is_dir() or item.is_symlink() for item in children)
    ):
        _fail()


def _same_recreated(left, right) -> bool:
    return (
        len(left) == len(right) == 11
        and all(
            current.reviewed is expected.reviewed
            and current.physical_identity == expected.physical_identity
            and current.admin_identity == expected.admin_identity
            and current.admin_content == expected.admin_content
            for current, expected in zip(left, right)
        )
    )


def _empty_config(root: AuditObject) -> ConfigMetadata:
    return ConfigMetadata(
        directory_identity=root.identity,
        filename=NORMAL_CONFIG_FILENAME,
        present=False,
        settings_file=None,
        size_bytes=0,
        keys=(),
        inventory_complete=True,
        direct_only=True,
        values_observed=False,
    )


def _empty_inventory(root: AuditObject) -> BoundedMetadataInventory:
    return BoundedMetadataInventory(
        root_identity=root.identity,
        entries=(),
        inventory_complete=True,
        direct_only=True,
        content_observed=False,
    )


def _audit_object(path: Path) -> AuditObject:
    identity, volume = directory_identity_and_volume(path)
    return AuditObject(
        identity=identity,
        kind=AuditObjectKind.DIRECTORY,
        volume_identity=volume,
    )


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_container_audit_policy_failed"
    ) from None
