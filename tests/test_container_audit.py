from __future__ import annotations

import unittest
from dataclasses import replace

from backend.container_audit import (
    AuditCounts,
    AuditStatus,
    BoundedMetadataInventory,
    ContainerAuditResult,
    FilesystemEvidence,
    GitEvidence,
    MetadataEntry,
    MetadataRole,
    RuntimeEvidence,
    VolumeEvidence,
    run_container_audit,
)
from tests.container_audit_fixtures import (
    first_evidence,
    valid_audit_inputs,
    with_adapter,
)


class AlwaysEqual:
    def __eq__(self, other: object) -> bool:
        return True


class ContainerAuditTests(unittest.TestCase):
    def test_valid_evidence_passes_after_two_stable_reads(self) -> None:
        policy, adapters = valid_audit_inputs()

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(
            result,
            ContainerAuditResult(
                status=AuditStatus.PASSED,
                counts=AuditCounts(accepted=1, rejected=0),
            ),
        )
        for adapter in (
            adapters.filesystem,
            adapters.volume,
            adapters.acl,
            adapters.git,
            adapters.worktree,
            adapters.runtime,
            adapters.sqlite,
        ):
            self.assertEqual(adapter.calls, 2)

    def test_container_and_top_level_alias_identity_fail_closed(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        git = first_evidence(adapters, "git")
        volume = first_evidence(adapters, "volume")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        self.assertIsInstance(git, GitEvidence)
        self.assertIsInstance(volume, VolumeEvidence)
        old_main = filesystem.entries[0].object
        aliased_entries = (
            replace(
                filesystem.entries[0],
                object=filesystem.container,
            ),
            *filesystem.entries[1:],
        )
        adapters = with_adapter(
            adapters,
            "filesystem",
            replace(filesystem, entries=aliased_entries),
        )
        adapters = with_adapter(
            adapters,
            "git",
            replace(git, repository=filesystem.container),
        )
        adapters = with_adapter(
            adapters,
            "volume",
            replace(
                volume,
                bound_identities=tuple(
                    identity
                    for identity in volume.bound_identities
                    if identity != old_main.identity
                ),
            ),
        )

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_zone_metadata_cannot_alias_a_top_level_directory(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        logs_root = next(
            entry.object
            for entry in filesystem.entries
            if entry.name == "Logs"
        )
        aliased_logs = BoundedMetadataInventory(
            root_identity=logs_root.identity,
            entries=(
                MetadataEntry(
                    object=logs_root,
                    size_bytes=0,
                    role=MetadataRole.CURRENT_LOG,
                ),
            ),
            inventory_complete=True,
            direct_only=True,
            content_observed=False,
        )
        adapters = with_adapter(
            adapters,
            "filesystem",
            replace(filesystem, logs=aliased_logs),
        )

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_non_string_runtime_version_cannot_compare_as_equal(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        runtime = first_evidence(adapters, "runtime")
        self.assertIsInstance(runtime, RuntimeEvidence)
        adapters = with_adapter(
            adapters,
            "runtime",
            replace(runtime, python_version=AlwaysEqual()),
        )

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_unhashable_config_key_is_a_fixed_failure(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        malformed = replace(
            filesystem,
            config=replace(filesystem.config, keys=([],)),
        )
        adapters = with_adapter(adapters, "filesystem", malformed)

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
