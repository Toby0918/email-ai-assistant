"""Strict content-free operator context for Issue #39 confirmations."""

from __future__ import annotations

import re
import sys

from backend.r2_production_binding import ProductionCommandV2


_PREFIX = "ISSUE39_CONFIRMATION_CONTEXT_V1"
_PHASES = {"preflight", "evidence", "catalog", "terminal"}
_DIRECTIONS = {"none", "forward", "rollback"}
_STATES = {
    "READY_TO_OBSERVE",
    "PREFLIGHT_CLAIM_PENDING",
    "LEDGER_ABSENT_EXACT",
    "EVIDENCE_ABSENT_EXACT",
    "EVIDENCE_CLASSIFIED_EXACT",
    "PRE_STATE_EXACT",
    "POST_STATE_EXACT",
    "EFFECT_ABSENT_EXACT",
    "EFFECT_PRESENT_EXACT",
    "EFFECT_PARTIAL_RESUMABLE",
    "FINAL_AUDIT_EXACT",
    "LEGACY_AUDIT_EXACT",
}
_PREFLIGHT_COMMANDS = {
    command.value: command
    for command in (
        ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
        ProductionCommandV2.HOST_BASELINE,
        ProductionCommandV2.EVIDENCE_REVIEW,
        ProductionCommandV2.EVIDENCE_VERIFICATION,
        ProductionCommandV2.FINAL_AUDIT_READINESS,
        ProductionCommandV2.RECOVERY_INSPECTION,
    )
}
_EVIDENCE_OPERATIONS = {
    "journal_genesis",
    "evidence_publication",
    "evidence_resume",
}
_CATALOG_OPERATIONS = {
    "legacy_service_quiescence",
    "legacy_anchor_rename",
    "container_publication",
    "main_publication",
    "acl_whole_tree_conformance",
    "repository_relocation",
    "runtime_prepare",
    "runtime_publish",
    "database_prepare",
    "database_publish",
    "crx_prepare",
    "crx_publish",
    "config_prepare",
    "config_publish",
    "start_a",
    "rule_fallback_analysis",
    "stop_a",
    "database_proof",
    "stopped_layout_audit",
    "start_b",
    "final_running_audit",
}
_TERMINAL_OPERATIONS = {
    "cutover_success_seal",
    "legacy_restoration_seal",
}
_CATALOG_COMMANDS = {
    **{name: ProductionCommandV2.EXECUTE for name in _CATALOG_OPERATIONS},
    "database_proof": ProductionCommandV2.EVIDENCE_VERIFICATION,
    "stopped_layout_audit": ProductionCommandV2.FINAL_AUDIT_READINESS,
    "final_running_audit": ProductionCommandV2.FINAL_AUDIT_READINESS,
}
_EVIDENCE_CONTEXTS = {
    "journal_genesis": (
        ProductionCommandV2.EVIDENCE_PUBLICATION,
        "LEDGER_ABSENT_EXACT",
    ),
    "evidence_publication": (
        ProductionCommandV2.EVIDENCE_PUBLICATION,
        "EVIDENCE_ABSENT_EXACT",
    ),
    "evidence_resume": (
        ProductionCommandV2.RESUME,
        "EVIDENCE_CLASSIFIED_EXACT",
    ),
}
_TERMINAL_CONTEXTS = {
    "cutover_success_seal": (
        ProductionCommandV2.RESUME,
        "FINAL_AUDIT_EXACT",
    ),
    "legacy_restoration_seal": (
        ProductionCommandV2.ROLLBACK,
        "LEGACY_AUDIT_EXACT",
    ),
}
_WORKTREE_OPERATION = re.compile(r"worktree_reconstruction_(0[1-9]|1[0-6])\Z")


def format_confirmation_context_v1(
    *, phase, operation, command, direction, current_state, sequence, total
):
    """Return the only printable operator-review line for one live claim."""

    if (
        type(phase) is not str
        or phase not in _PHASES
        or type(operation) is not str
        or type(command) is not ProductionCommandV2
        or type(direction) is not str
        or direction not in _DIRECTIONS
        or type(current_state) is not str
        or current_state not in _STATES
        or type(sequence) is not int
        or type(total) is not int
        or not 1 <= sequence <= total <= 64
        or not _valid_combination(
            phase, operation, command, direction, current_state
        )
    ):
        raise ValueError("R2_ISSUE39_CONFIRMATION_CONTEXT_INVALID")
    line = (
        f"{_PREFIX} phase={phase} operation={operation} "
        f"command={command.value} direction={direction} "
        f"state={current_state} sequence={sequence} total={total}"
    )
    if len(line) >= 256 or not line.isascii() or any(
        not 32 <= ord(character) <= 126 for character in line
    ):
        raise ValueError("R2_ISSUE39_CONFIRMATION_CONTEXT_INVALID")
    return line


def display_confirmation_context_v1(**values):
    line = format_confirmation_context_v1(**values)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
    return line


def _valid_combination(phase, operation, command, direction, state):
    if phase == "preflight":
        return _valid_preflight(operation, command, direction, state)
    if phase == "evidence":
        return _valid_evidence(operation, command, direction, state)
    if phase == "catalog":
        return _valid_catalog(operation, command, direction, state)
    return (
        phase == "terminal"
        and _valid_terminal(operation, command, direction, state)
    )


def _valid_preflight(operation, command, direction, state):
    fixed_command = _PREFLIGHT_COMMANDS.get(operation)
    return direction == "none" and (
        (command is fixed_command and state == "READY_TO_OBSERVE")
        or (
            fixed_command is not None
            and command is ProductionCommandV2.RESUME
            and state == "PREFLIGHT_CLAIM_PENDING"
        )
    )


def _valid_evidence(operation, command, direction, state):
    return (
        operation in _EVIDENCE_OPERATIONS
        and direction == "none"
        and (command, state) == _EVIDENCE_CONTEXTS[operation]
    )


def _valid_catalog(operation, command, direction, state):
    fixed_command = (
        ProductionCommandV2.EXECUTE
        if _WORKTREE_OPERATION.fullmatch(operation) is not None
        else _CATALOG_COMMANDS.get(operation)
    )
    if fixed_command is None or direction not in {"forward", "rollback"}:
        return False
    if command is ProductionCommandV2.RESUME:
        return state in {
            "EFFECT_ABSENT_EXACT",
            "EFFECT_PRESENT_EXACT",
            "EFFECT_PARTIAL_RESUMABLE",
        }
    return (
        (command is fixed_command and direction == "forward"
         and state == "PRE_STATE_EXACT")
        or (
            command is ProductionCommandV2.ROLLBACK
            and direction == "rollback"
            and state == "POST_STATE_EXACT"
        )
    )


def _valid_terminal(operation, command, direction, state):
    return (
        operation in _TERMINAL_OPERATIONS
        and direction == "none"
        and (command, state) == _TERMINAL_CONTEXTS[operation]
    )
