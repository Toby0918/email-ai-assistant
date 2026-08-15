"""Fresh immutable preparation for the fixed Issue #39 production run."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from .production_inputs import (
    Issue39ProductionInputsV1,
    Issue39ProductionInputStatusV1,
    verify_fixed_production_inputs_v1,
)
from .readiness import Issue39ReadinessObservationV1
from .roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    prepare_fixed_roster_v1,
    reverify_fixed_roster_v1,
)


class Issue39PrepareStatusV1(str, Enum):
    PREPARED = "ISSUE39_FRESH_PREPARE_COMPLETE"
    VERIFIED = "ISSUE39_FRESH_PREPARE_VERIFIED"
    BLOCKED_READINESS = "BLOCKED_ISSUE39_READINESS"
    BLOCKED_DRIFT = "BLOCKED_ISSUE39_PREPARE_DRIFT"


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39PreparationPorts:
    observe_closure: object = field(repr=False)
    verify_inputs: object = field(repr=False)
    prepare_roster: object = field(repr=False)
    reverify_roster: object = field(repr=False)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39PreparedExecutionV1:
    status: Issue39PrepareStatusV1
    prepare_fingerprint: str = field(repr=False)
    worktree_count: int
    embedded_count: int
    external_count: int
    _closure: Issue39ReadinessObservationV1 = field(repr=False)
    _inputs: Issue39ProductionInputsV1 | None = field(repr=False)
    _roster: Issue39BoundRosterV1 | None = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39PreparedExecutionV1 requires fresh prepare")

    def counts(self) -> tuple[int, int, int]:
        return self.worktree_count, self.embedded_count, self.external_count


def prepare_fixed_issue39_execution_v1() -> Issue39PreparedExecutionV1:
    """Bind all current fixed inputs without accepting caller paths."""

    return _prepare_issue39_execution_v1(ports=_production_ports())


def reverify_fixed_issue39_execution_v1(
    prepared: Issue39PreparedExecutionV1,
) -> Issue39PreparedExecutionV1:
    """Reject every change since the matching fresh prepare."""

    return _reverify_issue39_execution_v1(
        prepared=prepared,
        ports=_production_ports(),
    )


def _prepare_issue39_execution_v1(*, ports):
    try:
        _require_ports(ports)
        closure = ports.observe_closure()
        inputs = ports.verify_inputs()
        roster = ports.prepare_roster()
        _require_ready(closure, inputs, roster)
        counts = roster.counts()
        fingerprint = _prepare_fingerprint(closure, inputs, roster)
        return _allocate_prepared_execution_v1(
            Issue39PrepareStatusV1.PREPARED,
            fingerprint,
            *counts,
            closure,
            inputs,
            roster,
        )
    except Exception:
        return _blocked(Issue39PrepareStatusV1.BLOCKED_READINESS)


def _reverify_issue39_execution_v1(*, prepared, ports):
    if (
        type(prepared) is not Issue39PreparedExecutionV1
        or prepared.status is not Issue39PrepareStatusV1.PREPARED
    ):
        return _blocked(Issue39PrepareStatusV1.BLOCKED_DRIFT)
    try:
        _require_ports(ports)
        closure = ports.observe_closure()
        inputs = ports.verify_inputs()
        roster = ports.reverify_roster(prepared._roster)
        if (
            closure != prepared._closure
            or inputs != prepared._inputs
            or roster.status is not Issue39RosterStatusV1.VERIFIED
            or roster.worktrees != prepared._roster.worktrees
            or roster.roster_fingerprint != prepared._roster.roster_fingerprint
        ):
            raise ValueError
        fingerprint = _prepare_fingerprint(closure, inputs, roster)
        if fingerprint != prepared.prepare_fingerprint:
            raise ValueError
        return _allocate_prepared_execution_v1(
            Issue39PrepareStatusV1.VERIFIED,
            fingerprint,
            *roster.counts(),
            closure,
            inputs,
            roster,
        )
    except Exception:
        return _blocked(Issue39PrepareStatusV1.BLOCKED_DRIFT)


def _require_ports(ports) -> None:
    if type(ports) is not _Issue39PreparationPorts or not all(
        callable(getattr(ports, name))
        for name in (
            "observe_closure",
            "verify_inputs",
            "prepare_roster",
            "reverify_roster",
        )
    ):
        raise TypeError


def _require_ready(closure, inputs, roster) -> None:
    if (
        type(closure) is not Issue39ReadinessObservationV1
        or closure.ready() is not True
        or not _is_fingerprint(closure.closure_fingerprint)
        or type(inputs) is not Issue39ProductionInputsV1
        or inputs.status is not Issue39ProductionInputStatusV1.READY
        or type(roster) is not Issue39BoundRosterV1
        or roster.status is not Issue39RosterStatusV1.PREPARED
        or roster.counts()[0] < 1
    ):
        raise ValueError


def _prepare_fingerprint(closure, inputs, roster) -> str:
    return _fingerprint(
        "r2-issue39-fresh-prepare-v1",
        {
            "closure_fingerprint": closure.closure_fingerprint,
            "input_manifest_fingerprint": _fingerprint(
                "r2-issue39-production-inputs-v1",
                {
                    "wheelhouse": inputs.manifest_sha256,
                    "runtime": inputs.runtime_fingerprint,
                    "runtime_tree": inputs.runtime_tree_fingerprint,
                    "runtime_entries": inputs.runtime_entry_count,
                    "runtime_bytes": inputs.runtime_total_bytes,
                    "database": inputs.database_identity_fingerprint,
                    "crx": inputs.crx_fingerprint,
                    "config": inputs.config_fingerprint,
                },
            ),
            "roster_fingerprint": roster.roster_fingerprint,
            "worktree_counts": roster.counts(),
        },
    )


def _production_ports() -> _Issue39PreparationPorts:
    from .readiness import observe_fixed_issue39_readiness_v1

    return _Issue39PreparationPorts(
        observe_fixed_issue39_readiness_v1,
        verify_fixed_production_inputs_v1,
        prepare_fixed_roster_v1,
        reverify_fixed_roster_v1,
    )


def _blocked(status):
    from .readiness import _observation

    return _allocate_prepared_execution_v1(
        status, "0" * 64, 0, 0, 0,
        _observation(False, False, False, "0" * 64), None, None,
    )


def _allocate_prepared_execution_v1(
    status, fingerprint, worktrees, embedded, external, closure, inputs, roster
):
    value = object.__new__(Issue39PreparedExecutionV1)
    values = (
        ("status", status),
        ("prepare_fingerprint", fingerprint),
        ("worktree_count", worktrees),
        ("embedded_count", embedded),
        ("external_count", external),
        ("_closure", closure),
        ("_inputs", inputs),
        ("_roster", roster),
    )
    for name, item in values:
        object.__setattr__(value, name, item)
    return value


def _fingerprint(domain: str, value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def _is_fingerprint(value) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )
