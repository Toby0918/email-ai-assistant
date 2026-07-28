"""Windows ACL proof restricted to a caller-owned temporary NTFS sandbox."""

from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_host_mutation import (
    AclApplyReceiptV1,
    AclCompatibilityReceiptV1,
    AclCompatibilityPolicyV1,
    AclPostVerifyReceiptV1,
    AclReceiptStatus,
    AclRole,
)
from backend.cutover_host_mutation.windows_acl_apply import (
    _APPLY_SECURITY_INFORMATION,
    _DACL_SECURITY_INFORMATION,
    _GROUP_SECURITY_INFORMATION,
    _OWNER_SECURITY_INFORMATION,
    _PROTECTED_DACL_SECURITY_INFORMATION,
    _SACL_SECURITY_INFORMATION,
)
from backend.cutover_host_mutation.errors import CutoverHostMutationError
from backend.cutover_host_mutation.windows_acl import (
    _AclRolePaths,
    _create_test_windows_acl_adapter,
    _current_operator_sid_fingerprint,
)
from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_directory_primitive,
)
from backend.cutover_host_mutation.windows_security import WindowsSecurityApi
from backend.cutover_journal import DurabilityPlatform
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)
from tests.cutover_host_mutation_fixtures import durable_intent


@unittest.skipUnless(sys.platform == "win32", "Windows integration only")
class CutoverHostMutationWindowsAclTests(unittest.TestCase):
    def test_source_tree_compatibility_is_complete_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            child = source / "nested"
            finance = root / "finance"
            child.mkdir(parents=True)
            finance.mkdir()
            file_path = child / "tracked.txt"
            file_path.write_text("synthetic", encoding="utf-8")
            before = _descriptor_fingerprints((source, child, file_path))
            policy = AclCompatibilityPolicyV1.create(
                allowed_descriptor_fingerprints=tuple(sorted(set(before))),
                maximum_objects=10,
            )
            adapter = _adapter_with_policy(
                root,
                source=source,
                finance=finance,
                policy=policy,
            )

            receipt = adapter.capture(AclRole.SOURCE_TREE)

            self.assertIs(type(receipt), AclCompatibilityReceiptV1)
            self.assertIs(receipt.status, AclReceiptStatus.ACCEPTED)
            self.assertEqual(receipt.observed_objects, 3)
            self.assertEqual(
                _descriptor_fingerprints((source, child, file_path)),
                before,
            )
            self.assertNotIn(str(root), repr(receipt))

    def test_source_tree_rejects_unexpected_descriptor_without_writes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            finance = root / "finance"
            source.mkdir()
            finance.mkdir()
            before = _descriptor_fingerprints((source,))
            policy = AclCompatibilityPolicyV1.create(
                allowed_descriptor_fingerprints=(opaque_fingerprint(699),),
                maximum_objects=10,
            )
            adapter = _adapter_with_policy(
                root,
                source=source,
                finance=finance,
                policy=policy,
            )

            receipt = adapter.capture(AclRole.SOURCE_TREE)

            self.assertIs(type(receipt), AclCompatibilityReceiptV1)
            self.assertIs(receipt.status, AclReceiptStatus.REJECTED)
            self.assertEqual(receipt.failure_code.value, "ACL_COMPATIBILITY_REJECTED")
            self.assertEqual(receipt.observed_objects, 1)
            self.assertEqual(_descriptor_fingerprints((source,)), before)

    def test_source_tree_rejects_protected_descriptor_without_rewrite(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = _bundle(Path(temporary))
            created, create_store = _create_directory(
                bundle,
                bundle.paths.project_container,
            )
            intent, permit, apply_store = durable_intent(
                before_fingerprint=created.observation_fingerprint,
                expected_after_fingerprint=bundle.policy.policy_fingerprint,
                platform=DurabilityPlatform.WINDOWS,
            )
            bundle.adapter.apply_new_container_policy(
                created_container=created,
                intent=intent,
                durable_permit=permit,
            )
            before = _descriptor_fingerprints(
                (bundle.paths.project_container,)
            )
            policy = AclCompatibilityPolicyV1.create(
                allowed_descriptor_fingerprints=before,
                maximum_objects=10,
            )
            read_only_adapter = _adapter_with_policy(
                bundle.root,
                source=bundle.paths.project_container,
                finance=bundle.paths.finance,
                policy=policy,
            )

            receipt = read_only_adapter.capture(AclRole.SOURCE_TREE)

            self.assertIs(receipt.status, AclReceiptStatus.REJECTED)
            self.assertEqual(
                receipt.failure_code.value,
                "ACL_COMPATIBILITY_REJECTED",
            )
            self.assertEqual(
                _descriptor_fingerprints(
                    (bundle.paths.project_container,)
                ),
                before,
            )
            create_store.close()
            apply_store.close()

    def test_parent_and_finance_are_capture_and_exact_compare_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            finance = root / "finance"
            source.mkdir()
            finance.mkdir()
            adapter = _adapter(root, source=source, finance=finance)

            parent_baseline = adapter.capture(AclRole.PARENT)
            finance_baseline = adapter.capture(AclRole.FINANCE)
            parent_result = adapter.compare(parent_baseline)
            finance_result = adapter.compare(finance_baseline)

            self.assertIs(type(parent_result), AclPostVerifyReceiptV1)
            self.assertIs(type(finance_result), AclPostVerifyReceiptV1)
            self.assertIs(parent_result.status, AclReceiptStatus.ACCEPTED)
            self.assertIs(finance_result.status, AclReceiptStatus.ACCEPTED)
            self.assertEqual(parent_result.observed_objects, 1)
            self.assertEqual(finance_result.observed_objects, 1)
            self.assertNotIn(str(root), repr(parent_baseline))
            self.assertNotIn(str(root), repr(finance_result))

    def test_adapter_binds_current_token_sid_to_profile_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            finance = root / "finance"
            source.mkdir()
            finance.mkdir()
            policy = AclCompatibilityPolicyV1.create(
                allowed_descriptor_fingerprints=(opaque_fingerprint(600),),
                maximum_objects=10,
            )
            profile = _profile(policy, operator=opaque_fingerprint(601))
            authorization = _authorization(profile)

            with self.assertRaises(CutoverHostMutationError) as raised:
                _create_test_windows_acl_adapter(
                    root=root,
                    marker=_marker(root),
                    authorization=authorization,
                    profile=profile,
                    compatibility_policy=policy,
                    role_paths=_paths(root, source, finance),
                    observed_at_epoch=100,
                )

            self.assertEqual(
                raised.exception.code,
                "acl_authorization_rejected",
            )

    def test_apply_is_journaled_exact_and_leaves_adjacent_acls_unchanged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = _bundle(Path(temporary))
            parent_baseline = bundle.adapter.capture(AclRole.PARENT)
            finance_baseline = bundle.adapter.capture(AclRole.FINANCE)
            created, create_store = _create_directory(
                bundle,
                bundle.paths.project_container,
            )
            intent, permit, apply_store = durable_intent(
                before_fingerprint=created.observation_fingerprint,
                expected_after_fingerprint=bundle.policy.policy_fingerprint,
                platform=DurabilityPlatform.WINDOWS,
            )

            receipt = bundle.adapter.apply_new_container_policy(
                created_container=created,
                intent=intent,
                durable_permit=permit,
            )

            self.assertIs(type(receipt), AclApplyReceiptV1)
            self.assertIs(receipt.status, AclReceiptStatus.ACCEPTED)
            self.assertEqual(receipt.observed_objects, 1)
            self.assertEqual(
                bundle.adapter.compare(parent_baseline).status,
                AclReceiptStatus.ACCEPTED,
            )
            self.assertEqual(
                bundle.adapter.compare(finance_baseline).status,
                AclReceiptStatus.ACCEPTED,
            )
            self.assertEqual(
                list(bundle.paths.project_container.iterdir()),
                [],
            )
            create_store.close()
            apply_store.close()

    def test_apply_security_information_can_change_only_the_dacl(self) -> None:
        self.assertEqual(
            _APPLY_SECURITY_INFORMATION,
            _DACL_SECURITY_INFORMATION
            | _PROTECTED_DACL_SECURITY_INFORMATION,
        )
        self.assertFalse(
            _APPLY_SECURITY_INFORMATION
            & (
                _OWNER_SECURITY_INFORMATION
                | _GROUP_SECURITY_INFORMATION
                | _SACL_SECURITY_INFORMATION
            )
        )

    def test_apply_rejects_nonempty_or_unproven_container_without_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = _bundle(Path(temporary))
            created, create_store = _create_directory(
                bundle,
                bundle.paths.project_container,
            )
            child = bundle.paths.project_container / "unexpected"
            child.mkdir()
            intent, permit, apply_store = durable_intent(
                before_fingerprint=created.observation_fingerprint,
                expected_after_fingerprint=bundle.policy.policy_fingerprint,
                platform=DurabilityPlatform.WINDOWS,
            )

            with self.assertRaises(CutoverHostMutationError) as nonempty:
                bundle.adapter.apply_new_container_policy(
                    created_container=created,
                    intent=intent,
                    durable_permit=permit,
                )
            self.assertEqual(nonempty.exception.code, "acl_policy_rejected")
            self.assertTrue(child.is_dir())

            with self.assertRaises(CutoverHostMutationError) as unproven:
                bundle.adapter.apply_new_container_policy(
                    created_container=None,
                    intent=intent,
                    durable_permit=permit,
                )
            self.assertEqual(unproven.exception.code, "acl_policy_rejected")
            create_store.close()
            apply_store.close()

    def test_fixed_zones_inherit_exact_container_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = _bundle(Path(temporary))
            created, create_store = _create_directory(
                bundle,
                bundle.paths.project_container,
            )
            intent, permit, apply_store = durable_intent(
                before_fingerprint=created.observation_fingerprint,
                expected_after_fingerprint=bundle.policy.policy_fingerprint,
                platform=DurabilityPlatform.WINDOWS,
            )
            bundle.adapter.apply_new_container_policy(
                created_container=created,
                intent=intent,
                durable_permit=permit,
            )
            zone_stores = []
            for zone in _zone_paths(bundle.paths):
                _observation, store = _create_directory(bundle, zone)
                zone_stores.append(store)

            receipt = bundle.adapter.verify_fixed_zone_inheritance()

            self.assertIs(type(receipt), AclPostVerifyReceiptV1)
            self.assertIs(receipt.status, AclReceiptStatus.ACCEPTED)
            self.assertEqual(receipt.observed_objects, 8)
            create_store.close()
            apply_store.close()
            for store in zone_stores:
                store.close()


def _adapter(
    root: Path,
    *,
    source: Path,
    finance: Path,
):
    policy = AclCompatibilityPolicyV1.create(
        allowed_descriptor_fingerprints=(opaque_fingerprint(610),),
        maximum_objects=100,
    )
    return _adapter_with_policy(
        root,
        source=source,
        finance=finance,
        policy=policy,
    )


def _adapter_with_policy(
    root: Path,
    *,
    source: Path,
    finance: Path,
    policy: AclCompatibilityPolicyV1,
):
    profile = _profile(policy, operator=_current_operator_sid_fingerprint())
    return _create_test_windows_acl_adapter(
        root=root,
        marker=_marker(root),
        authorization=_authorization(profile),
        profile=profile,
        compatibility_policy=policy,
        role_paths=_paths(root, source, finance),
        observed_at_epoch=100,
    )


@dataclass(frozen=True)
class _Bundle:
    root: Path
    marker: Path
    policy: AclCompatibilityPolicyV1
    profile: CutoverProfileV1
    authorization: TestSandboxAuthorizationV1
    paths: _AclRolePaths
    adapter: object


def _bundle(root: Path) -> _Bundle:
    source = root / "source"
    finance = root / "finance"
    source.mkdir()
    finance.mkdir()
    marker = _marker(root)
    policy = AclCompatibilityPolicyV1.create(
        allowed_descriptor_fingerprints=(opaque_fingerprint(630),),
        maximum_objects=100,
    )
    profile = _profile(
        policy,
        operator=_current_operator_sid_fingerprint(),
    )
    authorization = _authorization(profile)
    paths = _paths(root, source, finance)
    adapter = _create_test_windows_acl_adapter(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        compatibility_policy=policy,
        role_paths=paths,
        observed_at_epoch=100,
    )
    return _Bundle(
        root,
        marker,
        policy,
        profile,
        authorization,
        paths,
        adapter,
    )


def _create_directory(bundle: _Bundle, target: Path):
    primitive = _create_test_directory_primitive(
        root=bundle.root,
        marker=bundle.marker,
        authorization=bundle.authorization,
        profile=bundle.profile,
        parent=target.parent,
        target=target,
        observed_at_epoch=100,
    )
    intent, permit, store = durable_intent(
        before_fingerprint=primitive.expectation.before_fingerprint,
        expected_after_fingerprint=(
            primitive.expectation.expected_after_fingerprint
        ),
        platform=DurabilityPlatform.WINDOWS,
    )
    observation = primitive.create_directory(
        intent=intent,
        durable_permit=permit,
    )
    return observation, store


def _zone_paths(paths: _AclRolePaths) -> tuple[Path, ...]:
    return (
        paths.runtimes,
        paths.local_data,
        paths.runtime_temp,
        paths.logs,
        paths.artifacts,
        paths.worktrees,
        paths.config,
        paths.operator_private,
    )


def _profile(
    policy: AclCompatibilityPolicyV1,
    *,
    operator: str,
) -> CutoverProfileV1:
    body = valid_profile_body()
    body["operator_fingerprint"] = operator
    body["acl_policy"]["policy_fingerprint"] = policy.policy_fingerprint
    return CutoverProfileV1.create(body)


def _authorization(
    profile: CutoverProfileV1,
) -> TestSandboxAuthorizationV1:
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=opaque_fingerprint(620),
        phase="execute",
        expires_at_epoch=200,
    )


def _marker(root: Path) -> Path:
    marker = root / ".codex-cutover-mutation-test-sandbox"
    marker.touch(exist_ok=True)
    return marker


def _paths(root: Path, source: Path, finance: Path) -> _AclRolePaths:
    container = root / "Container"
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


def _descriptor_fingerprints(paths: tuple[Path, ...]) -> tuple[str, ...]:
    security = WindowsSecurityApi()
    return tuple(
        security.capture(path, role=AclRole.SOURCE_TREE)
        .observation.canonical_sddl_fingerprint
        for path in paths
    )


if __name__ == "__main__":
    unittest.main()
