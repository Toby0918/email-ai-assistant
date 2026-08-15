"""Cleanup-free validation service with exact process and port ownership."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import time

from .durable_io import read_segment, write_segment
from .production_host_state import _state_directory
from .production_service_windows import (
    PORT as _PORT,
    command_hash as _command_hash,
    health as _health,
    observe_process as _observe_process,
    port_owner as _port_owner,
)


def start_validation_service(host, action, attempt_token):
    intent = _ensure_intent(host, action, attempt_token)
    running = _running_for_intent(host, intent)
    if running is not None:
        return running
    if _port_owner() is not None:
        raise ValueError("R2_ISSUE39_SERVICE_PORT_COLLISION")
    command = _command(host, intent["nonce"])
    if _command_hash(command) != intent["command_hash"]:
        raise ValueError("R2_ISSUE39_SERVICE_INTENT_INVALID")
    log = host._layout.logs / (
        f".issue39-validation-{action.sequence:04d}-{attempt_token[:24]}.log"
    )
    environment = {
        name: os.environ[name]
        for name in ("SYSTEMROOT", "WINDIR", "COMSPEC") if name in os.environ
    }
    environment.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "EMAIL_AGENT_LLM_PROVIDER": "disabled",
        "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "disabled",
    })
    with log.open("xb") as stream:
        process = subprocess.Popen(
            command, cwd=host._layout.main, env=environment,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            ),
        )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        observed = _running_for_intent(host, intent)
        if observed is not None and observed.pid == process.pid:
            _detach_process(process)
            return observed
        if process.poll() is not None:
            break
        time.sleep(0.05)
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)
    raise ValueError("R2_ISSUE39_SERVICE_START_FAILED")


def stop_validation_service(host, action_names):
    pid = _port_owner()
    if pid is None:
        return
    matches = []
    for intent in _intents(host):
        if intent["action_name"] in action_names:
            observed = _running_for_intent(host, intent)
            if observed is not None and observed.pid == pid:
                matches.append(observed)
    if len(matches) != 1:
        raise ValueError("R2_ISSUE39_SERVICE_IDENTITY_INVALID")
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _port_owner() is None and _observe_process(pid) is None:
            try:
                _require_database_released(host)
                return
            except Exception:
                pass
        time.sleep(0.05)
    raise ValueError("R2_ISSUE39_SERVICE_STOP_FAILED")


def validation_service_running(host, action_names=None):
    pid = _port_owner()
    if pid is None:
        return False
    matches = []
    for intent in _intents(host):
        if action_names is None or intent["action_name"] in action_names:
            observed = _running_for_intent(host, intent)
            if observed is not None and observed.pid == pid:
                matches.append(observed)
    if len(matches) != 1:
        raise ValueError("R2_ISSUE39_SERVICE_IDENTITY_INVALID")
    return _health() is True


def validation_service_observation(host, action_names):
    """Return the exact live validation process only after all ownership checks."""

    pid = _port_owner()
    if pid is None:
        raise ValueError("R2_ISSUE39_SERVICE_NOT_RUNNING")
    matches = []
    for intent in _intents(host):
        if intent["action_name"] in action_names:
            observed = _running_for_intent(host, intent)
            if observed is not None and observed.pid == pid:
                matches.append((intent, observed))
    if len(matches) != 1 or not _health():
        raise ValueError("R2_ISSUE39_SERVICE_IDENTITY_INVALID")
    intent, observed = matches[0]
    return {
        "pid": observed.pid,
        "image": observed.image.casefold(),
        "command_hash": observed.command_hash,
        "creation_time": observed.creation_time,
        "nonce": intent["nonce"],
        "intent_fingerprint": hashlib.sha256(_canonical(intent)).hexdigest(),
        "port_owner": pid,
        "provider_attempt_count": 0,
    }


def observe_legacy_service(root):
    from .production_legacy_service import observe_legacy_service as observe

    return observe(root)


def stop_legacy_service(host):
    from .production_legacy_service import stop_legacy_service as stop

    stop(host)


def restore_legacy_service(host, action, attempt_token):
    from .production_legacy_service import restore_legacy_service as restore

    restore(host, action, attempt_token)


def legacy_recovery_observation(host):
    from .production_legacy_service import legacy_recovery_observation as observe

    return observe(host)


def _ensure_intent(host, action, attempt):
    if not _fingerprint(attempt):
        raise ValueError("R2_ISSUE39_SERVICE_ATTEMPT_INVALID")
    nonce = hashlib.sha256(
        b"r2-issue39-service-nonce-v1\0"
        + bytes.fromhex(action.action_fingerprint)
        + bytes.fromhex(attempt)
    ).hexdigest()
    command = _command(host, nonce)
    value = {
        "schema": "issue39-validation-service-intent-v1",
        "action_name": action.action_name,
        "action_fingerprint": action.action_fingerprint,
        "attempt_fingerprint": attempt,
        "nonce": nonce,
        "command_hash": _command_hash(command),
        "llm_provider": "disabled",
        "text_fallback_provider": "disabled",
    }
    payload = _canonical(value)
    path = _state_directory(host) / (
        f"svc-{action.sequence:04d}-{attempt[:24]}.intent"
    )
    if os.path.lexists(path):
        if read_segment(path) != payload:
            raise ValueError("R2_ISSUE39_SERVICE_INTENT_INVALID")
    else:
        write_segment(path, payload)
    return value


def _intents(host):
    root = _state_directory(host)
    values = []
    for path in sorted(root.glob("svc-*.intent")):
        payload = read_segment(path)
        value = json.loads(payload)
        if _canonical(value) != payload or set(value) != {
            "schema", "action_name", "action_fingerprint",
            "attempt_fingerprint", "nonce", "command_hash",
            "llm_provider", "text_fallback_provider",
        } or value["schema"] != "issue39-validation-service-intent-v1":
            raise ValueError("R2_ISSUE39_SERVICE_INTENT_INVALID")
        if (
            value["llm_provider"] != "disabled"
            or value["text_fallback_provider"] != "disabled"
        ):
            raise ValueError("R2_ISSUE39_SERVICE_INTENT_INVALID")
        values.append(value)
    if len(values) > 16:
        raise ValueError("R2_ISSUE39_SERVICE_INTENT_INVALID")
    return tuple(values)


def _running_for_intent(host, intent):
    pid = _port_owner()
    if pid is None:
        return None
    observed = _observe_process(pid)
    expected_image = str(host._layout.runtime_target / "Scripts" / "python.exe")
    if (
        observed is None
        or observed.image.casefold() != expected_image.casefold()
        or observed.command_hash != intent["command_hash"]
        or not _health()
    ):
        return None
    return observed


def _command(host, nonce):
    return [
        str(host._layout.runtime_target / "Scripts" / "python.exe"),
        "-X", "frozen_modules=on", "-I", "-B", "-S",
        str(host._layout.main / "scripts" / "run_local_debug.py"),
        "--host", "127.0.0.1", "--port", str(_PORT),
        "--managed-container", "--issue39-validation-nonce", nonce,
    ]


def _require_database_released(host):
    from backend.cutover_managed_activation.windows_file_handles import (
        WindowsReadHandleApi,
    )

    path = host._layout.database_target
    api = WindowsReadHandleApi()
    handle = api.open_existing(path, deny_write=True)
    try:
        observed = api.observe(handle)
        api.require_stable(handle, observed, path)
    finally:
        api.close(handle)


def _detach_process(process):
    """Close only the creator's process handle; the validated service persists."""

    handle = getattr(process, "_handle", None)
    if handle is None:
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    handle.Close()
    process._handle = None
    process.returncode = 0


def _canonical(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("ascii")


def _fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )
