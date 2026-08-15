"""Fixed provider-disabled two-start validation and audits."""

from __future__ import annotations

import json
import hashlib
import os
import sqlite3
import urllib.request

from .terminal_seal import Issue39LegacyAuditV1, Issue39TerminalAuditV1


_TOP = {
    "main", "Runtimes", "LocalData", "RuntimeTemp", "Logs", "Artifacts",
    "Worktrees", "Config", "OperatorPrivate",
}


def mutate_validation(host, action, direction, attempt_token):
    name = action.action_name
    if name in {"start_a", "start_b"}:
        from .production_service import start_validation_service, stop_validation_service

        return (
            start_validation_service(host, action, attempt_token)
            if direction == "forward"
            else stop_validation_service(host, {name})
        )
    if name == "stop_a":
        from .production_service import start_validation_service, stop_validation_service

        if direction == "forward":
            return stop_validation_service(host, {"start_a"})
        original_start = next(
            item for item in host._catalog.actions if item.action_name == "start_a"
        )
        return start_validation_service(host, original_start, attempt_token)
    raise ValueError("R2_ISSUE39_VALIDATION_ACTION_INVALID")


def validation_state(host, name, reverse=False):
    from .production_service import validation_service_running

    if name in {"start_a", "start_b"}:
        running = validation_service_running(host, {name})
        return not running if reverse else running
    if name == "stop_a":
        running = validation_service_running(host, {"start_a", "stop_a"})
        return running if reverse else not running
    if name == "rule_fallback_analysis":
        from .production_analysis_state import matching_analysis

        present = matching_analysis(
            host._layout.database_target, allow_absent=True
        ) is not None
        return present
    return False


def run_validation(host, name):
    if name == "rule_fallback_analysis":
        from .production_service import validation_service_running

        if not validation_service_running(host, {"start_a"}):
            raise ValueError("R2_ISSUE39_SERVICE_NOT_RUNNING")
        return _analysis()
    if name == "database_proof":
        return _database_proof(host)
    if name == "stopped_layout_audit":
        from .production_service import validation_service_running

        if validation_service_running(host):
            raise ValueError("R2_ISSUE39_SERVICE_STILL_RUNNING")
        return _audit(host)
    if name == "final_running_audit":
        from .production_service import validation_service_running

        if not validation_service_running(host, {"start_b"}):
            raise ValueError("R2_ISSUE39_SERVICE_NOT_RUNNING")
        return _audit(host)
    raise ValueError("R2_ISSUE39_VALIDATION_ACTION_INVALID")


def _analysis():
    from .production_analysis_state import synthetic_analysis_payload

    payload = json.dumps(synthetic_analysis_payload()).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:8765/api/analyze-current-email",
        data=payload,
        headers={"Content-Type": "application/json", "Host": "127.0.0.1:8765"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read(64 * 1024 + 1)
    value = json.loads(body, object_pairs_hook=_strict_pairs)
    analysis = value.get("analysis")
    engine = analysis.get("analysis_engine") if type(analysis) is dict else None
    if (
        len(body) > 64 * 1024 or value.get("ok") is not True
        or type(value.get("saved_id")) is not int or value["saved_id"] <= 0
        or type(engine) is not dict or engine.get("source") != "rule_fallback"
    ):
        raise ValueError("R2_ISSUE39_RULE_FALLBACK_INVALID")
    return value["saved_id"]


def _database_proof(host):
    path = host._layout.database_target
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone() != ("ok",):
            raise ValueError("R2_ISSUE39_DATABASE_PROOF_INVALID")
        tables = connection.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()
        if type(tables[0]) is not int or tables[0] < 1:
            raise ValueError("R2_ISSUE39_DATABASE_PROOF_INVALID")
    finally:
        connection.close()


def _audit(host):
    layout = host._layout
    if set(item.name for item in layout.container.iterdir()) != _TOP:
        raise ValueError("R2_ISSUE39_LAYOUT_AUDIT_INVALID")
    if any(path.is_symlink() or path.is_junction() for path in layout.container.iterdir()):
        raise ValueError("R2_ISSUE39_LAYOUT_AUDIT_INVALID")
    config = layout.config_target.read_text(encoding="ascii")
    expected = {
        "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=cndlf.com",
        "EMAIL_AGENT_LOG_LEVEL=INFO",
    }
    if set(config.splitlines()) != expected:
        raise ValueError("R2_ISSUE39_LAYOUT_AUDIT_INVALID")
    if not (
        (layout.runtime_target / "Scripts" / "python.exe").is_file()
        and layout.database_target.is_file()
        and layout.crx_target.is_file()
        and layout.main.joinpath(".git").is_dir()
    ):
        raise ValueError("R2_ISSUE39_LAYOUT_AUDIT_INVALID")


def build_terminal_audit(host, catalog, journal_head_fingerprint):
    from .production_audit import terminal_audit_reads

    validation, first, second = terminal_audit_reads(
        host, catalog, journal_head_fingerprint
    )
    return Issue39TerminalAuditV1.create(
        catalog=catalog,
        journal_head_fingerprint=journal_head_fingerprint,
        validation_receipt_fingerprint=validation,
        first_read_fingerprint=first,
        second_read_fingerprint=second,
    )


def build_legacy_audit(host, catalog, journal_head_fingerprint):
    from .production_audit import legacy_audit_reads

    first, second = legacy_audit_reads(host, catalog, journal_head_fingerprint)
    return Issue39LegacyAuditV1.create(
        catalog=catalog,
        journal_head_fingerprint=journal_head_fingerprint,
        first_read_fingerprint=first,
        second_read_fingerprint=second,
    )


def _strict_pairs(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("R2_ISSUE39_VALIDATION_JSON_INVALID")
        value[name] = item
    return value
