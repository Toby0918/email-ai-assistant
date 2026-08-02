"""Fresh-console child for one signed synthetic execute action."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from backend.r2_transaction_process import TransactionProcessStatus
from backend.r2_transaction_process.terminal import SystemTerminal
from tests.r2_transaction_process_fixture import create_synthetic_process


def main() -> int:
    calls = 0
    verb = sys.argv[1] if len(sys.argv) == 2 else ""

    def action() -> int:
        nonlocal calls
        calls += 1
        return 1

    process = create_synthetic_process(action, verb=verb)
    result = process.run(
        argv=tuple(sys.argv[1:]), terminal=SystemTerminal()
    )
    sys.stdout.write(
        f"{result.status.value} accepted={result.accepted} "
        f"rejected={result.rejected} mutations={result.mutations}\n"
    )
    sys.stdout.flush()
    valid = (
        result.status is TransactionProcessStatus.ACTION_COMPLETE
        and result.counts() == (1, 0, 1)
        and calls == 1
        and process.action_acquisitions == 1
    )
    if valid and (Path.cwd() / ".r2-full-topology-sandbox").is_file():
        _write_proof(
            Path.cwd() / f"tty-transaction-{verb}.proof.json",
            {
                "proof_type": "SYNTHETIC_TRANSACTION_SUCCESS_V1",
                "verb": verb,
                **result.to_mapping(),
            },
        )
    return 0 if valid else 5


def _write_proof(path, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    with path.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(payload + "\n")
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == "__main__":
    raise SystemExit(main())
