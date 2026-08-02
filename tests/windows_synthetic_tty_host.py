"""Detached real-console host for fixed synthetic R2 success workers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from backend.r2_evidence_process import EVIDENCE_ACKNOWLEDGEMENT
from backend.r2_preflight_process import PREFLIGHT_ACKNOWLEDGEMENT
from backend.r2_transaction_process import TRANSACTION_ACKNOWLEDGEMENT
from tests.r2_evidence_process_fixture import valid_hidden_envelope as evidence_envelope
from tests.r2_preflight_process_fixture import valid_hidden_envelope as preflight_envelope
from tests.r2_transaction_process_fixture import valid_hidden_envelope as transaction_envelope
from tests.windows_real_tty_host import _inject_console_input


_WORKERS = {
    "preflight": ("tests.r2_preflight_process_worker", "current-topology"),
    "evidence": ("tests.r2_evidence_process_worker", "publish"),
}


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        return 2
    target = Path(sys.argv[1])
    process_type = sys.argv[2]
    verb = sys.argv[3] if len(sys.argv) == 4 else ""
    if target.exists() or not target.parent.is_dir():
        return 3
    try:
        result = _run_worker(process_type, verb, target.parent)
    except Exception:
        result = {"status": "rejected", "exit_code": -1}
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


def _run_worker(process_type, verb, workdir):
    if process_type == "transaction":
        if verb not in {"execute", "rollback"}:
            raise ValueError
        module, arguments = "tests.r2_transaction_process_worker", (verb,)
        acknowledgement = TRANSACTION_ACKNOWLEDGEMENT
        envelope = transaction_envelope(verb)
    else:
        if verb or process_type not in _WORKERS:
            raise ValueError
        module, argument = _WORKERS[process_type]
        arguments = (argument,)
        acknowledgement, envelope = _ingress(process_type)
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    process = subprocess.Popen(
        (str(Path(sys.executable).with_name("python.exe")), "-B", "-m", module, *arguments),
        cwd=workdir,
        env=environment,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=startup,
        close_fds=True,
    )
    try:
        _inject_console_input(
            process.pid, acknowledgement + "\r" + envelope + "\r"
        )
        exit_code = process.wait(timeout=15)
    except Exception:
        process.kill()
        process.wait(timeout=5)
        raise
    return {"status": "complete", "exit_code": exit_code}


def _ingress(process_type):
    if process_type == "preflight":
        return PREFLIGHT_ACKNOWLEDGEMENT, preflight_envelope()
    return EVIDENCE_ACKNOWLEDGEMENT, evidence_envelope()


if __name__ == "__main__":
    raise SystemExit(main())
