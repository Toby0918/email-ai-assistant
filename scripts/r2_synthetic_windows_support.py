"""Fixed Windows/NTFS/Git process helpers for the R2 verifier."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_composition_contracts.canonical import fingerprint, is_fingerprint


_ZONES = (
    "main",
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)


@dataclass(frozen=True, slots=True)
class TtyProcessProofs:
    process_types: frozenset[str]
    preflight_fingerprint: str
    evidence_fingerprint: str
    execution_fingerprint: str
    fresh_gate_fingerprint: str
    recovery_fingerprint: str


def run_tty_processes(repo_root: Path, sandbox: Path) -> TtyProcessProofs:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    cases = (
        ("preflight", ()),
        ("evidence", ()),
        ("transaction", ("execute",)),
        ("transaction", ("rollback",)),
    )
    observed = set()
    proofs = {}
    for index, (process_type, extra) in enumerate(cases):
        target = sandbox / f"tty-result-{index}.json"
        completed = subprocess.run(
            (
                str(pythonw), "-B", "-m", "tests.windows_synthetic_tty_host",
                str(target), process_type, *extra,
            ),
            cwd=repo_root,
            timeout=20,
            check=False,
        )
        value = json.loads(target.read_text(encoding="utf-8"))
        if (
            completed.returncode != 0
            or value != {"exit_code": 0, "status": "complete"}
        ):
            raise RuntimeError("R2_SYNTHETIC_TTY_PROCESS_FAILED")
        observed.add(process_type)
        proof_name = (
            "execution" if process_type == "transaction" and extra == ("execute",)
            else "recovery" if process_type == "transaction"
            else process_type
        )
        proof = _read_process_proof(sandbox, process_type, extra)
        proofs[proof_name] = fingerprint(
            "r2-executed-tty-process-proof-v1",
            [process_type, list(extra), proof],
        )
        if process_type == "preflight":
            proofs["fresh_gate"] = proof["fresh_gate_receipt_fingerprint"]
    return TtyProcessProofs(
        process_types=frozenset(observed),
        preflight_fingerprint=proofs["preflight"],
        evidence_fingerprint=proofs["evidence"],
        execution_fingerprint=proofs["execution"],
        fresh_gate_fingerprint=proofs["fresh_gate"],
        recovery_fingerprint=proofs["recovery"],
    )


def _read_process_proof(sandbox, process_type, extra):
    suffix = extra[0] if extra else process_type
    path = (
        sandbox / f"tty-transaction-{suffix}.proof.json"
        if process_type == "transaction"
        else sandbox / f"tty-{process_type}.proof.json"
    )
    first = path.read_bytes()
    second = path.read_bytes()
    if first != second or not first.endswith(b"\n"):
        raise RuntimeError("R2_SYNTHETIC_TTY_PROOF_UNSTABLE")
    value = json.loads(first.decode("ascii"))
    if process_type == "preflight":
        valid = (
            set(value) == {
                "proof_type", "status", "topology_receipt_fingerprint",
                "fresh_gate_receipt_fingerprint",
            }
            and value["proof_type"] == "SYNTHETIC_PREFLIGHT_SUCCESS_V1"
            and value["status"] == "PREFLIGHT_COMPLETE"
            and is_fingerprint(value["topology_receipt_fingerprint"])
            and is_fingerprint(value["fresh_gate_receipt_fingerprint"])
            and value["topology_receipt_fingerprint"]
            != value["fresh_gate_receipt_fingerprint"]
        )
    elif process_type == "evidence":
        artifact = sandbox / "published.evidence"
        valid = (
            set(value) == {
                "proof_type", "status", "accepted", "rejected", "published",
                "artifact_fingerprint",
            }
            and value["proof_type"] == "SYNTHETIC_EVIDENCE_SUCCESS_V1"
            and (value["status"], value["accepted"], value["rejected"], value["published"])
            == ("EVIDENCE_PUBLISHED", 1, 0, 1)
            and artifact.read_bytes() == b"SYNTHETIC_R2_EVIDENCE\n"
            and value["artifact_fingerprint"]
            == hashlib.sha256(artifact.read_bytes()).hexdigest()
        )
    else:
        valid = (
            set(value) == {
                "proof_type", "verb", "status", "accepted", "rejected",
                "mutations",
            }
            and value["proof_type"] == "SYNTHETIC_TRANSACTION_SUCCESS_V1"
            and value["verb"] == suffix
            and (value["status"], value["accepted"], value["rejected"], value["mutations"])
            == ("TRANSACTION_ACTION_COMPLETE", 1, 0, 1)
        )
    if not valid:
        raise RuntimeError("R2_SYNTHETIC_TTY_PROOF_INVALID")
    return value


def fixed_git(cwd: Path, *arguments: str) -> None:
    environment = {
        key: os.environ[key]
        for key in (
            "PATH",
            "PATHEXT",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
        )
        if key in os.environ
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    completed = subprocess.run(
        ("git", *arguments),
        cwd=cwd,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("R2_SYNTHETIC_GIT_FAILED")


def require_uniform_acl(container: Path) -> None:
    observed = {_security_hash(container / name) for name in _ZONES}
    if len(observed) != 1 or not next(iter(observed)):
        raise RuntimeError("R2_SYNTHETIC_ACL_SCAN_FAILED")


def is_ntfs(path: Path) -> bool:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    filesystem = ctypes.create_unicode_buffer(32)
    ok = kernel.GetVolumeInformationW(
        str(path.anchor),
        None,
        0,
        None,
        None,
        None,
        filesystem,
        len(filesystem),
    )
    return bool(ok) and filesystem.value.upper() == "NTFS"


def _security_hash(path: Path) -> str:
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    needed = ctypes.c_ulong()
    flags = 0x00000001 | 0x00000002 | 0x00000004
    security.GetFileSecurityW(str(path), flags, None, 0, ctypes.byref(needed))
    if needed.value == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_string_buffer(needed.value)
    if not security.GetFileSecurityW(
        str(path), flags, buffer, needed.value, ctypes.byref(needed)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return hashlib.sha256(buffer.raw[: needed.value]).hexdigest()
