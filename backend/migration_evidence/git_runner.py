"""Sanitized bounded runner for read-only local Git commands."""

from __future__ import annotations

import os
import subprocess
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
        completed = subprocess.run(
            (
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.untrackedCache=false",
                *arguments,
            ),
            cwd=root,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except Exception:
        raise MigrationEvidenceError() from None
    if completed.returncode != 0:
        if optional:
            return None
        raise MigrationEvidenceError()
    if len(completed.stdout) > maximum:
        raise MigrationEvidenceError()
    return completed.stdout


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
