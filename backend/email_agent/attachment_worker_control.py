"""Hard-deadline lifecycle control for isolated attachment workers."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any


STARTED = "started"
START_FAILED = "failed"
START_TIMED_OUT = "timed_out"
_CONTROL_WAIT_SECONDS = 0.05
_REAPER_ATTEMPTS = 20
_FAILED = object()
_PENDING = object()


def start_process_with_timeout(process: Any, timeout: float) -> str:
    """Start without allowing a blocking start method to exceed the caller timeout."""
    done = threading.Event()
    quarantine = threading.Event()
    result: dict[str, object] = {}
    reap_lock = threading.Lock()
    reaper_started = False

    def reap_once() -> None:
        nonlocal reaper_started
        with reap_lock:
            if reaper_started:
                return
            reaper_started = True
        _launch_reaper(process)

    def start() -> None:
        try:
            process.start()
            result["started"] = True
        except BaseException:
            result["failed"] = True
        finally:
            done.set()
            if quarantine.is_set():
                reap_once()

    threading.Thread(target=start, daemon=True).start()
    if done.wait(max(0.0, timeout)):
        if result.get("started") is True:
            return STARTED
        reap_once()
        return START_FAILED
    quarantine.set()
    if done.is_set():
        reap_once()
    return START_TIMED_OUT


def cleanup_process(process: Any, wait_seconds: float = 0.0) -> None:
    """Schedule bounded controls and wait only within the caller's remaining budget."""
    done = _launch_reaper(process)
    done.wait(max(0.0, wait_seconds))


def _launch_reaper(process: Any) -> threading.Event:
    done = threading.Event()

    def reap() -> None:
        try:
            _reap_process(process)
        finally:
            done.set()

    threading.Thread(target=reap, daemon=True).start()
    return done


def _reap_process(process: Any) -> None:
    alive = _process_call(process, "is_alive")
    if alive is not False:
        _process_call(process, "terminate")
        _process_call(process, "join", _CONTROL_WAIT_SECONDS)
        alive = _process_call(process, "is_alive")
    if alive is not False:
        _process_call(process, "kill")
        for _attempt in range(_REAPER_ATTEMPTS):
            _process_call(process, "join", _CONTROL_WAIT_SECONDS)
            alive = _process_call(process, "is_alive")
            if alive is False or alive is _FAILED:
                break
            time.sleep(0.01)
    _process_call(process, "close")


def _process_call(process: Any, name: str, *args: object) -> object:
    operation = getattr(process, name, None)
    return _bounded_call(operation, *args) if callable(operation) else _FAILED


def _bounded_call(operation: Callable[..., object], *args: object) -> object:
    done = threading.Event()
    result: dict[str, object] = {}

    def invoke() -> None:
        try:
            result["value"] = operation(*args)
        except BaseException:
            result["value"] = _FAILED
        finally:
            done.set()

    threading.Thread(target=invoke, daemon=True).start()
    if not done.wait(_CONTROL_WAIT_SECONDS):
        return _PENDING
    return result.get("value")
