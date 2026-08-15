"""Fresh bounded complete linked-worktree binding for Issue #39."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


_FIXED_ROOT = Path(r"D:\Projects\email_ai_assistant")
_MAX_WORKTREES = 16


class Issue39RosterStatusV1(str, Enum):
    PREPARED = "ISSUE39_WORKTREE_ROSTER_PREPARED"
    VERIFIED = "ISSUE39_WORKTREE_ROSTER_VERIFIED"
    BLOCKED_DISCOVERY = "BLOCKED_WORKTREE_DISCOVERY"
    BLOCKED_DRIFT = "BLOCKED_WORKTREE_DRIFT"


@dataclass(frozen=True, slots=True, repr=False)
class Issue39WorktreeV1:
    role: str
    placement: str
    selection_fingerprint: str = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _DiscoveredWorktree:
    path: Path = field(repr=False)
    placement: str
    identity_fingerprint: str = field(repr=False)
    admin_identity_fingerprint: str = field(repr=False)
    admin_content_fingerprint: str = field(repr=False)
    head_oid: str = field(repr=False)
    branch_fingerprint: str = field(repr=False)
    common_fingerprint: str = field(repr=False)
    status_fingerprint: str = field(repr=False)
    clean: bool
    admin_path: Path | None = field(default=None, repr=False)
    common_path: Path | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class _RosterPorts:
    discover: object = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class Issue39BoundRosterV1:
    status: Issue39RosterStatusV1
    worktrees: tuple[Issue39WorktreeV1, ...]
    roster_fingerprint: str = field(repr=False)
    _root: Path = field(repr=False)
    _snapshot: tuple[_DiscoveredWorktree, ...] = field(repr=False)

    def counts(self) -> tuple[int, int, int]:
        embedded = sum(item.placement == "embedded" for item in self.worktrees)
        return len(self.worktrees), embedded, len(self.worktrees) - embedded


def prepare_fixed_roster_v1() -> Issue39BoundRosterV1:
    """Discover the complete fixed-root linked-worktree roster once."""

    return _prepare_roster_v1(root=_FIXED_ROOT, ports=_production_ports())


def reverify_fixed_roster_v1(
    bound: Issue39BoundRosterV1,
) -> Issue39BoundRosterV1:
    """Reject every post-prepare roster or identity change."""

    return _reverify_roster_v1(bound=bound, ports=_production_ports())


def _prepare_roster_v1(*, root: Path, ports: _RosterPorts):
    try:
        if type(root) is not type(Path()) or type(ports) is not _RosterPorts:
            raise ValueError
        discovered = ports.discover(root)
        snapshot = _validated_snapshot(discovered)
        worktrees = tuple(
            Issue39WorktreeV1(
                f"worktree_{index:02d}",
                item.placement,
                _selection_fingerprint(item),
            )
            for index, item in enumerate(snapshot, start=1)
        )
        return Issue39BoundRosterV1(
            Issue39RosterStatusV1.PREPARED,
            worktrees,
            _roster_fingerprint(worktrees),
            root,
            snapshot,
        )
    except Exception:
        return _blocked(Issue39RosterStatusV1.BLOCKED_DISCOVERY, root)


def _reverify_roster_v1(*, bound, ports):
    if (
        type(bound) is not Issue39BoundRosterV1
        or bound.status is not Issue39RosterStatusV1.PREPARED
        or type(ports) is not _RosterPorts
    ):
        return _blocked(Issue39RosterStatusV1.BLOCKED_DRIFT, _FIXED_ROOT)
    try:
        current = _validated_snapshot(ports.discover(bound._root))
        if current != bound._snapshot:
            raise ValueError
        rebuilt = _prepare_roster_v1(root=bound._root, ports=ports)
        if (
            rebuilt.status is not Issue39RosterStatusV1.PREPARED
            or rebuilt.worktrees != bound.worktrees
            or rebuilt.roster_fingerprint != bound.roster_fingerprint
        ):
            raise ValueError
        return Issue39BoundRosterV1(
            Issue39RosterStatusV1.VERIFIED,
            bound.worktrees,
            bound.roster_fingerprint,
            bound._root,
            bound._snapshot,
        )
    except Exception:
        return _blocked(Issue39RosterStatusV1.BLOCKED_DRIFT, bound._root)


def _validated_snapshot(value):
    if type(value) is not tuple or not 1 <= len(value) <= _MAX_WORKTREES:
        raise ValueError
    result = tuple(sorted(value, key=lambda item: str(item.path).casefold()))
    paths = set()
    identities = set()
    common = result[0].common_fingerprint
    for item in result:
        if type(item) is not _DiscoveredWorktree:
            raise ValueError
        path_key = os.path.normcase(os.path.abspath(item.path))
        if (
            item.placement not in {"embedded", "external"}
            or not item.clean
            or path_key in paths
            or item.identity_fingerprint in identities
            or item.common_fingerprint != common
            or not _fingerprint_fields_valid(item)
        ):
            raise ValueError
        paths.add(path_key)
        identities.add(item.identity_fingerprint)
    return result


def _fingerprint_fields_valid(item) -> bool:
    values = (
        item.identity_fingerprint,
        item.admin_identity_fingerprint,
        item.admin_content_fingerprint,
        item.branch_fingerprint,
        item.common_fingerprint,
        item.status_fingerprint,
    )
    return _git_oid(item.head_oid) and all(_is_fingerprint(value) for value in values)


def _selection_fingerprint(item) -> str:
    return _fingerprint(
        "r2-issue39-worktree-selection-v1",
        {
            "path_fingerprint": _fingerprint(
                "r2-issue39-worktree-path-v1",
                os.path.normcase(os.path.abspath(item.path)),
            ),
            "placement": item.placement,
            "identity_fingerprint": item.identity_fingerprint,
            "admin_identity_fingerprint": item.admin_identity_fingerprint,
            "admin_path_fingerprint": _fingerprint(
                "r2-issue39-admin-path-v1",
                os.path.normcase(os.path.abspath(item.admin_path)),
            ) if item.admin_path is not None else item.admin_identity_fingerprint,
            "admin_content_fingerprint": item.admin_content_fingerprint,
            "head_oid": item.head_oid,
            "branch_fingerprint": item.branch_fingerprint,
            "common_fingerprint": item.common_fingerprint,
            "status_fingerprint": item.status_fingerprint,
        },
    )


def _roster_fingerprint(worktrees) -> str:
    return _fingerprint(
        "r2-issue39-worktree-roster-v1",
        [
            {
                "role": item.role,
                "placement": item.placement,
                "selection_fingerprint": item.selection_fingerprint,
            }
            for item in worktrees
        ],
    )


def _production_ports() -> _RosterPorts:
    from .roster_windows import production_roster_ports

    return production_roster_ports()


def _blocked(status, root):
    return Issue39BoundRosterV1(status, (), "0" * 64, root, ())


def _fingerprint(domain: str, value) -> str:
    payload = json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def _is_fingerprint(value) -> bool:
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _git_oid(value) -> bool:
    return type(value) is str and len(value) == 40 and all(c in "0123456789abcdef" for c in value)
