from __future__ import annotations

import unittest
from dataclasses import replace

from backend.container_audit import (
    AuditObject,
    AuditObjectKind,
    AuditStatus,
    BoundedMetadataInventory,
    FilesystemEvidence,
    MetadataEntry,
    MetadataRole,
    run_container_audit,
)
from tests.container_audit_fixtures import (
    first_evidence,
    opaque,
    populated_audit_inputs,
    valid_audit_inputs,
    with_adapter,
)


class ContainerAuditFilesystemTests(unittest.TestCase):
    def assert_filesystem_fails(
        self,
        filesystem: FilesystemEvidence,
        *,
        populated: bool = False,
    ) -> None:
        factory = populated_audit_inputs if populated else valid_audit_inputs
        policy, adapters = factory()
        adapters = with_adapter(adapters, "filesystem", filesystem)

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_exact_nine_entry_inventory_rejects_shape_drift(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        entries = filesystem.entries
        main = entries[0]
        cases = {
            "missing": entries[:-1],
            "unexpected": (
                *entries[:-1],
                replace(entries[-1], name="Unexpected"),
            ),
            "wrong_case": (
                replace(main, name="Main"),
                *entries[1:],
            ),
            "wrong_kind": (
                replace(
                    main,
                    object=replace(
                        main.object,
                        kind=AuditObjectKind.FILE,
                    ),
                ),
                *entries[1:],
            ),
            "not_direct": (
                replace(main, direct_child_of_container=False),
                *entries[1:],
            ),
        }

        for name, changed_entries in cases.items():
            with self.subTest(name=name):
                self.assert_filesystem_fails(
                    replace(filesystem, entries=changed_entries)
                )

    def test_unreadable_alias_reparse_and_incomplete_fail(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        main = filesystem.entries[0]
        cases = {
            "container_unreadable": replace(
                filesystem,
                container=replace(
                    filesystem.container,
                    readable=False,
                ),
            ),
            "container_noncanonical": replace(
                filesystem,
                container=replace(
                    filesystem.container,
                    canonical=False,
                ),
            ),
            "entry_reparse": replace(
                filesystem,
                entries=(
                    replace(
                        main,
                        object=replace(
                            main.object,
                            has_reparse_component=True,
                        ),
                    ),
                    *filesystem.entries[1:],
                ),
            ),
            "entry_alias": replace(
                filesystem,
                entries=(
                    replace(main, object=filesystem.container),
                    *filesystem.entries[1:],
                ),
            ),
            "incomplete": replace(
                filesystem,
                inventory_complete=False,
            ),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_filesystem_fails(changed)

    def test_config_accepts_only_bounded_key_metadata(self) -> None:
        policy, adapters = populated_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        config = filesystem.config
        cases = {
            "wrong_root": replace(
                config,
                directory_identity=filesystem.container.identity,
            ),
            "wrong_filename": replace(config, filename=".env"),
            "unknown_key": replace(
                config,
                keys=("OPENAI_API_KEY",),
            ),
            "duplicate_key": replace(
                config,
                keys=(
                    "EMAIL_AGENT_LOG_LEVEL",
                    "EMAIL_AGENT_LOG_LEVEL",
                ),
            ),
            "oversize": replace(config, size_bytes=16 * 1024 + 1),
            "values_observed": replace(config, values_observed=True),
            "recursive": replace(config, direct_only=False),
            "incomplete": replace(config, inventory_complete=False),
            "unreadable": replace(
                config,
                settings_file=replace(
                    config.settings_file,
                    readable=False,
                ),
            ),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_filesystem_fails(
                    replace(filesystem, config=changed),
                    populated=True,
                )

    def test_log_and_artifact_metadata_is_bounded_and_content_free(
        self,
    ) -> None:
        policy, adapters = populated_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        log_entry = filesystem.logs.entries[0]
        artifact_entry = filesystem.artifacts.entries[0]
        cases = {
            "log_content": replace(
                filesystem,
                logs=replace(
                    filesystem.logs,
                    content_observed=True,
                ),
            ),
            "log_recursive": replace(
                filesystem,
                logs=replace(filesystem.logs, direct_only=False),
            ),
            "log_wrong_role": replace(
                filesystem,
                logs=replace(
                    filesystem.logs,
                    entries=(
                        replace(
                            log_entry,
                            role=MetadataRole.ARTIFACT,
                        ),
                    ),
                ),
            ),
            "log_wrong_root": replace(
                filesystem,
                logs=replace(
                    filesystem.logs,
                    root_identity=filesystem.container.identity,
                ),
            ),
            "log_directory": replace(
                filesystem,
                logs=replace(
                    filesystem.logs,
                    entries=(
                        replace(
                            log_entry,
                            object=replace(
                                log_entry.object,
                                kind=AuditObjectKind.DIRECTORY,
                            ),
                        ),
                    ),
                ),
            ),
            "artifact_wrong_role": replace(
                filesystem,
                artifacts=replace(
                    filesystem.artifacts,
                    entries=(
                        replace(
                            artifact_entry,
                            role=MetadataRole.CURRENT_LOG,
                        ),
                    ),
                ),
            ),
            "artifact_content": replace(
                filesystem,
                artifacts=replace(
                    filesystem.artifacts,
                    content_observed=True,
                ),
            ),
            "artifact_recursive": replace(
                filesystem,
                artifacts=replace(
                    filesystem.artifacts,
                    direct_only=False,
                ),
            ),
            "artifact_incomplete": replace(
                filesystem,
                artifacts=replace(
                    filesystem.artifacts,
                    inventory_complete=False,
                ),
            ),
            "artifact_negative_size": replace(
                filesystem,
                artifacts=replace(
                    filesystem.artifacts,
                    entries=(
                        replace(artifact_entry, size_bytes=-1),
                    ),
                ),
            ),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_filesystem_fails(changed, populated=True)

    def test_metadata_entry_caps_fail_before_cross_adapter_use(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        artifacts = tuple(
            MetadataEntry(
                object=AuditObject(
                    identity=opaque(2000 + index),
                    kind=AuditObjectKind.FILE,
                    volume_identity=policy.volume_identity,
                ),
                size_bytes=0,
                role=MetadataRole.ARTIFACT,
            )
            for index in range(257)
        )
        over_limit = replace(
            filesystem,
            artifacts=BoundedMetadataInventory(
                root_identity=filesystem.artifacts.root_identity,
                entries=artifacts,
                inventory_complete=True,
                direct_only=True,
                content_observed=False,
            ),
        )

        self.assert_filesystem_fails(over_limit)

    def test_log_role_distribution_is_fixed_and_bounded(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        rotated = tuple(
            MetadataEntry(
                object=AuditObject(
                    identity=opaque(3000 + index),
                    kind=AuditObjectKind.FILE,
                    volume_identity=policy.volume_identity,
                ),
                size_bytes=0,
                role=MetadataRole.ROTATED_LOG,
            )
            for index in range(3)
        )
        invalid = replace(
            filesystem,
            logs=replace(filesystem.logs, entries=rotated),
        )

        self.assert_filesystem_fails(invalid)

    def test_private_zones_accept_only_fixed_disabled_states(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        cases = {
            "operator_state": replace(
                filesystem,
                operator_private_state="enabled",
            ),
            "operator_content": replace(
                filesystem,
                operator_private_content_observed=True,
            ),
            "raw_vault": replace(
                filesystem,
                raw_vault_state="inside_container",
            ),
            "recovery": replace(
                filesystem,
                recovery_state="inside_container",
            ),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_filesystem_fails(changed)


if __name__ == "__main__":
    unittest.main()
