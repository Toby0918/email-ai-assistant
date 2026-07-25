from __future__ import annotations

import unittest
from dataclasses import replace

from backend.container_audit import (
    AuditCounts,
    AuditObject,
    AuditObjectKind,
    AuditStatus,
    BoundedMetadataInventory,
    ContainerAuditResult,
    FilesystemEvidence,
    GitEvidence,
    MetadataEntry,
    MetadataRole,
    RuntimeEvidence,
    SqliteEvidence,
    VolumeEvidence,
    WorktreeEvidence,
    WorktreeRelationship,
    run_container_audit,
)
from tests.container_audit_fixtures import (
    SequenceAdapter,
    first_evidence,
    opaque,
    populated_audit_inputs,
)


class ContainerAuditPopulatedSuccessTests(unittest.TestCase):
    def test_complete_content_free_metadata_snapshot_passes(self) -> None:
        policy, adapters = populated_audit_inputs()

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(
            result,
            ContainerAuditResult(
                status=AuditStatus.PASSED,
                counts=AuditCounts(accepted=1, rejected=0),
            ),
        )

    def test_all_fixed_metadata_limits_can_coexist(self) -> None:
        policy, adapters = populated_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        git = first_evidence(adapters, "git")
        runtime = first_evidence(adapters, "runtime")
        sqlite = first_evidence(adapters, "sqlite")
        volume = first_evidence(adapters, "volume")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        self.assertIsInstance(git, GitEvidence)
        self.assertIsInstance(runtime, RuntimeEvidence)
        self.assertIsInstance(sqlite, SqliteEvidence)
        self.assertIsInstance(volume, VolumeEvidence)
        log_roles = (
            MetadataRole.CURRENT_LOG,
            MetadataRole.ROTATED_LOG,
            MetadataRole.ROTATED_LOG,
            MetadataRole.PID,
        )
        logs = tuple(
            MetadataEntry(
                object=AuditObject(
                    identity=opaque(8000 + index),
                    kind=AuditObjectKind.FILE,
                    volume_identity=policy.volume_identity,
                ),
                size_bytes=0,
                role=role,
            )
            for index, role in enumerate(log_roles)
        )
        artifacts = tuple(
            MetadataEntry(
                object=AuditObject(
                    identity=opaque(8100 + index),
                    kind=AuditObjectKind.FILE,
                    volume_identity=policy.volume_identity,
                ),
                size_bytes=0,
                role=MetadataRole.ARTIFACT,
            )
            for index in range(256)
        )
        relationships = tuple(
            WorktreeRelationship(
                approval_id=opaque(9000 + index),
                worktree=AuditObject(
                    identity=opaque(10000 + index),
                    kind=AuditObjectKind.DIRECTORY,
                    volume_identity=policy.volume_identity,
                ),
                common_directory_identity=git.common_directory.identity,
                direct_child_of_worktrees=True,
                linked=True,
                branch_attached=True,
                clean=True,
                content_observed=False,
            )
            for index in range(64)
        )
        changed_filesystem = replace(
            filesystem,
            logs=BoundedMetadataInventory(
                root_identity=filesystem.logs.root_identity,
                entries=logs,
                inventory_complete=True,
                direct_only=True,
                content_observed=False,
            ),
            artifacts=BoundedMetadataInventory(
                root_identity=filesystem.artifacts.root_identity,
                entries=artifacts,
                inventory_complete=True,
                direct_only=True,
                content_observed=False,
            ),
        )
        changed_worktrees = replace(
            first_evidence(adapters, "worktree"),
            relationships=relationships,
        )
        objects = (
            filesystem.container,
            *(entry.object for entry in filesystem.entries),
            *(entry.object for entry in logs),
            *(entry.object for entry in artifacts),
            git.common_directory,
            *(item.worktree for item in relationships),
            runtime.pinned_runtime,
            runtime.executable,
            filesystem.config.settings_file,
            sqlite.database,
        )
        changed_volume = replace(
            volume,
            bound_identities=tuple(
                sorted(item.identity for item in objects)
            ),
        )
        changed_policy = replace(
            policy,
            approved_worktrees=tuple(
                item.approval_id for item in relationships
            ),
        )
        changed_adapters = replace(
            adapters,
            filesystem=SequenceAdapter(
                changed_filesystem,
                changed_filesystem,
            ),
            volume=SequenceAdapter(changed_volume, changed_volume),
            worktree=SequenceAdapter(
                changed_worktrees,
                changed_worktrees,
            ),
        )

        result = run_container_audit(
            policy=changed_policy,
            adapters=changed_adapters,
        )

        self.assertEqual(result.status, AuditStatus.PASSED)


if __name__ == "__main__":
    unittest.main()
