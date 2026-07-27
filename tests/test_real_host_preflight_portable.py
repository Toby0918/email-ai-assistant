"""Portable contracts for the Issue #53 read-only preflight."""

from __future__ import annotations

import unittest

from backend.real_host_preflight import (
    CurrentTopologyObservationV1,
    HostObjectKind,
    HostObjectObservationV1,
    MissingHostObjectObservationV1,
)


class RealHostPreflightPortableTests(unittest.TestCase):
    def test_observation_values_require_validated_construction(self) -> None:
        with self.assertRaises(TypeError):
            HostObjectObservationV1(
                schema_version=1,
                volume_fingerprint="unsafe",
                file_id_128="unsafe",
                object_kind=HostObjectKind.DIRECTORY,
                parent_identity_fingerprint="unsafe",
                normalized_name_fingerprint="unsafe",
                filesystem_name="NTFS",
                file_attributes=16,
                reparse_tag=0,
                has_reparse_point=False,
                object_identity_fingerprint="unsafe",
                observation_fingerprint="unsafe",
            )

    def test_object_observation_binds_required_identity_metadata(self) -> None:
        observation = HostObjectObservationV1.create(
            volume_fingerprint="1" * 64,
            file_id_128="2" * 32,
            object_kind=HostObjectKind.DIRECTORY,
            parent_identity_fingerprint="3" * 64,
            normalized_name_fingerprint="4" * 64,
            filesystem_name="NTFS",
            file_attributes=16,
            reparse_tag=0,
            has_reparse_point=False,
        )

        self.assertEqual(observation.file_id_128, "2" * 32)
        self.assertEqual(observation.object_kind, HostObjectKind.DIRECTORY)
        self.assertEqual(len(observation.object_identity_fingerprint), 64)
        self.assertEqual(len(observation.observation_fingerprint), 64)
        self.assertNotIn("2" * 32, repr(observation))

        with self.assertRaises(ValueError):
            HostObjectObservationV1.create(
                volume_fingerprint="1" * 64,
                file_id_128="short",
                object_kind=HostObjectKind.DIRECTORY,
                parent_identity_fingerprint="3" * 64,
                normalized_name_fingerprint="4" * 64,
                filesystem_name="NTFS",
                file_attributes=16,
                reparse_tag=0,
                has_reparse_point=False,
            )

    def test_object_metadata_relationships_fail_closed(self) -> None:
        base = {
            "volume_fingerprint": "1" * 64,
            "file_id_128": "2" * 32,
            "object_kind": HostObjectKind.DIRECTORY,
            "parent_identity_fingerprint": "3" * 64,
            "normalized_name_fingerprint": "4" * 64,
            "filesystem_name": "NTFS",
            "file_attributes": 16,
            "reparse_tag": 0,
            "has_reparse_point": False,
        }
        invalid_overrides = (
            {"object_kind": HostObjectKind.FILE},
            {"file_attributes": 0},
            {
                "file_attributes": 16 | 1024,
                "reparse_tag": 0xA0000003,
                "has_reparse_point": False,
            },
            {
                "file_attributes": 16 | 1024,
                "reparse_tag": 0,
                "has_reparse_point": True,
            },
            {
                "file_attributes": 16,
                "reparse_tag": 0xA0000003,
                "has_reparse_point": False,
            },
        )

        for overrides in invalid_overrides:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(
                    ValueError,
                    "^REAL_HOST_OBSERVATION_INVALID$",
                ):
                    HostObjectObservationV1.create(
                        **{**base, **overrides},
                    )

    def test_missing_observation_binds_parent_volume_and_normalized_name(
        self,
    ) -> None:
        observation = MissingHostObjectObservationV1.create(
            parent_identity_fingerprint="5" * 64,
            volume_fingerprint="6" * 64,
            normalized_name_fingerprint="7" * 64,
            filesystem_name="NTFS",
        )

        self.assertFalse(observation.present)
        self.assertEqual(len(observation.observation_fingerprint), 64)
        self.assertNotIn("5" * 64, repr(observation))

    def test_current_topology_binds_exact_complete_relationships(self) -> None:
        target_parent = _directory_observation(
            file_id="8" * 32,
            parent_fingerprint="9" * 64,
            name_fingerprint="a" * 64,
        )
        source_root = _directory_observation(
            file_id="b" * 32,
            parent_fingerprint=target_parent.object_identity_fingerprint,
            name_fingerprint="c" * 64,
        )
        finance_root = _directory_observation(
            file_id="c" * 32,
            parent_fingerprint=target_parent.object_identity_fingerprint,
            name_fingerprint="d" * 64,
        )
        target_absence = MissingHostObjectObservationV1.create(
            parent_identity_fingerprint=(
                target_parent.object_identity_fingerprint
            ),
            volume_fingerprint="1" * 64,
            normalized_name_fingerprint="e" * 64,
            filesystem_name="NTFS",
        )

        topology = CurrentTopologyObservationV1.create(
            source_root=source_root,
            finance_root=finance_root,
            target_parent=target_parent,
            target_absence=target_absence,
            git_fingerprint="d" * 64,
            acl_fingerprint="f" * 64,
            volume_fingerprint="1" * 64,
            complete=True,
            content_observed=False,
            controlled_components_reparse_free=True,
        )

        self.assertEqual(len(topology.observation_fingerprint), 64)
        self.assertNotIn(source_root.file_id_128, repr(topology))
        with self.assertRaises(ValueError):
            CurrentTopologyObservationV1.create(
                source_root=source_root,
                finance_root=finance_root,
                target_parent=target_parent,
                target_absence=MissingHostObjectObservationV1.create(
                    parent_identity_fingerprint="0" * 64,
                    volume_fingerprint="1" * 64,
                    normalized_name_fingerprint="e" * 64,
                    filesystem_name="NTFS",
                ),
                git_fingerprint="d" * 64,
                acl_fingerprint="f" * 64,
                volume_fingerprint="1" * 64,
                complete=True,
                content_observed=False,
                controlled_components_reparse_free=True,
            )
        aliased_source = _directory_observation(
            file_id=target_parent.file_id_128,
            parent_fingerprint=target_parent.object_identity_fingerprint,
            name_fingerprint="0" * 64,
        )
        with self.assertRaises(ValueError):
            CurrentTopologyObservationV1.create(
                source_root=aliased_source,
                finance_root=finance_root,
                target_parent=target_parent,
                target_absence=target_absence,
                git_fingerprint="d" * 64,
                acl_fingerprint="f" * 64,
                volume_fingerprint="1" * 64,
                complete=True,
                content_observed=False,
                controlled_components_reparse_free=True,
            )


def _directory_observation(
    *,
    file_id: str,
    parent_fingerprint: str,
    name_fingerprint: str,
) -> HostObjectObservationV1:
    return HostObjectObservationV1.create(
        volume_fingerprint="1" * 64,
        file_id_128=file_id,
        object_kind=HostObjectKind.DIRECTORY,
        parent_identity_fingerprint=parent_fingerprint,
        normalized_name_fingerprint=name_fingerprint,
        filesystem_name="NTFS",
        file_attributes=16,
        reparse_tag=0,
        has_reparse_point=False,
    )


if __name__ == "__main__":
    unittest.main()
