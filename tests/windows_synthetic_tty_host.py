"""Detached worker host proving synthetic markers cannot unlock any root."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from backend.real_host_preflight import PreMutationGate
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import OBSERVED_AT, sandbox_authorization
from tests.test_real_host_preflight_windows_composition import (
    _SandboxLayout,
    _run_preflight,
)


_WORKERS = {
    "preflight": (
        "tests.r2_preflight_process_worker",
        "current-topology",
        frozenset({"current-topology"}),
        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 read_operations=0\n",
    ),
    "evidence": (
        "tests.r2_evidence_process_worker",
        "publish",
        frozenset({"publish"}),
        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 published=0\n",
    ),
    "transaction": (
        "tests.r2_transaction_process_worker",
        "execute",
        frozenset({"execute", "rollback"}),
        "DORMANT_NO_ISSUE39_APPROVAL accepted=0 rejected=0 mutations=0\n",
    ),
}


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        return 2
    target = Path(sys.argv[1])
    process_type = sys.argv[2]
    default = _WORKERS.get(process_type)
    if target.exists() or not target.parent.is_dir() or default is None:
        return 3
    module, default_verb, allowed_verbs, expected_stdout = default
    verb = sys.argv[3] if len(sys.argv) == 4 else default_verb
    if verb not in allowed_verbs:
        return 3
    result = _run_worker(module, verb, target.parent, expected_stdout)
    if result == {"exit_code": 0, "status": "complete"}:
        _write_sandbox_proof(target.parent, process_type, verb)
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


def _run_worker(module, verb, workdir, expected_stdout):
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.update({"PYTHONPATH": str(root), "R2_SYNTHETIC_UNLOCK": "1"})
    completed = subprocess.run(
        (sys.executable, "-B", "-m", module, verb),
        cwd=workdir,
        env=environment,
        input="synthetic-unlock-attempt\n",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if (
        completed.returncode == 0
        and completed.stdout == expected_stdout
        and completed.stderr == ""
    ):
        return {"exit_code": 0, "status": "complete"}
    return {"exit_code": completed.returncode, "status": "rejected"}


def _write_sandbox_proof(workdir, process_type, verb):
    if process_type == "preflight":
        _write_preflight_proof(workdir)
    elif process_type == "evidence":
        artifact = workdir / "published.evidence"
        _write_bytes_create_only(artifact, b"SYNTHETIC_R2_EVIDENCE\n")
        _write_json_create_only(
            workdir / "tty-evidence.proof.json",
            {
                "proof_type": "SYNTHETIC_EVIDENCE_SUCCESS_V1",
                "status": "EVIDENCE_PUBLISHED",
                "accepted": 1,
                "rejected": 0,
                "published": 1,
                "artifact_fingerprint": hashlib.sha256(
                    artifact.read_bytes()
                ).hexdigest(),
            },
        )
    else:
        _write_bytes_create_only(
            workdir / f"synthetic-transaction-{verb}.marker",
            f"{verb}\n".encode("ascii"),
        )
        _write_json_create_only(
            workdir / f"tty-transaction-{verb}.proof.json",
            {
                "proof_type": "SYNTHETIC_TRANSACTION_SUCCESS_V1",
                "verb": verb,
                "status": "TRANSACTION_ACTION_COMPLETE",
                "accepted": 1,
                "rejected": 0,
                "mutations": 1,
            },
        )


def _write_preflight_proof(workdir):
    scope = workdir / "tty-preflight-scope"
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
    _write_json_create_only(
        workdir / "tty-preflight.proof.json",
        {
            "proof_type": "SYNTHETIC_PREFLIGHT_SUCCESS_V1",
            "status": "PREFLIGHT_COMPLETE",
            "topology_receipt_fingerprint": receipt.receipt_fingerprint,
            "fresh_gate_receipt_fingerprint": gate_receipt.receipt_fingerprint,
        },
    )


def _write_bytes_create_only(path, payload):
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _write_json_create_only(path, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    _write_bytes_create_only(path, (payload + "\n").encode("ascii"))


if __name__ == "__main__":
    raise SystemExit(main())
