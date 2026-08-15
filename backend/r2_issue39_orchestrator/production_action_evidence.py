"""Canonical content-free evidence for each production catalog transition."""

from __future__ import annotations

import hashlib
import json


def action_evidence(host, action, direction, observed_state):
    handler = host._handler(action)
    reverse = direction == "rollback"
    retained_reverse = action.action_name in {
        "main_publication", "rule_fallback_analysis"
    }
    effect_state = (
        action.pre_state_fingerprint if reverse else action.post_state_fingerprint
    )
    if direction not in {"forward", "rollback"} or (
        not action.host_effect and direction != "forward"
    ):
        raise ValueError("R2_ISSUE39_ACTION_EVIDENCE_INVALID")
    effect_present = observed_state == effect_state
    if effect_present and action.host_effect and not handler.present(
        host, action, reverse=(reverse and not retained_reverse)
    ):
        raise ValueError("R2_ISSUE39_ACTION_EVIDENCE_INVALID")
    facts = {
        "schema": "issue39-action-evidence-v1",
        "action": action.action_fingerprint,
        "direction": direction,
        "observed_state": observed_state,
        "specific": (
            _specific(host, action.action_name, direction)
            if effect_present or not action.host_effect
            else {"classified_state": observed_state}
        ),
    }
    return hashlib.sha256(
        b"r2-issue39-action-evidence-v1\0" + _canonical(facts)
    ).hexdigest()


def _specific(host, name, direction):
    if name in {
        "start_a", "rule_fallback_analysis", "stop_a", "database_proof",
        "stopped_layout_audit", "start_b", "final_running_audit",
    }:
        return _validation(host, name, direction)
    if name == "legacy_service_quiescence":
        return _legacy(host, direction)
    from .production_host_state import _current_marker_binding

    kind, identity = _current_marker_binding(host, _action(host, name))
    return {
        "present": True,
        "bound_kind": kind or "catalog_state",
        "bound_identity": identity or _state_fingerprint(host, name, direction),
    }


def _validation(host, name, direction):
    from .production_analysis_state import matching_analysis
    from .production_service import (
        validation_service_observation,
        validation_service_running,
    )
    from .production_validation import _database_proof

    if name in {"start_a", "start_b"} and direction == "forward":
        return validation_service_observation(host, {name})
    if name == "stop_a" and direction == "rollback":
        return validation_service_observation(host, {"start_a", "stop_a"})
    if name in {"start_a", "start_b", "stop_a"}:
        return {"service_stopped": not validation_service_running(host)}
    if name == "rule_fallback_analysis":
        return matching_analysis(host._layout.database_target)
    if name == "database_proof":
        _database_proof(host)
        return _database_fact(host)
    from .production_audit import validation_audit_facts

    return validation_audit_facts(
        host, {"start_b"} if name == "final_running_audit" else None
    )


def _legacy(host, direction):
    if direction == "rollback":
        from .production_service import legacy_recovery_observation

        return legacy_recovery_observation(host)
    return {"status": "STOPPED"}


def _database_fact(host):
    from .production_audit import _file_fact

    return _file_fact(
        host._layout.database_target, 128 * 1024 * 1024, deny_write=False
    )


def _state_fingerprint(host, name, direction):
    handler = host._handler(_action(host, name))
    value = handler.present(host, _action(host, name), reverse=direction == "rollback")
    return hashlib.sha256(f"{name}:{direction}:{value}".encode("ascii")).hexdigest()


def _action(host, name):
    return next(item for item in host._catalog.actions if item.action_name == name)


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
