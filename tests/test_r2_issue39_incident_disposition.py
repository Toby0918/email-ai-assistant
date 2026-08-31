"""Fixed incident-stage disposition contracts and Windows sandbox behavior."""

from __future__ import annotations

import inspect
import os
from pathlib import Path, PureWindowsPath
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from backend.r2_issue39_orchestrator.incident_contracts import (
    IncidentDispositionStatusV1,
    fixed_incident_stage_contract_v1,
)
from backend.r2_issue39_orchestrator.incident_binding import (
    _fixed_incident_binding,
)
from backend.r2_issue39_orchestrator.incident_windows import (
    _open_move_handle_with_restored_dacl,
    _move_with_restored_dacl,
    _require_artifacts,
    dispose_fixed_incident_stage_v1,
)
from backend.r2_issue39_orchestrator.testing_incident import (
    SyntheticIncidentStageV1,
)


class Issue39IncidentDispositionContractTests(unittest.TestCase):
    def test_production_binding_uses_exact_retained_incident_leaf(self) -> None:
        binding = _fixed_incident_binding()
        leaf = (
            ".r2-solo-maintainer-closure-v1.incident-"
            "794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721"
        )

        self.assertEqual(
            binding.source,
            Path(r"D:\Projects\email_ai_assistant\.git") / leaf,
        )
        self.assertEqual(
            PureWindowsPath(binding.destination),
            PureWindowsPath(r"D:\IncidentArchives\email_ai_assistant\issue38")
            / leaf,
        )

    def test_production_entry_is_parameterless_and_contract_is_fixed(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(dispose_fixed_incident_stage_v1).parameters),
            (),
        )
        contract = fixed_incident_stage_contract_v1()
        self.assertEqual(contract.artifact_count, 2)
        self.assertEqual(contract.move_count, 1)
        self.assertEqual(contract.delete_count, 0)
        self.assertEqual(contract.cleanup_count, 0)
        self.assertNotIn("D:\\", repr(contract))
        self.assertNotIn("stage-", repr(contract))

    def test_delete_handle_open_failure_still_restores_original_dacl(self):
        class _FailingApi:
            def open_existing(self, *_args, **_kwargs):
                raise OSError("synthetic")

        with (
            patch(
                "backend.r2_issue39_orchestrator.incident_windows._temporary_sddl",
                return_value="temporary",
            ),
            patch(
                "backend.r2_issue39_orchestrator.incident_windows._set_dacl"
            ) as setter,
            patch(
                "backend.r2_issue39_orchestrator.incident_windows._capture_dacl_sddl",
                return_value="original",
            ),
        ):
            with self.assertRaises(OSError):
                _open_move_handle_with_restored_dacl(
                    _FailingApi(), SimpleNamespace(source="fixed"), 7, "original"
                )

        self.assertEqual(
            setter.call_args_list,
            [call(7, "temporary"), call(7, "original")],
        )


@unittest.skipUnless(sys.platform == "win32", "Windows DACL evidence only")
class Issue39IncidentDispositionWindowsTests(unittest.TestCase):
    def test_missing_archive_parent_is_provisioned_before_move(self) -> None:
        scenario = SyntheticIncidentStageV1.create(
            missing_destination_parent=True,
        )
        self.addCleanup(scenario.close)

        result = scenario.dispose()

        self.assertIs(result.status, IncidentDispositionStatusV1.ARCHIVED)
        self.assertEqual(result.counts(), (2, 1, 0))
        self.assertFalse(scenario.source_exists())
        self.assertTrue(scenario.destination_exists())
        self.assertTrue(scenario.artifacts_match())
        self.assertTrue(scenario.final_dacl_matches())

    def test_exact_stage_moves_no_replace_and_restores_final_dacl(self) -> None:
        scenario = SyntheticIncidentStageV1.create()
        self.addCleanup(scenario.close)

        result = scenario.dispose()

        self.assertIs(result.status, IncidentDispositionStatusV1.ARCHIVED)
        self.assertEqual(result.counts(), (2, 1, 0))
        self.assertFalse(scenario.source_exists())
        self.assertTrue(scenario.destination_exists())
        self.assertTrue(scenario.artifacts_match())
        self.assertTrue(scenario.final_dacl_matches())

    def test_archive_parent_handle_is_held_across_the_move_boundary(self) -> None:
        scenario = SyntheticIncidentStageV1.create()
        self.addCleanup(scenario.close)
        parent = scenario.destination.parent
        displaced = parent.with_name("issue38-displaced")
        replacement = parent.with_name("issue38-replacement")
        replacement.mkdir()
        self.addCleanup(lambda: replacement.rmdir() if replacement.exists() else None)
        attempts = []

        def attempt_parent_replacement(binding, parent_lease):
            os.rename(parent, displaced)
            os.rename(replacement, parent)
            attempts.append("replaced")
            return _move_with_restored_dacl(binding, parent_lease)

        with patch(
            "backend.r2_issue39_orchestrator.incident_windows."
            "_move_with_restored_dacl",
            side_effect=attempt_parent_replacement,
        ):
            result = scenario.dispose()

        self.assertEqual(attempts, ["replaced"])
        self.assertIs(result.status, IncidentDispositionStatusV1.INCIDENT_STOP)
        self.assertTrue(scenario.source_exists())
        parent.rmdir()
        os.rename(displaced, parent)

    def test_parent_replacement_after_artifact_reread_cannot_report_success(self):
        scenario = SyntheticIncidentStageV1.create()
        self.addCleanup(scenario.close)
        parent = scenario.destination.parent
        displaced = parent.with_name("issue38-reread-displaced")
        replacement = parent.with_name("issue38-reread-replacement")
        replacement.mkdir()
        replaced = []

        def replace_after_reread(binding, *, destination=False):
            _require_artifacts(binding, destination=destination)
            if destination:
                os.rename(parent, displaced)
                os.rename(replacement, parent)
                replaced.append(True)

        with patch(
            "backend.r2_issue39_orchestrator.incident_windows."
            "_require_artifacts",
            side_effect=replace_after_reread,
        ):
            result = scenario.dispose()

        self.assertEqual(replaced, [True])
        self.assertIs(result.status, IncidentDispositionStatusV1.INCIDENT_STOP)
        parent.rmdir()
        os.rename(displaced, parent)

    def test_destination_collision_retains_source_and_competitor(self) -> None:
        scenario = SyntheticIncidentStageV1.create(destination_collision=True)
        self.addCleanup(scenario.close)

        result = scenario.dispose()

        self.assertIs(
            result.status,
            IncidentDispositionStatusV1.BLOCKED_DESTINATION,
        )
        self.assertEqual(result.counts(), (0, 0, 0))
        self.assertTrue(scenario.source_exists())
        self.assertTrue(scenario.competitor_preserved())
        self.assertTrue(scenario.source_dacl_restored())

    def test_artifact_drift_stops_before_dacl_or_move(self) -> None:
        scenario = SyntheticIncidentStageV1.create(artifact_drift=True)
        self.addCleanup(scenario.close)

        result = scenario.dispose()

        self.assertIs(
            result.status,
            IncidentDispositionStatusV1.BLOCKED_ARTIFACT,
        )
        self.assertEqual(result.counts(), (0, 0, 0))
        self.assertTrue(scenario.source_exists())
        self.assertTrue(scenario.source_dacl_restored())


if __name__ == "__main__":
    unittest.main()
