"""Closed one-verb operator command for Issue #39."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import sys

from .preparation import (
    Issue39PrepareStatusV1,
    Issue39PreparedExecutionV1,
    prepare_fixed_issue39_execution_v1,
)


class Issue39CommandStatusV1(str, Enum):
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_CONSOLE = "BLOCKED_ISSUE39_CONSOLE"
    BLOCKED_PREPARE = "BLOCKED_ISSUE39_PREPARE"
    EXECUTION_COMPLETE = "ISSUE39_EXECUTION_COMPLETE"
    SAFE_ABORT = "SAFE_ABORT"
    LEGACY_RECOVERED = "LEGACY_RECOVERED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True)
class Issue39CommandResultV1:
    status: Issue39CommandStatusV1
    accepted: int
    rejected: int
    host_actions: int

    def counts(self) -> tuple[int, int, int]:
        return self.accepted, self.rejected, self.host_actions


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39CommandPorts:
    read_readiness: object = field(repr=False)
    require_console: object = field(repr=False)
    confirm_incident: object = field(repr=False)
    dispose_incident: object = field(repr=False)
    prepare: object = field(repr=False)
    bind_and_run: object = field(repr=False)
    is_anchor: object = field(default=lambda: False, repr=False)
    resume_anchor: object = field(default=lambda: None, repr=False)


def run_issue39_command_v1(*, argv):
    """Run only the code-fixed command with no caller-selected capability."""

    return _run_issue39_command_v1(argv=argv, ports=_production_ports())


def _run_issue39_command_v1(*, argv, ports):
    if type(argv) is not tuple or argv != ("run",):
        return _result(Issue39CommandStatusV1.BLOCKED_COMMAND)
    if (
        type(ports) is not _Issue39CommandPorts
        or not callable(ports.read_readiness)
        or not callable(ports.require_console)
        or not callable(ports.confirm_incident)
        or not callable(ports.dispose_incident)
        or not callable(ports.prepare)
        or not callable(ports.bind_and_run)
        or not callable(ports.is_anchor)
        or not callable(ports.resume_anchor)
    ):
        return _result(Issue39CommandStatusV1.INCIDENT_STOP)
    try:
        if ports.is_anchor():
            if ports.require_console() is not True:
                return _result(Issue39CommandStatusV1.BLOCKED_CONSOLE)
            return _command_outcome(ports.resume_anchor())
        readiness = ports.read_readiness()
        from .zero_readiness import Issue39ZeroMutationReadinessV1

        if (
            type(readiness) is not Issue39ZeroMutationReadinessV1
            or readiness.ready() is not True
        ):
            return _result(Issue39CommandStatusV1.BLOCKED_PREPARE)
        if ports.require_console() is not True:
            return _result(Issue39CommandStatusV1.BLOCKED_CONSOLE)
        if (
            readiness.incident_state == "SOURCE_VERIFIED"
            and ports.confirm_incident(readiness) is not True
        ):
            return _result(Issue39CommandStatusV1.BLOCKED_PREPARE)
        incident = ports.dispose_incident()
        if incident not in {"ARCHIVED", "VERIFIED"}:
            return _result(Issue39CommandStatusV1.BLOCKED_PREPARE)
        prepared = ports.prepare()
        if (
            type(prepared) is not Issue39PreparedExecutionV1
            or prepared.status is not Issue39PrepareStatusV1.PREPARED
        ):
            return _result(Issue39CommandStatusV1.BLOCKED_PREPARE)
        outcome = ports.bind_and_run(prepared)
        return _command_outcome(outcome)
    except Exception:
        return _result(Issue39CommandStatusV1.INCIDENT_STOP)


def _production_ports() -> _Issue39CommandPorts:
    from .console_gate import require_fixed_windows_console_v1
    from .incident_confirmation import confirm_fixed_incident_disposition_v1
    from .incident_contracts import IncidentDispositionStatusV1
    from .incident_verify import verify_fixed_incident_archive_v1
    from .incident_windows import dispose_fixed_incident_stage_v1
    from .production_binder import bind_and_run_fixed_issue39_execution_v1
    from .production_binder import resume_fixed_issue39_anchor_v1
    from .anchor_context import current_process_is_fixed_anchor_v1
    from .zero_readiness import (
        observe_fixed_issue39_zero_mutation_readiness_v1,
    )

    def disposition():
        if verify_fixed_incident_archive_v1():
            return "VERIFIED"
        result = dispose_fixed_incident_stage_v1()
        return (
            "ARCHIVED"
            if result.status is IncidentDispositionStatusV1.ARCHIVED
            and verify_fixed_incident_archive_v1()
            else "BLOCKED"
        )

    return _Issue39CommandPorts(
        observe_fixed_issue39_zero_mutation_readiness_v1,
        require_fixed_windows_console_v1,
        confirm_fixed_incident_disposition_v1,
        disposition,
        prepare_fixed_issue39_execution_v1,
        bind_and_run_fixed_issue39_execution_v1,
        current_process_is_fixed_anchor_v1,
        resume_fixed_issue39_anchor_v1,
    )


def _command_outcome(outcome):
    from .action_runner import (
        Issue39ActionRunResultV1,
        Issue39ActionRunStatusV1,
    )

    if type(outcome) is not Issue39ActionRunResultV1:
        raise ValueError
    statuses = {
        Issue39ActionRunStatusV1.SUCCEEDED: Issue39CommandStatusV1.EXECUTION_COMPLETE,
        Issue39ActionRunStatusV1.SAFE_ABORT: Issue39CommandStatusV1.SAFE_ABORT,
        Issue39ActionRunStatusV1.LEGACY_RECOVERED: Issue39CommandStatusV1.LEGACY_RECOVERED,
        Issue39ActionRunStatusV1.INCIDENT_STOP: Issue39CommandStatusV1.INCIDENT_STOP,
    }
    succeeded = outcome.status is Issue39ActionRunStatusV1.SUCCEEDED
    return Issue39CommandResultV1(
        statuses[outcome.status], outcome.committed if succeeded else 0,
        0 if succeeded else 1, outcome.host_actions,
    )


def _result(status):
    return Issue39CommandResultV1(status, 0, 1, 0)


def main():
    result = run_issue39_command_v1(argv=tuple(sys.argv[1:]))
    if result.status is Issue39CommandStatusV1.EXECUTION_COMPLETE:
        sys.stdout.write("PROJECT_CONTAINER_CUTOVER_SUCCEEDED\n")
    else:
        sys.stdout.write(json.dumps({
            "status": result.status.value,
            "accepted": result.accepted,
            "rejected": result.rejected,
            "host_actions": result.host_actions,
        }, sort_keys=True, separators=(",", ":")) + "\n")
    raise SystemExit(0 if result.rejected == 0 else 2)
