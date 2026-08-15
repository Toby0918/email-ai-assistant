"""Closed action catalog derived only from one verified Issue #39 prepare."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from .preparation import Issue39PrepareStatusV1, Issue39PreparedExecutionV1
from .roster import Issue39BoundRosterV1, Issue39RosterStatusV1


class Issue39ActionPhaseV1(str, Enum):
    FOUNDATION = "foundation"
    MANAGED_PUBLICATION = "managed_publication"
    VALIDATION = "validation"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39ProductionActionV1:
    sequence: int
    phase: Issue39ActionPhaseV1
    action_name: str
    command: str
    host_effect: bool
    action_fingerprint: str = field(repr=False)
    pre_state_fingerprint: str = field(repr=False)
    post_state_fingerprint: str = field(repr=False)
    _implementation_key: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39ProductionActionV1 is catalog-owned")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39ProductionActionCatalogV1:
    actions: tuple[Issue39ProductionActionV1, ...]
    action_count: int
    worktree_count: int
    catalog_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39ProductionActionCatalogV1 requires builder")


_FOUNDATION = (
    ("legacy_service_quiescence", True),
    ("legacy_anchor_rename", True),
    ("container_publication", True),
    ("main_publication", True),
    ("acl_whole_tree_conformance", True),
    ("repository_relocation", True),
)
_MANAGED = tuple(
    (f"{unit}_{phase}", True)
    for unit in ("runtime", "database", "crx", "config")
    for phase in ("prepare", "publish")
)
_VALIDATION = (
    ("start_a", True, "execute"),
    ("rule_fallback_analysis", True, "execute"),
    ("stop_a", True, "execute"),
    ("database_proof", False, "evidence_verification"),
    ("stopped_layout_audit", False, "final_audit_readiness"),
    ("start_b", True, "execute"),
    ("final_running_audit", False, "final_audit_readiness"),
)


def build_fixed_production_action_catalog_v1(prepared):
    """Return the sole action sequence; no registration surface exists."""

    if not _valid_prepare(prepared):
        raise TypeError("R2_ISSUE39_ACTION_CATALOG_INVALID")
    definitions = (
        tuple(
            (Issue39ActionPhaseV1.FOUNDATION, name, effect, "execute")
            for name, effect in _FOUNDATION
        )
        + tuple(
            (
                Issue39ActionPhaseV1.FOUNDATION,
                f"worktree_reconstruction_{index:02d}",
                True,
                "execute",
            )
            for index in range(1, prepared.worktree_count + 1)
        )
        + tuple(
            (Issue39ActionPhaseV1.MANAGED_PUBLICATION, name, effect, "execute")
            for name, effect in _MANAGED
        )
        + tuple(
            (Issue39ActionPhaseV1.VALIDATION, name, effect, command)
            for name, effect, command in _VALIDATION
        )
    )
    actions = tuple(
        _action(prepared.prepare_fingerprint, index, *definition)
        for index, definition in enumerate(definitions, start=1)
    )
    body = [_action_mapping(item) for item in actions]
    return _allocate(
        Issue39ProductionActionCatalogV1,
        actions=actions,
        action_count=len(actions),
        worktree_count=prepared.worktree_count,
        catalog_fingerprint=_fingerprint(
            "r2-issue39-production-action-catalog-v1",
            {
                "prepare_fingerprint": prepared.prepare_fingerprint,
                "actions": body,
            },
        ),
    )


def _action(prepare_fingerprint, sequence, phase, name, effect, command):
    body = {
        "prepare_fingerprint": prepare_fingerprint,
        "sequence": sequence,
        "phase": phase.value,
        "action_name": name,
        "command": command,
        "host_effect": effect,
        "implementation_key": name,
    }
    action_fingerprint = _fingerprint("r2-issue39-production-action-v1", body)
    pre_state = _fingerprint(
        "r2-issue39-production-action-pre-state-v1",
        {"action_fingerprint": action_fingerprint},
    )
    post_state = _fingerprint(
        "r2-issue39-production-action-post-state-v1",
        {"action_fingerprint": action_fingerprint},
    )
    return _allocate(
        Issue39ProductionActionV1,
        sequence=sequence,
        phase=phase,
        action_name=name,
        command=command,
        host_effect=effect,
        action_fingerprint=action_fingerprint,
        pre_state_fingerprint=pre_state,
        post_state_fingerprint=post_state,
        _implementation_key=name,
    )


def _action_mapping(action):
    return {
        "sequence": action.sequence,
        "phase": action.phase.value,
        "action_name": action.action_name,
        "command": action.command,
        "host_effect": action.host_effect,
        "action_fingerprint": action.action_fingerprint,
        "pre_state_fingerprint": action.pre_state_fingerprint,
        "post_state_fingerprint": action.post_state_fingerprint,
    }


def _valid_prepare(value) -> bool:
    return (
        type(value) is Issue39PreparedExecutionV1
        and value.status is Issue39PrepareStatusV1.VERIFIED
        and 1 <= value.worktree_count <= 16
        and value.embedded_count >= 0
        and value.external_count >= 0
        and value.embedded_count + value.external_count == value.worktree_count
        and type(value._roster) is Issue39BoundRosterV1
        and value._roster.status is Issue39RosterStatusV1.VERIFIED
        and value._roster.counts()
        == (value.worktree_count, value.embedded_count, value.external_count)
        and value._roster.roster_fingerprint != "0" * 64
        and _is_fingerprint(value.prepare_fingerprint)
    )


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


def _allocate(kind, **values):
    value = object.__new__(kind)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value
