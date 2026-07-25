from __future__ import annotations

import unittest
from dataclasses import replace

from backend.container_audit import (
    AclEvidence,
    AuditObjectKind,
    AuditStatus,
    GitEvidence,
    RuntimeEvidence,
    VolumeEvidence,
    WorktreeEvidence,
    run_container_audit,
)
from tests.container_audit_fixtures import (
    first_evidence,
    opaque,
    populated_audit_inputs,
    valid_audit_inputs,
    with_adapter,
)


class ContainerAuditSystemTests(unittest.TestCase):
    def assert_adapter_fails(
        self,
        name: str,
        evidence: object,
        *,
        populated: bool = False,
    ) -> None:
        factory = populated_audit_inputs if populated else valid_audit_inputs
        policy, adapters = factory()
        adapters = with_adapter(adapters, name, evidence)

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_acl_requires_exact_scoped_identities_and_fingerprints(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        acl = first_evidence(adapters, "acl")
        self.assertIsInstance(acl, AclEvidence)
        cases = {
            "container_identity": replace(
                acl,
                container_identity=opaque(4000),
            ),
            "container_fingerprint": replace(
                acl,
                container_fingerprint=opaque(4001),
            ),
            "operator_identity": replace(
                acl,
                operator_private_identity=opaque(4002),
            ),
            "operator_fingerprint": replace(
                acl,
                operator_private_fingerprint=opaque(4003),
            ),
            "incomplete": replace(acl, inventory_complete=False),
            "wrong_schema_type": replace(acl, schema_version=True),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_adapter_fails("acl", changed)

    def test_volume_requires_fixed_ntfs_identity_and_exact_bindings(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        volume = first_evidence(adapters, "volume")
        self.assertIsInstance(volume, VolumeEvidence)
        cases = {
            "identity": replace(
                volume,
                volume_identity=opaque(4100),
            ),
            "filesystem": replace(volume, filesystem_name="ReFS"),
            "drive": replace(volume, drive_type="removable"),
            "missing_binding": replace(
                volume,
                bound_identities=volume.bound_identities[:-1],
            ),
            "extra_binding": replace(
                volume,
                bound_identities=tuple(
                    sorted((*volume.bound_identities, opaque(4101)))
                ),
            ),
            "duplicate_binding": replace(
                volume,
                bound_identities=(
                    *volume.bound_identities,
                    volume.bound_identities[-1],
                ),
            ),
            "unsorted_binding": replace(
                volume,
                bound_identities=tuple(
                    reversed(volume.bound_identities)
                ),
            ),
            "incomplete": replace(volume, inventory_complete=False),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_adapter_fails("volume", changed)

    def test_git_requires_one_main_root_and_one_common_directory(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        git = first_evidence(adapters, "git")
        self.assertIsInstance(git, GitEvidence)
        roots = {entry.name: entry.object for entry in filesystem.entries}
        cases = {
            "repository_count": replace(git, repository_count=2),
            "common_count": replace(git, common_directory_count=0),
            "wrong_repository": replace(
                git,
                repository=roots["Runtimes"],
            ),
            "wrong_repository_name": replace(
                git,
                repository_name="repo",
            ),
            "wrong_common_name": replace(
                git,
                common_directory_name="gitdir",
            ),
            "outside_repository": replace(
                git,
                common_directory_inside_repository=False,
            ),
            "nested_common_directory": replace(
                git,
                common_directory_direct_child_of_repository=False,
            ),
            "common_reparse": replace(
                git,
                common_directory=replace(
                    git.common_directory,
                    has_reparse_component=True,
                ),
            ),
            "content": replace(git, content_observed=True),
            "incomplete": replace(git, inventory_complete=False),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_adapter_fails("git", changed)

    def test_approved_worktree_relationships_fail_closed(self) -> None:
        policy, adapters = populated_audit_inputs()
        worktrees = first_evidence(adapters, "worktree")
        git = first_evidence(adapters, "git")
        self.assertIsInstance(worktrees, WorktreeEvidence)
        self.assertIsInstance(git, GitEvidence)
        relationship = worktrees.relationships[0]
        cases = {
            "missing": replace(worktrees, relationships=()),
            "wrong_root": replace(
                worktrees,
                worktrees_root_identity=opaque(4200),
            ),
            "main_count": replace(worktrees, main_worktree_count=2),
            "wrong_common": replace(
                worktrees,
                relationships=(
                    replace(
                        relationship,
                        common_directory_identity=opaque(4201),
                    ),
                ),
            ),
            "not_direct": replace(
                worktrees,
                relationships=(
                    replace(
                        relationship,
                        direct_child_of_worktrees=False,
                    ),
                ),
            ),
            "not_linked": replace(
                worktrees,
                relationships=(
                    replace(relationship, linked=False),
                ),
            ),
            "detached": replace(
                worktrees,
                relationships=(
                    replace(relationship, branch_attached=False),
                ),
            ),
            "dirty": replace(
                worktrees,
                relationships=(
                    replace(relationship, clean=False),
                ),
            ),
            "content": replace(
                worktrees,
                relationships=(
                    replace(relationship, content_observed=True),
                ),
            ),
            "incomplete": replace(
                worktrees,
                inventory_complete=False,
            ),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_adapter_fails(
                    "worktree",
                    changed,
                    populated=True,
                )

    def test_reviewed_policy_can_allow_a_dirty_approved_worktree(
        self,
    ) -> None:
        policy, adapters = populated_audit_inputs()
        worktrees = first_evidence(adapters, "worktree")
        self.assertIsInstance(worktrees, WorktreeEvidence)
        relationship = replace(worktrees.relationships[0], clean=False)
        adapters = with_adapter(
            adapters,
            "worktree",
            replace(worktrees, relationships=(relationship,)),
        )

        result = run_container_audit(
            policy=replace(policy, require_clean_worktrees=False),
            adapters=adapters,
        )

        self.assertEqual(result.status, AuditStatus.PASSED)

    def test_two_approvals_cannot_alias_one_worktree_identity(
        self,
    ) -> None:
        policy, adapters = populated_audit_inputs()
        worktrees = first_evidence(adapters, "worktree")
        self.assertIsInstance(worktrees, WorktreeEvidence)
        first = worktrees.relationships[0]
        second_approval = opaque(4300)
        duplicate = replace(first, approval_id=second_approval)
        changed = replace(
            worktrees,
            relationships=(first, duplicate),
        )
        adapters = with_adapter(adapters, "worktree", changed)
        approvals = tuple(
            sorted((first.approval_id, second_approval))
        )

        result = run_container_audit(
            policy=replace(policy, approved_worktrees=approvals),
            adapters=adapters,
        )

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_runtime_requires_pinned_objects_versions_and_locations(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        runtime = first_evidence(adapters, "runtime")
        self.assertIsInstance(runtime, RuntimeEvidence)
        cases = {
            "count": replace(runtime, runtime_count=2),
            "python": replace(runtime, python_version="3.13.0"),
            "sqlite": replace(runtime, sqlite_version="3.51.0"),
            "pinned_unreadable": replace(
                runtime,
                pinned_runtime=replace(
                    runtime.pinned_runtime,
                    readable=False,
                ),
            ),
            "pinned_reparse": replace(
                runtime,
                pinned_runtime=replace(
                    runtime.pinned_runtime,
                    has_reparse_component=True,
                ),
            ),
            "executable_kind": replace(
                runtime,
                executable=replace(
                    runtime.executable,
                    kind=AuditObjectKind.DIRECTORY,
                ),
            ),
            "executable_location": replace(
                runtime,
                executable_location_exact=False,
            ),
            "pinned_location": replace(
                runtime,
                pinned_runtime_location_exact=False,
            ),
            "incomplete": replace(runtime, inventory_complete=False),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_adapter_fails("runtime", changed)


if __name__ == "__main__":
    unittest.main()
