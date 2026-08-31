"""Fixed archive-parent readiness and Windows provisioning boundaries."""

from __future__ import annotations

import inspect
from pathlib import Path, PureWindowsPath
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.cutover_host_mutation.windows_handles import (
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
)
from backend.real_host_preflight.windows_paths import expected_final_path
from backend.r2_issue39_orchestrator.archive_parent_native import (
    SecurityDescriptor,
    create_directory,
)
from backend.r2_issue39_orchestrator.archive_parent_windows import (
    _ArchiveParentFailure,
    _expected_archive_parent_sddl,
    _observe_archive_parent_readiness_v1,
    _provision_archive_parent_v1,
    _require_identity,
    observe_fixed_archive_parent_readiness_v1,
    provision_fixed_archive_parent_v1,
)
from backend.r2_issue39_orchestrator.testing_incident import (
    SyntheticIncidentStageV1,
    _apply_sddl,
)
from backend.r2_issue39_orchestrator.incident_binding import (
    _fixed_incident_binding,
)
from windows_reparse_fixtures import create_test_junction


class Issue39ArchiveParentContractTests(unittest.TestCase):
    def test_production_observer_and_provisioner_are_parameterless(self) -> None:
        self.assertEqual(
            tuple(
                inspect.signature(
                    observe_fixed_archive_parent_readiness_v1
                ).parameters
            ),
            (),
        )

    def test_production_hierarchy_is_the_one_fixed_three_component_path(self):
        binding = _fixed_incident_binding()

        self.assertEqual(binding.archive_anchor, Path("D:\\"))
        self.assertEqual(
            binding.archive_components,
            ("IncidentArchives", "email_ai_assistant", "issue38"),
        )
        self.assertEqual(
            PureWindowsPath(binding.destination.parent),
            PureWindowsPath(r"D:\IncidentArchives\email_ai_assistant\issue38"),
        )
        self.assertEqual(
            tuple(
                inspect.signature(provision_fixed_archive_parent_v1).parameters
            ),
            (),
        )


@unittest.skipUnless(
    sys.platform == "win32", "Windows native Issue #39 operations"
)
class Issue39ArchiveParentWindowsTests(unittest.TestCase):
    def test_missing_hierarchy_becomes_ready_with_a_new_fingerprint(self) -> None:
        scenario = SyntheticIncidentStageV1.create(
            missing_destination_parent=True,
        )
        self.addCleanup(scenario.close)

        before = _observe_archive_parent_readiness_v1(scenario.binding)
        self.assertEqual(before.state, "PROVISIONABLE")
        self.assertEqual(len(before.readiness_fingerprint), 64)

        self.assertTrue(_provision_archive_parent_v1(scenario.binding))

        after = _observe_archive_parent_readiness_v1(scenario.binding)
        self.assertEqual(after.state, "READY")
        self.assertEqual(len(after.readiness_fingerprint), 64)
        self.assertNotEqual(before.readiness_fingerprint, after.readiness_fingerprint)

    def test_partially_existing_hierarchy_is_bound_then_completed(self) -> None:
        scenario = SyntheticIncidentStageV1.create(
            missing_destination_parent=True,
        )
        self.addCleanup(scenario.close)
        first = scenario.binding.archive_anchor / "IncidentArchives"
        api = WindowsHandleApi()
        anchor = api.open_existing(
            scenario.binding.archive_anchor,
            access=FILE_READ_ATTRIBUTES,
        )
        descriptor = SecurityDescriptor(_expected_archive_parent_sddl())
        child = None
        try:
            child = create_directory(
                anchor, "IncidentArchives", descriptor.pointer
            )
        finally:
            if child is not None:
                api.close(child)
            descriptor.close()
            api.close(anchor)

        before = _observe_archive_parent_readiness_v1(scenario.binding)

        self.assertEqual(before.state, "PROVISIONABLE")
        self.assertTrue(
            _provision_archive_parent_v1(scenario.binding, expected=before)
        )
        self.assertEqual(
            _observe_archive_parent_readiness_v1(scenario.binding).state,
            "READY",
        )

    def test_wrong_existing_dacl_is_blocked_not_repaired(self) -> None:
        scenario = SyntheticIncidentStageV1.create()
        self.addCleanup(scenario.close)
        first = scenario.binding.archive_anchor / scenario.binding.archive_components[0]
        _apply_sddl(first, "D:P(A;OICI;GR;;;WD)")

        observed = _observe_archive_parent_readiness_v1(scenario.binding)

        self.assertEqual(observed.state, "BLOCKED")
        self.assertFalse(_provision_archive_parent_v1(scenario.binding))

    def test_competing_create_is_preserved_and_not_adopted(self) -> None:
        scenario = SyntheticIncidentStageV1.create(
            missing_destination_parent=True,
        )
        self.addCleanup(scenario.close)
        competitor = scenario.binding.archive_anchor / "IncidentArchives"

        def collide(_parent, _name, _descriptor):
            competitor.mkdir()
            (competitor / "competitor.bin").write_bytes(b"competitor\n")
            raise OSError("synthetic collision")

        with patch(
            "backend.r2_issue39_orchestrator.archive_parent_windows.create_directory",
            side_effect=collide,
        ):
            self.assertFalse(_provision_archive_parent_v1(scenario.binding))

        self.assertEqual(
            (competitor / "competitor.bin").read_bytes(), b"competitor\n"
        )
        self.assertEqual(
            _observe_archive_parent_readiness_v1(scenario.binding).state,
            "BLOCKED",
        )

    def test_exact_dacl_competitor_after_readiness_is_not_adopted(self) -> None:
        scenario = SyntheticIncidentStageV1.create(
            missing_destination_parent=True,
        )
        self.addCleanup(scenario.close)
        expected = _observe_archive_parent_readiness_v1(scenario.binding)
        competitor = scenario.binding.archive_anchor / "IncidentArchives"
        competitor.mkdir()
        _apply_sddl(competitor, _expected_archive_parent_sddl())

        self.assertFalse(
            _provision_archive_parent_v1(scenario.binding, expected=expected)
        )
        self.assertTrue(competitor.is_dir())
        self.assertFalse((competitor / "email_ai_assistant").exists())

    def test_reparse_component_is_blocked_not_followed(self) -> None:
        scenario = SyntheticIncidentStageV1.create(
            missing_destination_parent=True,
        )
        self.addCleanup(scenario.close)
        target = scenario.binding.archive_anchor / "junction-target"
        target.mkdir()
        link = scenario.binding.archive_anchor / "IncidentArchives"
        create_test_junction(link, target)

        observed = _observe_archive_parent_readiness_v1(scenario.binding)

        self.assertEqual(observed.state, "BLOCKED")
        self.assertFalse(_provision_archive_parent_v1(scenario.binding))
        self.assertTrue(target.is_dir())

    def test_non_ntfs_non_fixed_and_placement_drift_fail_closed(self) -> None:
        path = Path(self._testMethodName).resolve()
        expected = expected_final_path(path)
        baseline = {
            "file_attributes": 0x10,
            "filesystem_name": "NTFS",
            "drive_type": "fixed",
            "normalized_path": expected,
        }

        for drift in (
            {"filesystem_name": "FAT32"},
            {"drive_type": "removable"},
            {"normalized_path": expected + "-drift"},
        ):
            with self.subTest(drift=drift):
                observed = SimpleNamespace(**(baseline | drift))
                api = SimpleNamespace(require_stable=lambda *_args: None)
                with self.assertRaises(_ArchiveParentFailure):
                    _require_identity(
                        api,
                        7,
                        observed,
                        path,
                        None,
                    )


if __name__ == "__main__":
    unittest.main()
