"""Linux-safe tests for pure contracts without Windows/NTFS claims."""

from __future__ import annotations

import unittest

import backend.cutover_host_mutation as contracts
from backend.cutover_host_mutation import (
    AclCompatibilityObservationV1,
    AclCompatibilityPolicyV1,
    AclDescriptorObservationV1,
    AclRole,
    FilesystemMutationKind,
    FilesystemMutationObservationV1,
)
from tests.cutover_contract_fixtures import opaque_fingerprint


class CutoverHostMutationPortableTests(unittest.TestCase):
    def test_importing_contracts_loads_no_windows_adapter(self) -> None:
        self.assertFalse(
            any(
                "windows" in name.lower() or "ntfs" in name.lower()
                for name in contracts.__all__
            )
        )

    def test_portable_acl_observation_claims_no_native_execution(self) -> None:
        policy = AclCompatibilityPolicyV1.create(
            allowed_descriptor_fingerprints=(opaque_fingerprint(1),),
            maximum_objects=2,
        )
        descriptor = AclDescriptorObservationV1.create(
            role=AclRole.SOURCE_TREE,
            object_identity_fingerprint=opaque_fingerprint(2),
            canonical_sddl_fingerprint=opaque_fingerprint(1),
            binary_descriptor_fingerprint=opaque_fingerprint(3),
            owner_fingerprint=opaque_fingerprint(4),
            group_fingerprint=opaque_fingerprint(5),
            dacl_fingerprint=opaque_fingerprint(6),
            dacl_protected=False,
            ace_count=1,
            inherited_ace_count=1,
            complete=True,
            content_observed=False,
        )
        observation = AclCompatibilityObservationV1.create(
            policy_fingerprint=policy.policy_fingerprint,
            source_root_identity_fingerprint=(
                descriptor.object_identity_fingerprint
            ),
            inventory_fingerprint=opaque_fingerprint(7),
            descriptors_observed=1,
            complete=True,
            content_observed=False,
        )

        self.assertTrue(observation.complete)
        self.assertFalse(observation.content_observed)
        self.assertNotIn("windows", repr(observation).lower())
        self.assertNotIn("ntfs", repr(observation).lower())

    def test_portable_no_replace_observation_requires_same_identity(self) -> None:
        observation = FilesystemMutationObservationV1.create(
            kind=FilesystemMutationKind.MOVE_OBJECT,
            journal_intent_fingerprint=opaque_fingerprint(10),
            journal_effect_fingerprint=opaque_fingerprint(11),
            source_identity_fingerprint=opaque_fingerprint(12),
            target_identity_fingerprint=opaque_fingerprint(12),
            parent_identity_fingerprint=opaque_fingerprint(13),
            volume_fingerprint=opaque_fingerprint(14),
            same_identity=True,
            no_replace=True,
            reparse_free=True,
        )

        self.assertTrue(observation.same_identity)
        self.assertTrue(observation.no_replace)
        self.assertNotIn("windows", repr(observation).lower())
        self.assertNotIn("ntfs", repr(observation).lower())


if __name__ == "__main__":
    unittest.main()
