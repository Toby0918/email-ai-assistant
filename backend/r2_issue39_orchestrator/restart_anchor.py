"""Transfer the operator process to the fixed external restart anchor."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from .production_evidence import (
    Issue39EvidencePackageV1,
    fixed_issue39_evidence_location_v1,
    verify_fixed_issue39_evidence_v1,
)
from .durable_io import guard_directory


_PYTHON = Path(
    r"D:\Projects\email_ai_assistant-runtime\python-3.12.13-sqlite-3.50.4\python.exe"
)
_RUNNER = "issue39-cutover-runner-v1.pyz"


def ensure_fixed_issue39_restart_anchor_v1(package):
    if type(package) is not Issue39EvidencePackageV1:
        raise TypeError("R2_ISSUE39_RESTART_ANCHOR_INVALID")
    runner = fixed_issue39_evidence_location_v1(package) / _RUNNER
    if Path(sys.argv[0]).resolve(strict=True) == runner.resolve(strict=True):
        return True
    if not _PYTHON.is_file() or not runner.is_file():
        raise TypeError("R2_ISSUE39_RESTART_ANCHOR_INVALID")
    verify_fixed_issue39_evidence_v1(package)
    from backend.cutover_managed_activation.windows_file_handles import (
        WindowsReadHandleApi,
    )

    api = WindowsReadHandleApi()
    handle = api.open_existing(runner, deny_write=True)
    try:
        identity = api.observe(handle)
        size, digest = api.hash_bounded(handle, limit=len(package.restart_anchor))
        if size != len(package.restart_anchor) or digest != hashlib.sha256(
            package.restart_anchor
        ).hexdigest():
            raise TypeError("R2_ISSUE39_RESTART_ANCHOR_INVALID")
        with guard_directory(runner.parent, flush=False):
            api.require_stable(handle, identity, runner)
            verify_fixed_issue39_evidence_v1(package)
            api.require_stable(handle, identity, runner)
            os.chdir(runner.parent)
            os.execv(
                str(_PYTHON),
                (str(_PYTHON), "-I", "-B", str(runner), "run"),
            )
    finally:
        api.close(handle)
    raise AssertionError("unreachable")
