"""Portable closed contracts for Issue #55 host mutation primitives."""

from __future__ import annotations

import json
import unittest

from backend.cutover_host_mutation import (
    AclApplyReceiptV1,
    AclBaselineReceiptV1,
    AclCompatibilityObservationV1,
    AclCompatibilityPolicyV1,
    AclCompatibilityReceiptV1,
    AclDescriptorObservationV1,
    AclFailureCode,
    AclPostVerifyReceiptV1,
    AclReceiptStatus,
    AclRole,
    FilesystemMutationKind,
    FilesystemMutationObservationV1,
)
from backend.cutover_host_mutation.errors import CutoverHostMutationError
from tests.cutover_contract_fixtures import opaque_fingerprint


class CutoverHostMutationContractTests(unittest.TestCase):
    def test_acl_descriptor_observation_is_closed_and_content_free(self) -> None:
        observation = _descriptor(AclRole.PARENT, 1)

        self.assertEqual(observation.schema_version, 1)
        self.assertEqual(observation.role, AclRole.PARENT)
        self.assertTrue(observation.complete)
        self.assertFalse(observation.content_observed)
        self.assertEqual(len(observation.observation_fingerprint), 64)
        self.assertNotIn("path", repr(observation).lower())
        self.assertNotIn("sid", repr(observation).lower())
        self.assertNotIn("sddl", repr(observation).lower())

        with self.assertRaises(TypeError):
            AclDescriptorObservationV1()
        with self.assertRaises(CutoverHostMutationError) as raised:
            AclDescriptorObservationV1.create(
                **{
                    **_descriptor_arguments(AclRole.PARENT, 1),
                    "unexpected": "field",
                }
            )
        self.assertEqual(raised.exception.code, "acl_contract_invalid")

    def test_compatibility_policy_and_observation_are_canonical(self) -> None:
        allowed = (opaque_fingerprint(30), opaque_fingerprint(31))
        policy = AclCompatibilityPolicyV1.create(
            allowed_descriptor_fingerprints=allowed,
            maximum_objects=12,
        )
        observation = AclCompatibilityObservationV1.create(
            policy_fingerprint=policy.policy_fingerprint,
            source_root_identity_fingerprint=opaque_fingerprint(32),
            inventory_fingerprint=opaque_fingerprint(33),
            descriptors_observed=4,
            complete=True,
            content_observed=False,
        )

        self.assertEqual(
            policy.allowed_descriptor_fingerprints,
            tuple(sorted(allowed)),
        )
        self.assertEqual(observation.descriptors_observed, 4)
        self.assertEqual(
            json.loads(policy.to_canonical_json())["maximum_objects"],
            12,
        )
        with self.assertRaises(CutoverHostMutationError):
            AclCompatibilityPolicyV1.create(
                allowed_descriptor_fingerprints=(allowed[0], allowed[0]),
                maximum_objects=12,
            )

    def test_four_acl_receipts_have_exact_closed_schemas(self) -> None:
        receipt_types = (
            AclBaselineReceiptV1,
            AclCompatibilityReceiptV1,
            AclApplyReceiptV1,
            AclPostVerifyReceiptV1,
        )
        for index, receipt_type in enumerate(receipt_types, start=40):
            with self.subTest(receipt_type=receipt_type.__name__):
                receipt = receipt_type.create(
                    status=AclReceiptStatus.ACCEPTED,
                    failure_code=AclFailureCode.NONE,
                    profile_fingerprint=opaque_fingerprint(index),
                    authorization_fingerprint=opaque_fingerprint(index + 10),
                    policy_fingerprint=opaque_fingerprint(index + 20),
                    observation_fingerprint=opaque_fingerprint(index + 30),
                    accepted=1,
                    rejected=0,
                    observed_objects=index,
                )
                mapping = receipt.to_mapping()

                self.assertEqual(mapping["receipt_type"], receipt_type.__name__)
                self.assertEqual(set(mapping), _receipt_keys())
                self.assertEqual(len(mapping["receipt_fingerprint"]), 64)
                self.assertNotIn("path", repr(receipt).lower())
                self.assertEqual(
                    type(receipt).from_json(receipt.to_canonical_json()),
                    receipt,
                )
                hostile = {**mapping, "path": "forbidden"}
                with self.assertRaises(CutoverHostMutationError):
                    type(receipt).from_mapping(hostile)

    def test_receipt_status_and_failure_code_relationship_is_fixed(self) -> None:
        common = {
            "profile_fingerprint": opaque_fingerprint(80),
            "authorization_fingerprint": opaque_fingerprint(81),
            "policy_fingerprint": opaque_fingerprint(82),
            "observation_fingerprint": opaque_fingerprint(83),
            "observed_objects": 1,
        }
        with self.assertRaises(CutoverHostMutationError):
            AclApplyReceiptV1.create(
                status=AclReceiptStatus.ACCEPTED,
                failure_code=AclFailureCode.POLICY_REJECTED,
                accepted=1,
                rejected=0,
                **common,
            )
        with self.assertRaises(CutoverHostMutationError):
            AclApplyReceiptV1.create(
                status=AclReceiptStatus.REJECTED,
                failure_code=AclFailureCode.NONE,
                accepted=0,
                rejected=1,
                **common,
            )

    def test_filesystem_observation_proves_no_replace_and_identity(self) -> None:
        observation = FilesystemMutationObservationV1.create(
            kind=FilesystemMutationKind.PUBLISH_FILE,
            journal_intent_fingerprint=opaque_fingerprint(90),
            journal_effect_fingerprint=opaque_fingerprint(91),
            source_identity_fingerprint=opaque_fingerprint(92),
            target_identity_fingerprint=opaque_fingerprint(92),
            parent_identity_fingerprint=opaque_fingerprint(93),
            volume_fingerprint=opaque_fingerprint(94),
            same_identity=True,
            no_replace=True,
            reparse_free=True,
        )

        self.assertEqual(
            observation.source_identity_fingerprint,
            observation.target_identity_fingerprint,
        )
        self.assertTrue(observation.same_identity)
        self.assertTrue(observation.no_replace)
        self.assertNotIn("path", repr(observation).lower())

        with self.assertRaises(CutoverHostMutationError):
            FilesystemMutationObservationV1.create(
                kind=FilesystemMutationKind.PUBLISH_FILE,
                journal_intent_fingerprint=opaque_fingerprint(90),
                journal_effect_fingerprint=opaque_fingerprint(91),
                source_identity_fingerprint=opaque_fingerprint(92),
                target_identity_fingerprint=opaque_fingerprint(95),
                parent_identity_fingerprint=opaque_fingerprint(93),
                volume_fingerprint=opaque_fingerprint(94),
                same_identity=True,
                no_replace=True,
                reparse_free=True,
            )


def _descriptor(role: AclRole, index: int) -> AclDescriptorObservationV1:
    return AclDescriptorObservationV1.create(
        **_descriptor_arguments(role, index)
    )


def _descriptor_arguments(role: AclRole, index: int) -> dict[str, object]:
    return {
        "role": role,
        "object_identity_fingerprint": opaque_fingerprint(index),
        "canonical_sddl_fingerprint": opaque_fingerprint(index + 1),
        "binary_descriptor_fingerprint": opaque_fingerprint(index + 2),
        "owner_fingerprint": opaque_fingerprint(index + 3),
        "group_fingerprint": opaque_fingerprint(index + 4),
        "dacl_fingerprint": opaque_fingerprint(index + 5),
        "dacl_protected": False,
        "ace_count": 3,
        "inherited_ace_count": 3,
        "complete": True,
        "content_observed": False,
    }


def _receipt_keys() -> set[str]:
    return {
        "schema_version",
        "receipt_type",
        "status",
        "failure_code",
        "profile_fingerprint",
        "authorization_fingerprint",
        "policy_fingerprint",
        "observation_fingerprint",
        "accepted",
        "rejected",
        "observed_objects",
        "receipt_fingerprint",
    }


if __name__ == "__main__":
    unittest.main()
