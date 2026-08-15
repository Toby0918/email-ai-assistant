"""Stable observations and retained action receipts for the fixed host."""

from __future__ import annotations

import hashlib
import os
import stat
import re
from pathlib import Path

from .durable_io import guard_directory, read_segment, write_segment


_ROOT = Path(r"D:\IncidentArchives\email_ai_assistant\issue38")
_RETAINED_REVERSE = {"main_publication", "rule_fallback_analysis"}


def observe_action(host, action):
    if not action.host_effect:
        return action.pre_state_fingerprint
    handler = host._handler(action)
    forward = _marker(host, action, "forward")
    reverse = _marker(host, action, "rollback")
    forward_exists = os.path.lexists(forward)
    reverse_exists = os.path.lexists(reverse)
    if reverse_exists:
        _require_marker(host, reverse, action, "rollback")
        if not forward_exists:
            raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
        _require_marker(host, forward, action, "forward")
        reverse_present = (
            handler.present(host, action)
            if action.action_name in _RETAINED_REVERSE
            else handler.present(host, action, reverse=True)
        )
        if not reverse_present:
            raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
        return action.pre_state_fingerprint
    if forward_exists:
        return _forward_marked_state(host, action, handler, forward)
    if (
        action.action_name == "legacy_service_quiescence"
        and host._legacy_service["status"] == "STOPPED"
    ):
        return action.pre_state_fingerprint
    present = handler.present(host, action)
    reversed_present = (
        False if action.action_name in _RETAINED_REVERSE
        else handler.present(host, action, reverse=True)
    )
    if present and reversed_present:
        raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
    partial = handler.partial(host, action, "forward")
    if partial is not None:
        return partial
    return (
        action.post_state_fingerprint if present else action.pre_state_fingerprint
    )


def _forward_marked_state(host, action, handler, forward):
    _require_marker(host, forward, action, "forward")
    present = handler.present(host, action)
    reversed_present = (
        False if action.action_name in _RETAINED_REVERSE or (
            action.action_name == "legacy_service_quiescence"
            and host._legacy_service["status"] == "STOPPED"
        )
        else handler.present(host, action, reverse=True)
    )
    if present and reversed_present:
        raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
    if present:
        return action.post_state_fingerprint
    if reversed_present:
        return action.pre_state_fingerprint
    reverse_partial = handler.partial(host, action, "rollback")
    if reverse_partial is not None:
        return reverse_partial
    raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")


def seal_action(host, action, direction):
    path = _marker(host, action, direction)
    if os.path.lexists(path):
        _require_marker(host, path, action, direction)
        return
    directory = path.parent
    if not os.path.lexists(directory):
        with guard_directory(directory.parent, flush=True):
            directory.mkdir(mode=0o700)
    kind, identity = _current_marker_binding(host, action)
    payload = _payload(action, direction, bound_kind=kind, bound_identity=identity)
    with guard_directory(directory, flush=True):
        write_segment(path, payload)
        if read_segment(path) != payload:
            raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")


def reverify_host(host, action, direction):
    state = _state_directory(host)
    if os.path.lexists(state):
        with guard_directory(state, flush=False):
            entries = tuple(state.iterdir())
            if len(entries) > host._catalog.action_count * 2 + 4:
                raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
            known = {
                _marker(host, action, direction).name
                for action in host._catalog.actions
                for direction in ("forward", "rollback")
            }
            unknown = tuple(item for item in entries if item.name not in known)
            allowed_unknown = all(
                item.name == "legacy-recovery.intent"
                or re.fullmatch(
                    r"svc-[0-9]{4}-[0-9a-f]{24}\.intent", item.name
                ) is not None
                for item in unknown
            )
            if not allowed_unknown:
                raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
            if unknown:
                from .production_service import _intents

                _intents(host)
                if any(item.name == "legacy-recovery.intent" for item in unknown):
                    from .production_legacy_service import _read_recovery_intent

                    _read_recovery_intent(host)
    _require_plain_directory(host._layout.projects)
    from .production_roster_reverify import reverify_evolving_roster

    reverify_evolving_roster(host, action, direction)
    return True


def _marker(host, action, direction):
    return _state_directory(host) / (
        f"{action.sequence:04d}-{action.action_fingerprint}-{direction}.p39a"
    )


def _state_directory(host):
    return _ROOT / (
        ".issue39-host-state-" + host._closure.production.binding_fingerprint
    )


def _payload(
    action, direction, *, bound_kind=None, bound_identity=None
):
    payload = (
        "issue39-host-action-v1\n"
        f"sequence={action.sequence}\n"
        f"action={action.action_fingerprint}\n"
        f"direction={direction}\n"
    )
    if bound_identity is not None:
        payload += f"bound_kind={bound_kind}\n"
        payload += f"bound_identity={bound_identity}\n"
    return payload.encode("ascii")


def _require_marker(host, path, action, direction):
    payload = read_segment(path)
    kind, identity = _current_marker_binding(host, action)
    if payload != _payload(
        action, direction, bound_kind=kind, bound_identity=identity
    ):
        raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")


def database_identity_bound(host, action):
    marker = _marker(host, action, "forward")
    if not os.path.lexists(marker):
        return False
    _require_marker(host, marker, action, "forward")
    return True


def _current_marker_binding(host, action):
    if action.action_name == "container_publication":
        from backend.cutover_repository_transaction.windows_identity import (
            directory_identity,
        )

        candidates = (host._layout.container, host._layout.failed)
        present = tuple(path for path in candidates if os.path.lexists(path))
        if len(present) != 1:
            raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
        return "container_directory", directory_identity(present[0])
    if action.action_name == "main_publication":
        from backend.cutover_repository_transaction.windows_identity import (
            directory_identity,
        )

        return "main_directory", directory_identity(host._layout.main)
    if action.action_name not in {"database_prepare", "database_publish"}:
        return None, None
    return "database_file", _current_database_identity(host, action)


def _current_database_identity(host, action):
    from .input_identity import file_identity_fingerprint

    stage = host._layout.database_stage
    paths = (
        stage,
        host._layout.database_target,
        retained_path(host, action, stage),
    )
    present = tuple(path for path in paths if os.path.lexists(path))
    if len(present) != 1:
        raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")
    return file_identity_fingerprint(present[0])


def _require_plain_directory(path):
    metadata = path.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & 0x400
        or path.is_symlink() or path.is_junction()
    ):
        raise ValueError("R2_ISSUE39_HOST_STATE_INVALID")


def retained_path(host, action, path):
    suffix = hashlib.sha256(
        b"r2-issue39-retained-action-v1\0"
        + bytes.fromhex(action.action_fingerprint)
    ).hexdigest()[:16]
    return path.with_name(path.name + ".rollback-" + suffix)
