"""Fresh caller-owned NTFS fixture for the Issue #74 tracer."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_host_mutation.acl_contracts import (
    AclCompatibilityPolicyV1,
)
from backend.cutover_host_mutation.roles import AclRole
from backend.cutover_host_mutation.windows_acl import (
    _AclRolePaths,
    _create_test_windows_acl_adapter,
    _current_operator_sid_fingerprint,
)
from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_guarded_container_primitive,
)
from backend.cutover_journal import DurabilityPlatform
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)
from tests.cutover_host_mutation_fixtures import durable_intent


@dataclass(slots=True)
class MainPublicationScenario:
    owner: tempfile.TemporaryDirectory[str] | None
    root: Path
    marker: Path
    source: Path
    legacy: Path
    container: Path
    main: Path
    failed_main: Path
    journal: Path
    profile: CutoverProfileV1
    authorization: TestSandboxAuthorizationV1

    def close(self) -> None:
        if self.owner is not None:
            self.owner.cleanup()


def build_main_publication_scenario(
    directory: Path | None = None,
    *,
    shared_root: Path | None = None,
) -> MainPublicationScenario:
    owner = None
    if shared_root is None:
        owner = tempfile.TemporaryDirectory(
            prefix="issue74-main-publication-",
            dir=str(directory) if directory is not None else None,
        )
        root = Path(owner.name).resolve(strict=True)
    else:
        root = shared_root
    marker = root / ".codex-cutover-mutation-test-sandbox"
    marker.write_bytes(b"issue74-synthetic-marker-v1")
    source = root / "flat-root"
    _build_selected_tree(source)
    finance = root / "finance-synthetic"
    finance.mkdir(exist_ok=True)
    container = root / "Container"
    policy = AclCompatibilityPolicyV1.create(
        allowed_descriptor_fingerprints=(opaque_fingerprint(740),),
        maximum_objects=100,
    )
    profile = _profile(policy)
    authorization = TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=opaque_fingerprint(741),
        phase="execute",
        expires_at_epoch=200,
    )
    _publish_protected_container(
        root, marker, source, finance, container,
        policy, profile, authorization,
    )
    return MainPublicationScenario(
        owner=owner,
        root=root,
        marker=marker,
        source=source,
        legacy=root / "LegacySourceAnchorV1",
        container=container,
        main=container / "ManagedMainRootV1",
        failed_main=container / "FailedManagedMainRootV1",
        journal=root / "main-publication.journal",
        profile=profile,
        authorization=authorization,
    )


def _build_selected_tree(source: Path) -> None:
    (source / "selected-directory" / "descendant").mkdir(parents=True)
    (source / "selected-directory" / "descendant" / "leaf.bin").write_bytes(
        b"synthetic-directory-leaf"
    )
    (source / "selected-file.bin").write_bytes(b"synthetic-file-unit")
    repository = source / "repository-like" / ".git-synthetic" / "objects"
    repository.mkdir(parents=True)
    (repository / "object.bin").write_bytes(b"synthetic-repository-object")


def _profile(policy: AclCompatibilityPolicyV1) -> CutoverProfileV1:
    body = valid_profile_body()
    body["operator_fingerprint"] = _current_operator_sid_fingerprint()
    body["acl_policy"]["policy_fingerprint"] = policy.policy_fingerprint
    return CutoverProfileV1.create(body)


def _publish_protected_container(
    root, marker, source, finance, container,
    policy, profile, authorization,
) -> None:
    paths = _role_paths(root, source, finance, container)
    adapter = _create_test_windows_acl_adapter(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        compatibility_policy=policy,
        role_paths=paths,
        observed_at_epoch=100,
    )
    primitive = _create_test_guarded_container_primitive(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        parent=root,
        target=container,
        observed_at_epoch=100,
    )
    intent, permit, store = durable_intent(
        before_fingerprint=primitive.expectation.before_fingerprint,
        expected_after_fingerprint=primitive.expectation.expected_after_fingerprint,
        platform=DurabilityPlatform.WINDOWS,
    )
    created = primitive.create_directory(intent=intent, durable_permit=permit)
    acl_intent, acl_permit, acl_store = durable_intent(
        before_fingerprint=created.observation_fingerprint,
        expected_after_fingerprint=policy.policy_fingerprint,
        platform=DurabilityPlatform.WINDOWS,
    )
    adapter.apply_new_container_policy(
        created_container=created,
        intent=acl_intent,
        durable_permit=acl_permit,
    )
    store.close()
    acl_store.close()


def _role_paths(root, source, finance, container) -> _AclRolePaths:
    return _AclRolePaths(
        source_tree=source,
        parent=root,
        finance=finance,
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
