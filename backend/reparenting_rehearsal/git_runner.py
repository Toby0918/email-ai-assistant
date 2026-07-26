"""Bounded Git execution confined to one synthetic scope."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from .errors import RehearsalError


_ALLOWED_VERBS = frozenset(
    {
        "add",
        "commit",
        "config",
        "for-each-ref",
        "init",
        "ls-files",
        "remote",
        "rev-list",
        "rev-parse",
        "status",
        "symbolic-ref",
        "update-ref",
        "worktree",
    }
)
_MAX_OUTPUT_BYTES = 1024 * 1024
_TIMEOUT_SECONDS = 20


def git_output(
    scope: Path,
    working_directory: Path,
    arguments: tuple[str, ...],
) -> str:
    """Run one allowlisted local Git command."""

    if (
        type(arguments) is not tuple
        or not arguments
        or arguments[0] not in _ALLOWED_VERBS
        or any(type(item) is not str or "\x00" in item for item in arguments)
    ):
        raise RehearsalError()
    root = _require_inside(scope, working_directory)
    command = (
        "git",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "protocol.file.allow=always",
        "-C",
        str(root),
        *arguments,
    )
    completed = _run_command(scope, command)
    if (
        completed.returncode != 0
        or len(completed.stdout) > _MAX_OUTPUT_BYTES
        or len(completed.stderr) > _MAX_OUTPUT_BYTES
    ):
        raise RehearsalError()
    try:
        return completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise RehearsalError() from None


def _run_command(
    scope: Path,
    command: tuple[str, ...],
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=_TIMEOUT_SECONDS,
            check=False,
            env=_git_environment(scope),
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )
    except Exception:
        raise RehearsalError() from None


def _require_inside(scope: Path, path: Path) -> Path:
    try:
        root = scope.resolve(strict=True)
        candidate = path.resolve(strict=True)
    except Exception:
        raise RehearsalError() from None
    if candidate != root and root not in candidate.parents:
        raise RehearsalError()
    return candidate


def _git_environment(scope: Path) -> dict[str, str]:
    environment = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_PAGER": "",
        "GIT_EDITOR": "true",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    for name in ("PATH", "SystemRoot", "COMSPEC", "WINDIR"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    process_temp = scope / "process-temp"
    environment["TEMP"] = str(process_temp)
    environment["TMP"] = str(process_temp)
    return environment
