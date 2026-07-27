"""TDD tests for the Issue #53 two-pass topology preflight."""

from __future__ import annotations

import unittest

from backend.real_host_preflight import (
    CurrentTopologyCallbacks,
    CurrentTopologyPreflightReceiptV1,
    HostCheckKind,
    MissingHostObjectObservationV1,
    OpaqueHostCheckV1,
    VolumeObservationV1,
    run_current_topology_preflight,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    MutatingReader,
    OrderedReader,
    profile_for_role_names,
    sandbox_authorization,
    topology_callbacks,
    topology_components,
    valid_profile,
)


class CurrentTopologyPreflightTests(unittest.TestCase):
    def test_named_receipt_requires_validated_envelope_construction(
        self,
    ) -> None:
        with self.assertRaises(TypeError):
            CurrentTopologyPreflightReceiptV1(object())

    def test_calls_all_seven_readers_twice_and_issues_canonical_receipt(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        authorization = sandbox_authorization(
            profile,
            operation_fingerprint=operation,
        )
        components = topology_components()
        calls: list[str] = []
        callbacks = CurrentTopologyCallbacks(
            source_root=OrderedReader(
                "source_root", components["source_root"], calls
            ),
            target_parent=OrderedReader(
                "target_parent", components["target_parent"], calls
            ),
            finance_root=OrderedReader(
                "finance_root", components["finance_root"], calls
            ),
            target_absence=OrderedReader(
                "target_absence", components["target_absence"], calls
            ),
            git=OrderedReader(
                "git",
                OpaqueHostCheckV1.create(
                    kind=HostCheckKind.GIT,
                    fingerprint=opaque_fingerprint(405),
                    complete=True,
                    content_observed=False,
                ),
                calls,
            ),
            acl=OrderedReader(
                "acl",
                OpaqueHostCheckV1.create(
                    kind=HostCheckKind.ACL,
                    fingerprint=opaque_fingerprint(406),
                    complete=True,
                    content_observed=False,
                ),
                calls,
            ),
            volume=OrderedReader(
                "volume",
                VolumeObservationV1.create(
                    volume_fingerprint=opaque_fingerprint(301),
                    filesystem_name="NTFS",
                    drive_type="fixed",
                    complete=True,
                ),
                calls,
            ),
        )

        receipt = run_current_topology_preflight(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            policy_fingerprint=opaque_fingerprint(407),
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )

        self.assertIs(type(receipt), CurrentTopologyPreflightReceiptV1)
        self.assertEqual(
            calls,
            [
                "source_root",
                "target_parent",
                "finance_root",
                "target_absence",
                "git",
                "acl",
                "volume",
            ]
            * 2,
        )
        mapping = receipt.to_mapping()
        self.assertEqual(mapping["status"], "PREFLIGHT_ACCEPTED")
        self.assertEqual(
            mapping["details"],
            {"observation_kind": "repeated_current_topology"},
        )
        self.assertEqual(
            mapping["counts"],
            {"accepted": 1, "rejected": 0},
        )
        self.assertLessEqual(
            mapping["validity"]["expires_at_epoch"]
            - mapping["validity"]["issued_at_epoch"],
            60,
        )

    def test_tampered_callback_evidence_is_rejected_before_receipt(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        mutations = (
            ("target_absence", "present", True),
            ("git", "complete", False),
            ("volume", "drive_type", "remote"),
            ("source_root", "file_attributes", 16 | 1024),
        )

        for role, field, value in mutations:
            with self.subTest(role=role, field=field):
                callbacks = _callbacks_with_mutation(role, field, value)
                with self.assertRaisesRegex(
                    ValueError,
                    "^REAL_HOST_TOPOLOGY_REJECTED$",
                ):
                    run_current_topology_preflight(
                        profile=profile,
                        authorization=sandbox_authorization(
                            profile,
                            operation_fingerprint=operation,
                        ),
                        operation_fingerprint=operation,
                        policy_fingerprint=opaque_fingerprint(407),
                        observed_at_epoch=OBSERVED_AT,
                        callbacks=callbacks,
                    )

    def test_profile_role_binding_rejects_decoy_target_absence(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        components = topology_components()
        parent = components["target_parent"]
        components["target_absence"] = MissingHostObjectObservationV1.create(
            parent_identity_fingerprint=(
                parent.object_identity_fingerprint
            ),
            volume_fingerprint=opaque_fingerprint(301),
            normalized_name_fingerprint=opaque_fingerprint(999),
            filesystem_name="NTFS",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_TOPOLOGY_REJECTED$",
        ):
            run_current_topology_preflight(
                profile=profile,
                authorization=sandbox_authorization(
                    profile,
                    operation_fingerprint=operation,
                ),
                operation_fingerprint=operation,
                policy_fingerprint=opaque_fingerprint(407),
                observed_at_epoch=OBSERVED_AT,
                callbacks=topology_callbacks([], components=components),
            )

    def test_profile_snapshot_rejects_callback_role_swap(self) -> None:
        profile = valid_profile()
        alternate = profile_for_role_names(
            source_root=opaque_fingerprint(322),
            target_parent=opaque_fingerprint(321),
            finance_root=opaque_fingerprint(323),
            target_absence=opaque_fingerprint(999),
        )
        components = topology_components()
        parent = components["target_parent"]
        components["target_absence"] = MissingHostObjectObservationV1.create(
            parent_identity_fingerprint=parent.object_identity_fingerprint,
            volume_fingerprint=opaque_fingerprint(301),
            normalized_name_fingerprint=opaque_fingerprint(999),
            filesystem_name="NTFS",
        )
        callbacks = topology_callbacks([], components=components)
        object.__setattr__(
            callbacks,
            "source_root",
            MutatingReader(
                profile,
                "role_selections",
                alternate.role_selections,
                callbacks.source_root,
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_TOPOLOGY_REJECTED$",
        ):
            run_current_topology_preflight(
                profile=profile,
                authorization=sandbox_authorization(profile),
                operation_fingerprint=opaque_fingerprint(201),
                policy_fingerprint=opaque_fingerprint(407),
                observed_at_epoch=OBSERVED_AT,
                callbacks=callbacks,
            )

    def test_receipt_uses_profile_snapshot_after_callback_mutation(self) -> None:
        profile = valid_profile()
        original_fingerprint = profile.profile_fingerprint
        alternate = profile_for_role_names(
            source_root=opaque_fingerprint(322),
            target_parent=opaque_fingerprint(321),
            finance_root=opaque_fingerprint(323),
            target_absence=opaque_fingerprint(999),
        )
        authorization = sandbox_authorization(profile)
        callbacks = topology_callbacks([])
        object.__setattr__(
            callbacks,
            "source_root",
            MutatingReader(
                profile,
                "profile_fingerprint",
                alternate.profile_fingerprint,
                callbacks.source_root,
            ),
        )

        receipt = run_current_topology_preflight(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=opaque_fingerprint(201),
            policy_fingerprint=opaque_fingerprint(407),
            observed_at_epoch=OBSERVED_AT,
            callbacks=callbacks,
        )

        self.assertEqual(
            receipt.to_mapping()["profile_fingerprint"],
            original_fingerprint,
        )


def _callbacks_with_mutation(
    role: str,
    field: str,
    value: object,
) -> CurrentTopologyCallbacks:
    components = topology_components()
    checks = {
        "git": OpaqueHostCheckV1.create(
            kind=HostCheckKind.GIT,
            fingerprint=opaque_fingerprint(405),
            complete=True,
            content_observed=False,
        ),
        "acl": OpaqueHostCheckV1.create(
            kind=HostCheckKind.ACL,
            fingerprint=opaque_fingerprint(406),
            complete=True,
            content_observed=False,
        ),
        "volume": VolumeObservationV1.create(
            volume_fingerprint=opaque_fingerprint(301),
            filesystem_name="NTFS",
            drive_type="fixed",
            complete=True,
        ),
    }
    selected = components if role in components else checks
    object.__setattr__(selected[role], field, value)
    calls: list[str] = []
    return CurrentTopologyCallbacks(
        source_root=OrderedReader(
            "source_root", components["source_root"], calls
        ),
        target_parent=OrderedReader(
            "target_parent", components["target_parent"], calls
        ),
        finance_root=OrderedReader(
            "finance_root", components["finance_root"], calls
        ),
        target_absence=OrderedReader(
            "target_absence", components["target_absence"], calls
        ),
        git=OrderedReader("git", checks["git"], calls),
        acl=OrderedReader("acl", checks["acl"], calls),
        volume=OrderedReader("volume", checks["volume"], calls),
    )


if __name__ == "__main__":
    unittest.main()
