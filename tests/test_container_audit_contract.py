from __future__ import annotations

import inspect
import unittest
from dataclasses import FrozenInstanceError, MISSING, fields

from backend.container_audit import (
    AclEvidence,
    AuditObject,
    AuditObjectKind,
    BoundedMetadataInventory,
    ConfigMetadata,
    ContainerAuditAdapters,
    FilesystemEvidence,
    GitEvidence,
    MetadataEntry,
    RuntimeEvidence,
    SqliteEvidence,
    TopLevelEntry,
    TrustedAuditPolicy,
    VolumeEvidence,
    WorktreeEvidence,
    WorktreeRelationship,
    run_container_audit,
)
from tests.container_audit_fixtures import valid_audit_inputs


EVIDENCE_TYPES = (
    AuditObject,
    TopLevelEntry,
    MetadataEntry,
    BoundedMetadataInventory,
    ConfigMetadata,
    FilesystemEvidence,
    AclEvidence,
    VolumeEvidence,
    GitEvidence,
    WorktreeRelationship,
    WorktreeEvidence,
    RuntimeEvidence,
    SqliteEvidence,
)


class ContainerAuditContractTests(unittest.TestCase):
    def test_manual_entrypoint_is_keyword_only_and_has_no_default(
        self,
    ) -> None:
        signature = inspect.signature(run_container_audit)

        self.assertEqual(tuple(signature.parameters), ("policy", "adapters"))
        for parameter in signature.parameters.values():
            self.assertIs(
                parameter.kind,
                inspect.Parameter.KEYWORD_ONLY,
            )
            self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_adapter_bundle_is_exactly_seven_injected_callables(
        self,
    ) -> None:
        adapter_fields = fields(ContainerAuditAdapters)

        self.assertEqual(
            tuple(field.name for field in adapter_fields),
            (
                "filesystem",
                "acl",
                "volume",
                "git",
                "worktree",
                "runtime",
                "sqlite",
            ),
        )
        for field in adapter_fields:
            self.assertIs(field.default, MISSING)
            self.assertIs(field.default_factory, MISSING)

    def test_policy_and_evidence_are_frozen_slots_and_repr_redacted(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        values = (
            policy,
            adapters,
            adapters.filesystem.first,
            adapters.acl.first,
            adapters.volume.first,
            adapters.git.first,
            adapters.worktree.first,
            adapters.runtime.first,
            adapters.sqlite.first,
        )
        for value in values:
            with self.subTest(type=type(value).__name__):
                self.assertNotIn("000000000000", repr(value))
                self.assertTrue(hasattr(type(value), "__slots__"))
                first_field = fields(value)[0].name
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, first_field, None)

        for evidence_type in EVIDENCE_TYPES:
            with self.subTest(evidence=evidence_type.__name__):
                self.assertFalse(
                    evidence_type.__dataclass_params__.repr
                )
                self.assertTrue(
                    evidence_type.__dataclass_params__.frozen
                )

    def test_evidence_objects_cannot_carry_path_or_reader_capability(
        self,
    ) -> None:
        forbidden = {
            "account",
            "client",
            "exception",
            "handle",
            "path",
            "reader",
            "secret",
            "sid",
        }

        for evidence_type in EVIDENCE_TYPES:
            names = {field.name for field in fields(evidence_type)}
            with self.subTest(evidence=evidence_type.__name__):
                self.assertTrue(names.isdisjoint(forbidden))

        malformed = AuditObject(
            identity="private-identity-canary",
            kind=AuditObjectKind.FILE,
            volume_identity="private-volume-canary",
        )
        self.assertNotIn("canary", repr(malformed))


if __name__ == "__main__":
    unittest.main()
