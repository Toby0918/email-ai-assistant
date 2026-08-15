from __future__ import annotations

import unittest
import io
from unittest.mock import patch

from backend.r2_issue39_orchestrator.cli import (
    Issue39CommandStatusV1,
    _Issue39CommandPorts,
    _run_issue39_command_v1,
    main,
)
from backend.r2_issue39_orchestrator.preparation import (
    Issue39PrepareStatusV1,
    _allocate_prepared_execution_v1,
)
from backend.r2_issue39_orchestrator.readiness import _observation
from backend.r2_issue39_orchestrator.zero_readiness import _allocate as _zero
from backend.r2_issue39_orchestrator.action_runner import (
    Issue39ActionRunResultV1,
    Issue39ActionRunStatusV1,
)


class Issue39CliTest(unittest.TestCase):
    def test_unknown_or_extra_argument_stops_before_prepare(self):
        calls = []
        ports = _Issue39CommandPorts(
            lambda: calls.append("readiness"),
            lambda: calls.append("console"),
            lambda _readiness: calls.append("confirmation"),
            lambda: calls.append("incident"),
            lambda: calls.append("prepare"),
            lambda _value: None,
        )

        for argv in ((), ("prepare",), ("run", "--force")):
            result = _run_issue39_command_v1(argv=argv, ports=ports)
            self.assertEqual(result.status, Issue39CommandStatusV1.BLOCKED_COMMAND)
        self.assertEqual(calls, [])

    def test_readiness_and_console_stop_before_incident_mutation(self):
        for readiness, console, expected in (
            (_zero(False, "SOURCE_VERIFIED", "0" * 64), True, ["readiness"]),
            (_zero(True, "SOURCE_VERIFIED", "b" * 64), False, ["readiness", "console"]),
        ):
            with self.subTest(readiness=readiness, console=console):
                calls = []
                ports = _Issue39CommandPorts(
                    lambda: calls.append("readiness") or readiness,
                    lambda: calls.append("console") or console,
                    lambda _value: calls.append("confirmation") or True,
                    lambda: calls.append("incident") or "VERIFIED",
                    lambda: calls.append("prepare"),
                    lambda _value: calls.append("bind"),
                )

                result = _run_issue39_command_v1(argv=("run",), ports=ports)

                self.assertEqual(
                    result.status,
                    Issue39CommandStatusV1.BLOCKED_PREPARE
                    if not readiness.baseline_eligible
                    else Issue39CommandStatusV1.BLOCKED_CONSOLE,
                )
                self.assertEqual(calls, expected)

    def test_blocked_fresh_prepare_never_binds_execution(self):
        calls = []
        ports = _Issue39CommandPorts(
            lambda: _zero(True, "ARCHIVED", "b" * 64),
            lambda: True,
            lambda _value: True,
            lambda: "VERIFIED",
            lambda: _prepared(Issue39PrepareStatusV1.BLOCKED_READINESS),
            lambda _value: calls.append("bind"),
        )

        result = _run_issue39_command_v1(argv=("run",), ports=ports)

        self.assertEqual(result.status, Issue39CommandStatusV1.BLOCKED_PREPARE)
        self.assertEqual(result.counts(), (0, 1, 0))
        self.assertEqual(calls, [])

    def test_incident_disposition_must_verify_before_prepare(self):
        calls = []
        ports = _Issue39CommandPorts(
            lambda: calls.append("readiness") or _zero(True, "SOURCE_VERIFIED", "b" * 64),
            lambda: calls.append("console") or True,
            lambda _value: calls.append("confirmation") or True,
            lambda: "BLOCKED",
            lambda: calls.append("prepare"),
            lambda _value: calls.append("bind"),
        )

        result = _run_issue39_command_v1(argv=("run",), ports=ports)

        self.assertEqual(result.status, Issue39CommandStatusV1.BLOCKED_PREPARE)
        self.assertEqual(calls, ["readiness", "console", "confirmation"])

    def test_success_order_is_readiness_console_incident_fresh_prepare_bind(self):
        calls = []
        ports = _Issue39CommandPorts(
            lambda: calls.append("readiness") or _zero(True, "SOURCE_VERIFIED", "b" * 64),
            lambda: calls.append("console") or True,
            lambda _value: calls.append("confirmation") or True,
            lambda: calls.append("incident") or "ARCHIVED",
            lambda: calls.append("prepare") or _prepared(
                Issue39PrepareStatusV1.PREPARED
            ),
            lambda _value: calls.append("bind") or Issue39ActionRunResultV1(
                Issue39ActionRunStatusV1.SUCCEEDED, 1, 0, 1, None
            ),
        )

        result = _run_issue39_command_v1(argv=("run",), ports=ports)

        self.assertEqual(
            result.status,
            Issue39CommandStatusV1.EXECUTION_COMPLETE,
        )
        self.assertEqual(
            calls,
            ["readiness", "console", "confirmation", "incident", "prepare", "bind"],
        )

    def test_recovery_classifications_are_not_flattened_to_incident_stop(self):
        for action_status, command_status in (
            (Issue39ActionRunStatusV1.SAFE_ABORT, Issue39CommandStatusV1.SAFE_ABORT),
            (Issue39ActionRunStatusV1.LEGACY_RECOVERED, Issue39CommandStatusV1.LEGACY_RECOVERED),
            (Issue39ActionRunStatusV1.INCIDENT_STOP, Issue39CommandStatusV1.INCIDENT_STOP),
        ):
            ports = _Issue39CommandPorts(
                lambda: _zero(True, "ARCHIVED", "b" * 64), lambda: True,
                lambda _value: True, lambda: "VERIFIED",
                lambda: _prepared(Issue39PrepareStatusV1.PREPARED),
                lambda _value, status=action_status: Issue39ActionRunResultV1(
                    status, 3, 2, 5, None
                ),
            )
            result = _run_issue39_command_v1(argv=("run",), ports=ports)
            self.assertIs(result.status, command_status)
            self.assertEqual(result.rejected, 1)

    def test_public_success_is_the_one_fixed_success_line(self):
        output = io.StringIO()
        with (
            patch("sys.argv", ["execute_project_container_cutover.py", "run"]),
            patch("sys.stdout", output),
            patch(
                "backend.r2_issue39_orchestrator.cli.run_issue39_command_v1",
                return_value=__import__(
                    "backend.r2_issue39_orchestrator.cli",
                    fromlist=["Issue39CommandResultV1"],
                ).Issue39CommandResultV1(
                    Issue39CommandStatusV1.EXECUTION_COMPLETE, 27, 0, 24
                ),
            ),
        ):
            with self.assertRaises(SystemExit) as stopped:
                main()
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(output.getvalue(), "PROJECT_CONTAINER_CUTOVER_SUCCEEDED\n")

    def test_verified_anchor_resumes_without_repeating_initial_readiness(self):
        calls = []
        ports = _Issue39CommandPorts(
            lambda: calls.append("readiness"),
            lambda: calls.append("console") or True,
            lambda _value: calls.append("incident-confirm"),
            lambda: calls.append("incident"),
            lambda: calls.append("prepare"),
            lambda _value: calls.append("bind"),
            lambda: True,
            lambda: calls.append("resume") or Issue39ActionRunResultV1(
                Issue39ActionRunStatusV1.SUCCEEDED, 27, 0, 24, None
            ),
        )

        result = _run_issue39_command_v1(argv=("run",), ports=ports)

        self.assertIs(result.status, Issue39CommandStatusV1.EXECUTION_COMPLETE)
        self.assertEqual(calls, ["console", "resume"])


def _prepared(status):
    return _allocate_prepared_execution_v1(
        status,
        "a" * 64 if status is Issue39PrepareStatusV1.PREPARED else "0" * 64,
        6 if status is Issue39PrepareStatusV1.PREPARED else 0,
        2 if status is Issue39PrepareStatusV1.PREPARED else 0,
        4 if status is Issue39PrepareStatusV1.PREPARED else 0,
        _observation(True, True, True, "b" * 64),
        None,
        None,
    )


if __name__ == "__main__":
    unittest.main()
