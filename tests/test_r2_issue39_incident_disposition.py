"""Fixed incident-stage disposition contracts and Windows sandbox behavior."""

from __future__ import annotations

import inspect
from pathlib import Path
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
            binding.destination,
            Path(r"D:\IncidentArchives\email_ai_assistant\issue38") / leaf,
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
