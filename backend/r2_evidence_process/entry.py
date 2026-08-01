"""Production evidence executable stays unavailable before Issue #39."""

from __future__ import annotations

import sys

from .contracts import (
    EVIDENCE_ACKNOWLEDGEMENT,
    EvidenceProcessStatus,
    result,
)
from .terminal import SystemTerminal


def main() -> int:
    terminal = SystemTerminal()
    if tuple(sys.argv[1:]) != ("publish",):
        return _write(result(EvidenceProcessStatus.BLOCKED_COMMAND), 2)
    if terminal.tty_state() != (True, True, True):
        return _write(result(EvidenceProcessStatus.BLOCKED_TTY), 3)
    if terminal.read_acknowledgement() != EVIDENCE_ACKNOWLEDGEMENT:
        return _write(
            result(EvidenceProcessStatus.BLOCKED_ACKNOWLEDGEMENT), 4
        )
    terminal.read_hidden_envelope(65_536)
    return _write(
        result(EvidenceProcessStatus.BLOCKED_NO_APPROVED_COMMAND), 0
    )


def _write(value, exit_code: int) -> int:
    sys.stdout.write(
        f"{value.status.value} accepted={value.accepted} "
        f"rejected={value.rejected} published={value.published}\n"
    )
    sys.stdout.flush()
    return exit_code
