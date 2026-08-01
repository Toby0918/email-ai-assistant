"""Fixed Windows/NTFS/Git process helpers for the R2 verifier."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


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


def run_tty_processes(repo_root: Path, sandbox: Path) -> set[str]:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    cases = (
        ("tests.windows_real_tty_host", "preflight", ()),
        ("tests.windows_evidence_tty_host", "evidence", ()),
        ("tests.windows_transaction_tty_host", "transaction", ("execute",)),
        ("tests.windows_transaction_tty_host", "transaction", ("rollback",)),
    )
    observed = set()
    for index, (module, process_type, extra) in enumerate(cases):
        target = sandbox / f"tty-result-{index}.json"
        completed = subprocess.run(
            (str(pythonw), "-B", "-m", module, str(target), *extra),
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
    return observed


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
