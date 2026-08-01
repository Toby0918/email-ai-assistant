"""Production transaction entry remains locked before Issue #39."""

from __future__ import annotations

import sys

from .contracts import (
    TRANSACTION_ACKNOWLEDGEMENT,
    TRANSACTION_VERBS,
    TransactionProcessStatus,
    result,
)
from .terminal import SystemTerminal


def main() -> int:
    terminal = SystemTerminal()
    argv = tuple(sys.argv[1:])
    if len(argv) != 1 or argv[0] not in TRANSACTION_VERBS:
        return _write(result(TransactionProcessStatus.BLOCKED_COMMAND), 2)
    if terminal.tty_state() != (True, True, True):
        return _write(result(TransactionProcessStatus.BLOCKED_TTY), 3)
    if terminal.read_acknowledgement() != TRANSACTION_ACKNOWLEDGEMENT:
        return _write(
            result(TransactionProcessStatus.BLOCKED_ACKNOWLEDGEMENT), 4
        )
    terminal.read_hidden_envelope(65_536)
    return _write(
        result(TransactionProcessStatus.BLOCKED_NO_APPROVED_COMMAND), 0
    )


def _write(value, exit_code: int) -> int:
    sys.stdout.write(
        f"{value.status.value} accepted={value.accepted} "
        f"rejected={value.rejected} mutations={value.mutations}\n"
    )
    sys.stdout.flush()
    return exit_code
