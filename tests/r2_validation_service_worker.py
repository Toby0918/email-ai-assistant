"""Persistent provider-disabled service used only by the Issue #81 sandbox."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path


def _write(value: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(value, sort_keys=True) + "\n")
    sys.stdout.flush()


def _append(path: Path, value: dict[str, object]) -> None:
    with path.open("ab", buffering=0) as stream:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        stream.write(payload.encode("ascii") + b"\n")
        os.fsync(stream.fileno())


def main() -> int:
    database_path = Path(sys.argv[1])
    journal_path = Path(sys.argv[2])
    config_path = Path(sys.argv[3])
    _verify_config(config_path)
    if journal_path.exists():
        return 4
    journal_path.touch(exist_ok=False)
    start_time_ns = time.time_ns()
    _write(
        {
            "pid": os.getpid(),
            "start_time_ns": start_time_ns,
            "primary_provider": "disabled",
            "fallback_provider": "disabled",
        }
    )
    analyses = 0
    writes = 0
    bound = False
    for raw in sys.stdin:
        command = json.loads(raw)
        if command.get("command") == "bind" and not bound:
            expected = {
                "command",
                "profile",
                "runtime",
                "config",
                "database",
                "nonce",
                "port",
            }
            if set(command) != expected:
                return 5
            _append(
                journal_path,
                {
                    **command,
                    "event": "started",
                    "pid": os.getpid(),
                    "start_time_ns": start_time_ns,
                    "primary_provider": "disabled",
                    "fallback_provider": "disabled",
                },
            )
            bound = True
            _write({"pid": os.getpid(), "bound": True})
            continue
        if not bound:
            return 5
        if command == {"command": "health"}:
            value = {
                "event": "health",
                "pid": os.getpid(),
                "healthy": True,
                "analysis_count": analyses,
                "write_count": writes,
            }
            _append(journal_path, value)
            _write(value)
            continue
        if set(command) == {"command", "request", "result"} and command[
            "command"
        ] == "analyze_rule_fallback":
            if analyses != 0 or writes != 0:
                return 6
            with closing(sqlite3.connect(database_path)) as connection, connection:
                connection.execute(
                    "INSERT INTO analyses(result_fingerprint) VALUES (?)",
                    (command["result"],),
                )
            analyses += 1
            writes += 1
            value = {
                    "event": "analysis",
                    "pid": os.getpid(),
                    "request": command["request"],
                    "result": command["result"],
                    "analysis_engine_source": "rule_fallback",
                    "provider_attempts": 0,
                    "safe": True,
                    "analysis_count": analyses,
                    "write_count": writes,
                }
            _append(journal_path, value)
            _write(value)
            continue
        if command == {"command": "stop"}:
            value = {
                    "event": "stopped",
                    "pid": os.getpid(),
                    "analysis_count": analyses,
                    "write_count": writes,
                    "stopped": True,
                }
            _append(journal_path, value)
            _write(value)
            return 0
        return 7
    return 8


def _verify_config(path):
    first = path.read_bytes()
    second = path.read_bytes()
    expected = (
        b"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=example.test,internal.example\n"
        b"EMAIL_AGENT_LOG_LEVEL=WARNING\n"
    )
    if first != second or first != expected:
        raise RuntimeError("R2_VALIDATION_CONFIG_INVALID")


if __name__ == "__main__":
    raise SystemExit(main())
