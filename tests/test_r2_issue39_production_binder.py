from __future__ import annotations

import unittest
import hashlib
from pathlib import Path
from types import SimpleNamespace

from backend.r2_issue39_orchestrator.action_runner import (
    Issue39ActionRunResultV1,
    Issue39ActionRunStatusV1,
    _Issue39ActionRunnerPortsV1,
)
from backend.r2_issue39_orchestrator.closure_binding import (
    _Issue39ClosureBindingV1,
)

from backend.r2_issue39_orchestrator.preparation import (
    Issue39PrepareStatusV1,
    _Issue39PreparationPorts,
    _prepare_issue39_execution_v1,
    _reverify_issue39_execution_v1,
)
from backend.r2_issue39_orchestrator.production_inputs import (
    Issue39ProductionInputsV1,
    Issue39ProductionInputStatusV1,
)
from backend.r2_issue39_orchestrator.roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    Issue39WorktreeV1,
)
from backend.r2_issue39_orchestrator.readiness import _observation
from backend.r2_issue39_orchestrator.production_binder import (
    _Issue39ProductionBinderPortsV1,
    _bind_and_run_issue39_execution_v1,
)
from tests.test_r2_transaction_journal_v2 import _binding


class Issue39ProductionBinderTest(unittest.TestCase):
    def test_binder_owns_exact_composition_order_and_returns_success_counts(self):
        state = _State()
        prepared = _prepare_issue39_execution_v1(ports=state.ports())
        state.roster = _roster(
            "a" * 64, status=Issue39RosterStatusV1.VERIFIED
        )
        verified = _reverify_issue39_execution_v1(
            prepared=prepared, ports=state.ports()
        )
        binding = _binding()
        manifest = SimpleNamespace(manifest_fingerprint="4" * 64)
        receipt = SimpleNamespace(receipt_fingerprint="5" * 64)
        closure = _Issue39ClosureBindingV1(
            manifest, receipt, object(), binding
        )
        closure_fingerprint = hashlib.sha256(
            b"r2-issue39-closure-readiness-v1\0"
            + bytes.fromhex(manifest.manifest_fingerprint)
            + bytes.fromhex(receipt.receipt_fingerprint)
        ).hexdigest()
        object.__setattr__(verified._closure, "closure_fingerprint", closure_fingerprint)
        calls = []
        runner_ports = _Issue39ActionRunnerPortsV1(
            lambda *_args: None, lambda *_args: None,
            lambda *_args: None, lambda *_args: None, lambda _journal: None,
            lambda: {}, lambda *_args: None,
            lambda *_args: None, lambda *_args: None,
            lambda *_args: False,
        )

        def catalog(value):
            calls.append("catalog")
            return __import__(
                "backend.r2_issue39_orchestrator.action_catalog",
                fromlist=["build_fixed_production_action_catalog_v1"],
            ).build_fixed_production_action_catalog_v1(value)

        ports = _Issue39ProductionBinderPortsV1(
            lambda _value: calls.append("reverify") or verified,
            lambda: calls.append("closure") or closure,
            catalog,
            lambda *_args: calls.append(f"preflight:{_args[4]}") or object(),
            lambda *_args: calls.append("evidence") or object(),
            lambda **_kwargs: calls.append("bootstrap") or (object(), object()),
            lambda _package: calls.append("anchor"),
            lambda **_kwargs: calls.append("actions") or runner_ports,
            lambda **_kwargs: calls.append("run") or Issue39ActionRunResultV1(
                Issue39ActionRunStatusV1.SUCCEEDED, 27, 0, 24, None
            ),
        )

        result = _bind_and_run_issue39_execution_v1(
            prepared=prepared, ports=ports
        )

        self.assertIs(result.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual(
            (result.committed, result.reversed, result.host_actions),
            (27, 0, 24),
        )
        self.assertEqual(
            calls,
            ["reverify", "closure", "catalog",
             "preflight:before_evidence", "evidence", "bootstrap",
             "preflight:after_evidence", "anchor", "actions", "run"],
        )

    def test_fresh_prepare_binds_complete_dynamic_roster_and_fixed_inputs(self):
        state = _State()

        prepared = _prepare_issue39_execution_v1(ports=state.ports())

        self.assertEqual(prepared.status, Issue39PrepareStatusV1.PREPARED)
        self.assertEqual(prepared.counts(), (6, 2, 4))
        self.assertEqual(len(prepared.prepare_fingerprint), 64)
        self.assertNotIn("D:/", repr(prepared))

    def test_any_post_prepare_roster_drift_stops_before_execution(self):
        state = _State()
        prepared = _prepare_issue39_execution_v1(ports=state.ports())
        state.roster = _roster("b" * 64, status=Issue39RosterStatusV1.VERIFIED)

        verified = _reverify_issue39_execution_v1(
            prepared=prepared,
            ports=state.ports(),
        )

        self.assertEqual(verified.status, Issue39PrepareStatusV1.BLOCKED_DRIFT)
        self.assertEqual(verified.counts(), (0, 0, 0))

    def test_open_issue38_or_unready_fixed_input_fails_closed(self):
        for issue38_closed, input_status in (
            (False, Issue39ProductionInputStatusV1.READY),
            (True, Issue39ProductionInputStatusV1.BLOCKED_WHEELHOUSE),
        ):
            with self.subTest(issue38_closed=issue38_closed, input_status=input_status):
                state = _State(issue38_closed=issue38_closed, input_status=input_status)
                result = _prepare_issue39_execution_v1(ports=state.ports())
                self.assertEqual(result.status, Issue39PrepareStatusV1.BLOCKED_READINESS)


class _State:
    def __init__(
        self,
        *,
        issue38_closed=True,
        input_status=Issue39ProductionInputStatusV1.READY,
    ):
        self.issue38_closed = issue38_closed
        self.input_status = input_status
        self.roster = _roster("a" * 64)

    def ports(self):
        return _Issue39PreparationPorts(
            observe_closure=lambda: _observation(
                True, self.issue38_closed, True, "c" * 64
            ),
            verify_inputs=lambda: Issue39ProductionInputsV1(
                self.input_status,
                "d" * 64 if self.input_status is Issue39ProductionInputStatusV1.READY else "0" * 64,
                31 if self.input_status is Issue39ProductionInputStatusV1.READY else 0,
                1 if self.input_status is Issue39ProductionInputStatusV1.READY else 0,
                36 if self.input_status is Issue39ProductionInputStatusV1.READY else 0,
                "e" * 64,
                "3" * 64,
                3_684,
                66_855_518,
                "f" * 64,
                "1" * 64,
                "2" * 64,
            ),
            prepare_roster=lambda: self.roster,
            reverify_roster=lambda _bound: self.roster,
        )


def _roster(fingerprint, *, status=Issue39RosterStatusV1.PREPARED):
    worktrees = tuple(
        Issue39WorktreeV1(
            f"worktree_{index:02d}",
            "embedded" if index <= 2 else "external",
            f"{index:064x}",
        )
        for index in range(1, 7)
    )
    return Issue39BoundRosterV1(
        status,
        worktrees,
        fingerprint,
        Path("D:/synthetic"),
        (),
    )


if __name__ == "__main__":
    unittest.main()
