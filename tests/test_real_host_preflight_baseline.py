"""TDD tests for the content-free real HostBaseline projection."""

from __future__ import annotations

import unittest

from backend.migration_evidence import HostBaseline
from backend.real_host_preflight import (
    AclBaselineObservationV1,
    BaselineAclRole,
    OperatorSidObservationV1,
    RealHostBaselineCallbacks,
    RealHostBaselineCollector,
    VolumeObservationV1,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    OrderedReader,
    object_observation,
    sandbox_authorization,
    valid_profile,
)


class RealHostBaselineCollectorTests(unittest.TestCase):
    def test_collects_eight_separate_readers_and_projects_hostbaseline(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        authorization = sandbox_authorization(
            profile,
            phase="host_baseline",
            operation_fingerprint=operation,
        )
        parent = object_observation(
            1,
            parent_identity_fingerprint=opaque_fingerprint(401),
        )
        source = object_observation(
            2,
            parent_identity_fingerprint=parent.object_identity_fingerprint,
        )
        finance = object_observation(
            3,
            parent_identity_fingerprint=parent.object_identity_fingerprint,
        )
        calls: list[str] = []
        callbacks = RealHostBaselineCallbacks(
            source_root=OrderedReader("source_root", source, calls),
            parent=OrderedReader("parent", parent, calls),
            finance=OrderedReader("finance", finance, calls),
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
            operator_sid=OrderedReader(
                "operator_sid",
                OperatorSidObservationV1.create(
                    sid_fingerprint=opaque_fingerprint(501),
                    complete=True,
                    content_observed=False,
                ),
                calls,
            ),
            source_acl=OrderedReader(
                "source_acl",
                _acl(BaselineAclRole.SOURCE_ROOT, source, 2, 502),
                calls,
            ),
            parent_acl=OrderedReader(
                "parent_acl",
                _acl(BaselineAclRole.PARENT, parent, 3, 503),
                calls,
            ),
            finance_acl=OrderedReader(
                "finance_acl",
                _acl(BaselineAclRole.FINANCE, finance, 4, 504),
                calls,
            ),
        )

        baseline = RealHostBaselineCollector(callbacks).collect(
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation,
            observed_at_epoch=OBSERVED_AT,
        )

        self.assertIs(type(baseline), HostBaseline)
        self.assertEqual(
            calls,
            [
                "source_root",
                "parent",
                "finance",
                "volume",
                "operator_sid",
                "source_acl",
                "parent_acl",
                "finance_acl",
            ],
        )
        self.assertEqual(baseline.acl_entry_count, 9)
        self.assertEqual(baseline.filesystem_name, "NTFS")
        self.assertEqual(baseline.drive_type, "fixed")
        self.assertTrue(baseline.evidence_complete)
        self.assertFalse(baseline.content_observed)
        self.assertNotIn(opaque_fingerprint(501), repr(baseline))

    def test_rejects_acl_count_outside_canonical_hostbaseline_range(
        self,
    ) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        parent = object_observation(
            1,
            parent_identity_fingerprint=opaque_fingerprint(401),
        )
        source = object_observation(
            2,
            parent_identity_fingerprint=parent.object_identity_fingerprint,
        )
        finance = object_observation(
            3,
            parent_identity_fingerprint=parent.object_identity_fingerprint,
        )
        callbacks = RealHostBaselineCallbacks(
            source_root=lambda: source,
            parent=lambda: parent,
            finance=lambda: finance,
            volume=lambda: VolumeObservationV1.create(
                volume_fingerprint=opaque_fingerprint(301),
                filesystem_name="NTFS",
                drive_type="fixed",
                complete=True,
            ),
            operator_sid=lambda: OperatorSidObservationV1.create(
                sid_fingerprint=opaque_fingerprint(501),
                complete=True,
                content_observed=False,
            ),
            source_acl=lambda: _acl(
                BaselineAclRole.SOURCE_ROOT, source, 2000, 502
            ),
            parent_acl=lambda: _acl(
                BaselineAclRole.PARENT, parent, 2000, 503
            ),
            finance_acl=lambda: _acl(
                BaselineAclRole.FINANCE, finance, 2000, 504
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "^REAL_HOST_BASELINE_REJECTED$",
        ):
            RealHostBaselineCollector(callbacks).collect(
                profile=profile,
                authorization=sandbox_authorization(
                    profile,
                    phase="host_baseline",
                    operation_fingerprint=operation,
                ),
                operation_fingerprint=operation,
                observed_at_epoch=OBSERVED_AT,
            )


def _acl(
    role: BaselineAclRole,
    observed_object: object,
    count: int,
    index: int,
) -> AclBaselineObservationV1:
    return AclBaselineObservationV1.create(
        role=role,
        object_identity_fingerprint=(
            observed_object.object_identity_fingerprint
        ),
        descriptor_fingerprint=opaque_fingerprint(index),
        entry_count=count,
        complete=True,
        content_observed=False,
    )


if __name__ == "__main__":
    unittest.main()
