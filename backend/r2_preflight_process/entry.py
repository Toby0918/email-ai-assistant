"""Production preflight executable remains unavailable before Issue #39."""

from __future__ import annotations

import sys

from .contracts import (
    PREFLIGHT_ACKNOWLEDGEMENT,
    PREFLIGHT_VERBS,
    PreflightProcessStatus,
    blocked,
)
from .terminal import SystemTerminal


def main() -> int:
    terminal = SystemTerminal()
    argv = tuple(sys.argv[1:])
    if not _valid_argv(argv):
        return _write(blocked(PreflightProcessStatus.BLOCKED_COMMAND), 2)
    if terminal.tty_state() != (True, True, True):
        return _write(blocked(PreflightProcessStatus.BLOCKED_TTY), 3)
    if terminal.read_acknowledgement() != PREFLIGHT_ACKNOWLEDGEMENT:
        return _write(
            blocked(PreflightProcessStatus.BLOCKED_ACKNOWLEDGEMENT), 4
        )
    terminal.read_hidden_envelope(65_536)
    return _write(
        blocked(PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND), 0
    )


def _valid_argv(argv: object) -> bool:
    return (
        type(argv) is tuple
        and len(argv) == 1
        and type(argv[0]) is str
        and argv[0] in PREFLIGHT_VERBS
    )


def _write(result, exit_code: int) -> int:
    sys.stdout.write(
        f"{result.status.value} "
        f"accepted={result.accepted} "
        f"rejected={result.rejected} "
        f"host_operations={result.host_operations}\n"
    )
    sys.stdout.flush()
    return exit_code
