"""Detached host for one signed transaction TTY child."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from backend.r2_transaction_process import TRANSACTION_ACKNOWLEDGEMENT
from tests.r2_transaction_process_fixture import valid_hidden_envelope
from tests.windows_real_tty_host import _inject_console_input


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        return 2
    target = Path(sys.argv[1])
    verb = sys.argv[2] if len(sys.argv) == 3 else "execute"
    if verb not in {"execute", "rollback"}:
        return 2
    if target.exists() or not target.parent.is_dir():
        return 3
    try:
        result = _run_operator(verb, target.parent)
    except Exception:
        result = {"status": "rejected", "exit_code": -1}
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


def _run_operator(verb="execute", workdir=None) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    workdir = Path(workdir) if workdir is not None else root
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root)
    python = Path(sys.executable).with_name("python.exe")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    process = subprocess.Popen(
        (
            str(python),
            "-B",
            "-m",
            "tests.r2_transaction_process_worker",
            verb,
        ),
        cwd=workdir,
        env=environment,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=startup,
        close_fds=True,
    )
    try:
        _inject_console_input(
            process.pid,
            TRANSACTION_ACKNOWLEDGEMENT
            + "\r"
            + valid_hidden_envelope(verb)
            + "\r",
        )
        exit_code = process.wait(timeout=10)
    except Exception:
        process.kill()
        process.wait(timeout=5)
        raise
    return {"status": "complete", "exit_code": exit_code}


if __name__ == "__main__":
    raise SystemExit(main())
