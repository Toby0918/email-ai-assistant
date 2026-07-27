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
    HostObjectKind,
    HostObjectObservationV1,
    VolumeObservationV1,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    MutatingReader,
    OrderedReader,
    object_observation,
    profile_for_role_names,
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

    def test_rejects_file_or_reparse_role_observations(self) -> None:
        profile = valid_profile()
        operation = opaque_fingerprint(201)
        parent = object_observation(
            1,
            parent_identity_fingerprint=opaque_fingerprint(401),
        )
        invalid_sources = (
            HostObjectObservationV1.create(
                volume_fingerprint=opaque_fingerprint(301),
                file_id_128=f"{2:032x}",
                object_kind=HostObjectKind.FILE,
                parent_identity_fingerprint=(
                    parent.object_identity_fingerprint
                ),
                normalized_name_fingerprint=opaque_fingerprint(322),
                filesystem_name="NTFS",
                file_attributes=0,
                reparse_tag=0,
                has_reparse_point=False,
            ),
            HostObjectObservationV1.create(
                volume_fingerprint=opaque_fingerprint(301),
                file_id_128=f"{2:032x}",
                object_kind=HostObjectKind.DIRECTORY,
                parent_identity_fingerprint=(
                    parent.object_identity_fingerprint
                ),
                normalized_name_fingerprint=opaque_fingerprint(322),
                filesystem_name="NTFS",
                file_attributes=16 | 1024,
                reparse_tag=0xA0000003,
                has_reparse_point=True,
            ),
        )

        for source in invalid_sources:
            with self.subTest(kind=source.object_kind):
                callbacks = _baseline_callbacks(parent, source)
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

    def test_rejects_profile_role_mismatch_and_tampered_sid(self) -> None:
        operation = opaque_fingerprint(201)
        parent = object_observation(
            1,
            parent_identity_fingerprint=opaque_fingerprint(401),
        )
        source = object_observation(
            2,
            parent_identity_fingerprint=parent.object_identity_fingerprint,
        )
        callbacks = _baseline_callbacks(parent, source)
        mismatched = profile_for_role_names(
            source_root=opaque_fingerprint(999),
            target_parent=opaque_fingerprint(321),
            finance_root=opaque_fingerprint(323),
            target_absence=opaque_fingerprint(404),
        )
        _assert_baseline_rejected(self, callbacks, mismatched, operation)

        profile = valid_profile()
        sid = callbacks.operator_sid()
        object.__setattr__(sid, "complete", False)
        object.__setattr__(callbacks, "operator_sid", lambda: sid)
        _assert_baseline_rejected(self, callbacks, profile, operation)

    def test_profile_snapshot_rejects_callback_role_swap(self) -> None:
        profile = valid_profile()
        alternate = profile_for_role_names(
            source_root=opaque_fingerprint(999),
            target_parent=opaque_fingerprint(321),
            finance_root=opaque_fingerprint(323),
            target_absence=opaque_fingerprint(404),
        )
        parent = object_observation(
            1,
            parent_identity_fingerprint=opaque_fingerprint(401),
        )
        source = HostObjectObservationV1.create(
            volume_fingerprint=opaque_fingerprint(301),
            file_id_128=f"{2:032x}",
            object_kind=HostObjectKind.DIRECTORY,
            parent_identity_fingerprint=parent.object_identity_fingerprint,
            normalized_name_fingerprint=opaque_fingerprint(999),
            filesystem_name="NTFS",
            file_attributes=16,
            reparse_tag=0,
            has_reparse_point=False,
        )
        callbacks = _baseline_callbacks(parent, source)
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

        _assert_baseline_rejected(
            self,
            callbacks,
            profile,
            opaque_fingerprint(201),
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


def _assert_baseline_rejected(
    case: unittest.TestCase,
    callbacks: RealHostBaselineCallbacks,
    profile: object,
    operation: str,
) -> None:
    with case.assertRaisesRegex(
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


def _baseline_callbacks(
    parent: HostObjectObservationV1,
    source: HostObjectObservationV1,
) -> RealHostBaselineCallbacks:
    finance = object_observation(
        3,
        parent_identity_fingerprint=parent.object_identity_fingerprint,
    )
    return RealHostBaselineCallbacks(
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
            BaselineAclRole.SOURCE_ROOT, source, 2, 502
        ),
        parent_acl=lambda: _acl(BaselineAclRole.PARENT, parent, 3, 503),
        finance_acl=lambda: _acl(
            BaselineAclRole.FINANCE, finance, 4, 504
        ),
    )


if __name__ == "__main__":
    unittest.main()
