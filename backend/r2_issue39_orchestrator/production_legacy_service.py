"""Exact legacy service quiescence and restoration without cleanup."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time

from .durable_io import guard_directory, read_segment, write_segment
from .production_service_windows import (
    PORT,
    command_hash,
    health,
    observe_process,
    port_owner,
)


def observe_legacy_service(root):
    command = _legacy_command(root)
    image = str(root / ".venv" / "Scripts" / "python.exe")
    pid = _read_pid(root / "outputs" / "local_debug_service.pid")
    owner = port_owner()
    if owner is None:
        if pid is not None and observe_process(pid) is not None:
            raise ValueError("R2_ISSUE39_LEGACY_SERVICE_AMBIGUOUS")
        return {
            "status": "STOPPED", "image": image,
            "command_hash": command_hash(command), "creation_time": 0,
        }
    observed = observe_process(owner)
    if (
        pid != owner or observed is None or not health()
        or observed.image.casefold() != image.casefold()
        or observed.command_hash != command_hash(command)
    ):
        raise ValueError("R2_ISSUE39_LEGACY_SERVICE_AMBIGUOUS")
    return {
        "status": "RUNNING", "image": image,
        "command_hash": observed.command_hash,
        "creation_time": observed.creation_time,
    }


def stop_legacy_service(host):
    expected = host._legacy_service
    source = host._layout.source
    root = source if source.joinpath(".git").is_dir() else host._layout.legacy
    current = observe_legacy_service(root)
    if current["status"] == "STOPPED":
        return
    if expected["status"] != "RUNNING" or current != expected:
        raise ValueError("R2_ISSUE39_LEGACY_SERVICE_DRIFT")
    pid = port_owner()
    os.kill(pid, signal.SIGTERM)
    _wait_stopped(pid)


def restore_legacy_service(host, action, attempt_token):
    expected = host._legacy_service
    root = host._layout.source
    if expected["status"] == "STOPPED":
        current = observe_legacy_service(root)
        if current["status"] != "STOPPED":
            raise ValueError("R2_ISSUE39_LEGACY_SERVICE_DRIFT")
        return
    if port_owner() is not None:
        legacy_recovery_observation(host)
        return
    intent = _ensure_recovery_intent(host, action, attempt_token)
    process = _launch_legacy(root, intent)
    _publish_pid(host, root, process.pid)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if legacy_recovery_observation(host)["status"] == "RUNNING":
            _detach_process(process)
            return
        if process.poll() is not None:
            break
        time.sleep(0.05)
    raise ValueError("R2_ISSUE39_LEGACY_SERVICE_RESTORE_FAILED")


def legacy_recovery_observation(host):
    expected = host._legacy_service
    root = host._layout.source
    if expected["status"] == "STOPPED":
        current = observe_legacy_service(root)
        if current["status"] != "STOPPED":
            raise ValueError("R2_ISSUE39_LEGACY_SERVICE_DRIFT")
        return current
    intent = _read_recovery_intent(host)
    pid = _read_pid(root / "outputs" / "local_debug_service.pid")
    owner = port_owner()
    observed = observe_process(owner) if owner is not None else None
    image = str(root / ".venv" / "Scripts" / "python.exe")
    if (
        pid != owner or observed is None or not health()
        or observed.image.casefold() != image.casefold()
        or observed.command_hash != intent["command_hash"]
        or observed.creation_time <= 0
        or observed.creation_time == expected["creation_time"]
    ):
        raise ValueError("R2_ISSUE39_LEGACY_SERVICE_DRIFT")
    return {
        "status": "RUNNING", "image": image,
        "command_hash": observed.command_hash,
        "creation_time": observed.creation_time,
        "nonce": intent["nonce"],
        "llm_provider": intent["llm_provider"],
        "text_fallback_provider": intent["text_fallback_provider"],
    }


def _launch_legacy(root, intent):
    log_path = root / "outputs" / "local_debug_service.log"
    environment = {
        name: os.environ[name]
        for name in ("SYSTEMROOT", "WINDIR", "COMSPEC") if name in os.environ
    }
    environment.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "EMAIL_AGENT_LLM_PROVIDER": "disabled",
        "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "disabled",
        "EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": "false",
    })
    with log_path.open("ab") as stream:
        return subprocess.Popen(
            _recovery_command(root, intent["nonce"]), cwd=root, env=environment,
            stdin=subprocess.DEVNULL,
            stdout=stream, stderr=subprocess.STDOUT, close_fds=True,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            ),
        )


def _publish_pid(host, root, pid):
    pid_path = root / "outputs" / "local_debug_service.pid"
    if os.path.lexists(pid_path):
        from .production_native import move_no_replace

        retained = pid_path.with_name(
            pid_path.name + ".issue39-retained-"
            + host._closure.production.binding_fingerprint[:16]
        )
        if not os.path.lexists(retained):
            move_no_replace(pid_path, retained)
    write_segment(pid_path, f"{pid}\n".encode("ascii"))


def _legacy_command(root):
    return [
        str(root / ".venv" / "Scripts" / "python.exe"), "-B",
        str(root / "scripts" / "run_local_debug.py"),
        "--host", "127.0.0.1", "--port", str(PORT),
    ]


def _recovery_command(root, nonce):
    return [
        *_legacy_command(root),
        "--issue39-legacy-recovery-nonce", nonce,
    ]


def _ensure_recovery_intent(host, action, attempt_token):
    if not _fingerprint(attempt_token):
        raise ValueError("R2_ISSUE39_LEGACY_RECOVERY_INTENT_INVALID")
    path = _recovery_intent_path(host)
    if os.path.lexists(path):
        retained = _read_recovery_intent(host)
        if retained["action_fingerprint"] != action.action_fingerprint:
            raise ValueError("R2_ISSUE39_LEGACY_RECOVERY_INTENT_INVALID")
        return retained
    nonce = hashlib.sha256(
        b"r2-issue39-legacy-recovery-nonce-v1\0"
        + bytes.fromhex(action.action_fingerprint)
        + bytes.fromhex(attempt_token)
    ).hexdigest()
    value = {
        "schema": "issue39-legacy-recovery-intent-v1",
        "action_fingerprint": action.action_fingerprint,
        "attempt_fingerprint": attempt_token,
        "nonce": nonce,
        "command_hash": command_hash(_recovery_command(host._layout.source, nonce)),
        "llm_provider": "disabled",
        "text_fallback_provider": "disabled",
        "private_knowledge_enabled": False,
    }
    payload = _canonical(value)
    with guard_directory(path.parent, flush=True):
        if os.path.lexists(path):
            raise ValueError("R2_ISSUE39_LEGACY_RECOVERY_INTENT_INVALID")
        write_segment(path, payload)
    return value


def _read_recovery_intent(host):
    payload = read_segment(_recovery_intent_path(host))
    value = json.loads(payload)
    required = {
        "schema", "action_fingerprint", "attempt_fingerprint", "nonce",
        "command_hash", "llm_provider", "text_fallback_provider",
        "private_knowledge_enabled",
    }
    if (
        _canonical(value) != payload or set(value) != required
        or value["schema"] != "issue39-legacy-recovery-intent-v1"
        or value["llm_provider"] != "disabled"
        or value["text_fallback_provider"] != "disabled"
        or value["private_knowledge_enabled"] is not False
        or not all(_fingerprint(value[name]) for name in (
            "action_fingerprint", "attempt_fingerprint", "nonce", "command_hash"
        ))
        or command_hash(_recovery_command(host._layout.source, value["nonce"]))
        != value["command_hash"]
    ):
        raise ValueError("R2_ISSUE39_LEGACY_RECOVERY_INTENT_INVALID")
    return value


def _recovery_intent_path(host):
    from .production_host_state import _state_directory

    return _state_directory(host) / "legacy-recovery.intent"


def _read_pid(path):
    try:
        payload = path.read_bytes()
        if len(payload) > 32:
            raise ValueError
        value = int(payload.strip())
        return value if 0 < value < 2**31 else None
    except FileNotFoundError:
        return None


def _wait_stopped(pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if port_owner() is None and observe_process(pid) is None:
            return
        time.sleep(0.05)
    raise ValueError("R2_ISSUE39_LEGACY_SERVICE_STOP_FAILED")


def _detach_process(process):
    handle = getattr(process, "_handle", None)
    if handle is None:
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    handle.Close()
    process._handle = None
    process.returncode = 0


def _canonical(value):
    return (json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ) + "\n").encode("ascii")


def _fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )
