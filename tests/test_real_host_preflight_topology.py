"""TDD tests for the Issue #53 two-pass topology preflight."""

from __future__ import annotations

import unittest

from backend.real_host_preflight import (
    CurrentTopologyCallbacks,
    CurrentTopologyPreflightReceiptV1,
    HostCheckKind,
    OpaqueHostCheckV1,
    VolumeObservationV1,
    run_current_topology_preflight,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    OrderedReader,
    sandbox_authorization,
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


if __name__ == "__main__":
    unittest.main()
