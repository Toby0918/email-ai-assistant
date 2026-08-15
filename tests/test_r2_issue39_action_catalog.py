from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_issue39_orchestrator.action_catalog import (
    Issue39ActionPhaseV1,
    build_fixed_production_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.preparation import (
    Issue39PrepareStatusV1,
    _allocate_prepared_execution_v1,
)
from backend.r2_issue39_orchestrator.production_handlers import (
    _definition,
    build_fixed_action_handlers_v1,
)
from backend.r2_issue39_orchestrator.readiness import _observation
from backend.r2_issue39_orchestrator.roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    Issue39WorktreeV1,
)


class Issue39ActionCatalogTest(unittest.TestCase):
    def test_six_worktree_prepare_builds_exact_closed_27_action_catalog(self):
        catalog = build_fixed_production_action_catalog_v1(_prepared(6, 2, 4))

        self.assertEqual(catalog.action_count, 27)
        self.assertEqual(
            tuple(item.phase for item in catalog.actions).count(
                Issue39ActionPhaseV1.FOUNDATION
            ),
            12,
        )
        self.assertEqual(
            tuple(item.action_name for item in catalog.actions[6:12]),
            tuple(f"worktree_reconstruction_{index:02d}" for index in range(1, 7)),
        )
        self.assertEqual(len(catalog.catalog_fingerprint), 64)
        self.assertNotIn("D:/", repr(catalog))
        validations = tuple(
            item for item in catalog.actions if not item.host_effect
        )
        self.assertEqual(len(validations), 3)
        rule_action = next(
            item for item in catalog.actions
            if item.action_name == "rule_fallback_analysis"
        )
        self.assertTrue(rule_action.host_effect)
        self.assertTrue(
            all(
                item.pre_state_fingerprint != item.post_state_fingerprint
                for item in validations
            )
        )

    def test_invalid_or_out_of_range_prepare_cannot_select_actions(self):
        for prepared in (
            object(),
            _prepared(0, 0, 0),
            _prepared(17, 8, 9),
        ):
            with self.assertRaisesRegex(TypeError, "R2_ISSUE39_ACTION_CATALOG_INVALID"):
                build_fixed_production_action_catalog_v1(prepared)

    def test_database_proof_is_dispatched_by_validation_phase(self):
        catalog = build_fixed_production_action_catalog_v1(_prepared(6, 2, 4))
        action = next(
            item for item in catalog.actions if item.action_name == "database_proof"
        )
        handler = build_fixed_action_handlers_v1(catalog)[
            action.action_fingerprint
        ]
        host = object()

        with (
            patch(
                "backend.r2_issue39_orchestrator.production_validation.run_validation"
            ) as validation,
            patch(
                "backend.r2_issue39_orchestrator.production_managed.mutate_managed",
                side_effect=AssertionError("managed publisher selected"),
            ),
        ):
            result = handler.apply(host, action, "forward", "a" * 64)

        validation.assert_called_once_with(host, "database_proof")
        self.assertEqual(result, action.post_state_fingerprint)

    def test_worktree_handler_rejects_prefix_only_name(self):
        catalog = build_fixed_production_action_catalog_v1(_prepared(6, 2, 4))
        action = next(
            item for item in catalog.actions
            if item.action_name == "worktree_reconstruction_01"
        )

        with self.assertRaisesRegex(
            ValueError, "R2_ISSUE39_HANDLER_CATALOG_INVALID"
        ):
            _definition(
                SimpleNamespace(
                    phase=action.phase,
                    sequence=action.sequence,
                    action_name=f"{action.action_name}_extra",
                )
            )

    def test_stop_a_reverse_restarts_the_original_start_a_identity(self):
        from backend.r2_issue39_orchestrator.production_validation import (
            mutate_validation,
        )

        catalog = build_fixed_production_action_catalog_v1(_prepared(6, 2, 4))
        start = next(
            item for item in catalog.actions if item.action_name == "start_a"
        )
        stop = next(
            item for item in catalog.actions if item.action_name == "stop_a"
        )
        host = SimpleNamespace(_catalog=catalog)

        with patch(
            "backend.r2_issue39_orchestrator.production_service.start_validation_service"
        ) as restart:
            mutate_validation(host, stop, "rollback", "a" * 64)

        restart.assert_called_once_with(host, start, "a" * 64)


def _prepared(total, embedded, external):
    worktrees = tuple(
        Issue39WorktreeV1(
            f"worktree_{index:02d}",
            "embedded" if index <= embedded else "external",
            f"{index:064x}",
        )
        for index in range(1, total + 1)
    )
    roster = Issue39BoundRosterV1(
        Issue39RosterStatusV1.VERIFIED,
        worktrees,
        "c" * 64,
        Path("D:/synthetic"),
        (),
    )
    return _allocate_prepared_execution_v1(
        Issue39PrepareStatusV1.VERIFIED,
        "a" * 64,
        total,
        embedded,
        external,
        _observation(True, True, True, "b" * 64),
        None,
        roster,
    )


if __name__ == "__main__":
    unittest.main()
