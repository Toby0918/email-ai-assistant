"""Synthetic child that drives the production preflight runner on a TTY."""

from __future__ import annotations

import sys

from backend.r2_preflight_process import PreflightProcessStatus
from backend.r2_preflight_process.terminal import SystemTerminal
from tests.r2_preflight_process_fixture import create_synthetic_process


def main() -> int:
    argv = tuple(sys.argv[1:])
    process = create_synthetic_process()
    result = process.run(argv=argv, terminal=SystemTerminal())
    sys.stdout.write(
        f"{result.status.value} accepted={result.accepted} "
        f"rejected={result.rejected} "
        f"host_operations={result.host_operations}\n"
    )
    sys.stdout.flush()
    expected = (
        result.status is PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND
        and result.counts() == (1, 0, 0)
        and process.reader_acquisitions == 0
    )
    return 0 if expected else 5


if __name__ == "__main__":
    raise SystemExit(main())
