"""Sanitized bounded runner for read-only local Git commands."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from .errors import MigrationEvidenceError


_MAX_GIT_OUTPUT = 4 * 1024 * 1024


def git_output(
    root: Path,
    arguments: tuple[str, ...],
    *,
    optional: bool = False,
    maximum: int = _MAX_GIT_OUTPUT,
) -> bytes | None:
    """Run one fixed-argument Git read with optional locks disabled."""

    if type(maximum) is not int or not 1 <= maximum <= 20 * 1024 * 1024:
        raise MigrationEvidenceError()
    try:
        payload, returncode, timed_out = _bounded_git_output(
            root,
            arguments,
            maximum,
        )
    except Exception:
        raise MigrationEvidenceError() from None
    if timed_out or returncode != 0:
        if optional and not timed_out:
            return None
        raise MigrationEvidenceError()
    return payload


def _bounded_git_output(
    root: Path,
    arguments: tuple[str, ...],
    maximum: int,
) -> tuple[bytes, int, bool]:
    process = None
    timer = None
    timed_out = threading.Event()
    try:
        process = subprocess.Popen(
            _git_command(arguments),
            cwd=root,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        timer = threading.Timer(
            30,
            _expire_process,
            args=(process, timed_out),
        )
        timer.daemon = True
        timer.start()
        if process.stdout is None:
            raise MigrationEvidenceError()
        payload = process.stdout.read(maximum + 1)
        if len(payload) > maximum:
            _kill_process(process)
            raise MigrationEvidenceError()
        returncode = process.wait()
    finally:
        if timer is not None:
            timer.cancel()
        if process is not None:
            _kill_process(process)
            if process.stdout is not None:
                process.stdout.close()
    return payload, returncode, timed_out.is_set()


def _git_command(arguments: tuple[str, ...]) -> tuple[str, ...]:
    return (
        "git",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        *arguments,
    )


def _expire_process(
    process: subprocess.Popen,
    timed_out: threading.Event,
) -> None:
    if process.poll() is None:
        timed_out.set()
        _kill_process(process)


def _kill_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _git_environment() -> dict[str, str]:
    allowed = {
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SystemRoot",
        "TEMP",
        "TMP",
        "TMPDIR",
        "WINDIR",
    }
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in allowed
    }
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
        }
    )
    return environment
