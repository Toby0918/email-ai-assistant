"""Synthetic child that drives the production preflight runner on a TTY."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from backend.real_host_preflight import PreMutationGate
from backend.r2_preflight_process import PreflightProcessStatus
from backend.r2_preflight_process.terminal import SystemTerminal
from tests.r2_preflight_process_fixture import create_synthetic_process
from tests.test_real_host_preflight_windows_composition import (
    _SandboxLayout,
    _run_preflight,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import OBSERVED_AT, sandbox_authorization


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
    if expected and (Path.cwd() / ".r2-full-topology-sandbox").is_file():
        scope = Path.cwd() / "tty-preflight-scope"
        scope.mkdir()
        layout = _SandboxLayout.create(scope)
        receipt = _run_preflight(layout.callbacks(), layout.profile)
        operation = opaque_fingerprint(201)
        gate = PreMutationGate.bind(
            current_topology_receipt=receipt,
            callbacks=layout.callbacks(),
            policy_fingerprint=opaque_fingerprint(407),
        )
        gate_receipt = gate.evaluate(
            profile=layout.profile,
            authorization=sandbox_authorization(
                layout.profile, operation_fingerprint=operation
            ),
            operation_fingerprint=operation,
            nonce="123e4567-e89b-42d3-a456-426614174000",
            observed_at_epoch=OBSERVED_AT + 1,
        )
        _write_proof(
            Path.cwd() / "tty-preflight.proof.json",
            {
                "proof_type": "SYNTHETIC_PREFLIGHT_SUCCESS_V1",
                "status": "PREFLIGHT_COMPLETE",
                "topology_receipt_fingerprint": receipt.receipt_fingerprint,
                "fresh_gate_receipt_fingerprint": gate_receipt.receipt_fingerprint,
            },
        )
    return 0 if expected else 5


def _write_proof(path, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    with path.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(payload + "\n")
        stream.flush()
        os.fsync(stream.fileno())


if __name__ == "__main__":
    raise SystemExit(main())
