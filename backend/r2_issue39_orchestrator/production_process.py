"""Bounded-output foreground process execution for fixed production tools."""

from __future__ import annotations

import subprocess
import threading
import time


def run_bounded(command, *, cwd, env, timeout, output_limit):
    if not 0 <= output_limit <= 4 * 1024 * 1024:
        raise ValueError("R2_ISSUE39_PROCESS_LIMIT_INVALID")
    process = subprocess.Popen(
        command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        shell=False,
    )
    output = bytearray()
    exceeded = threading.Event()
    reader = threading.Thread(
        target=_read, args=(process.stdout, output, output_limit, exceeded),
        daemon=True,
    )
    reader.start()
    deadline = time.monotonic() + timeout
    forced = False
    while process.poll() is None:
        if exceeded.is_set() or time.monotonic() >= deadline:
            process.kill()
            forced = True
            break
        time.sleep(0.01)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        forced = True
    reader.join(timeout=2)
    if reader.is_alive():
        forced = True
    return subprocess.CompletedProcess(
        command, -1 if forced or exceeded.is_set() else process.returncode,
        bytes(output),
    )


def _read(stream, output, limit, exceeded):
    try:
        while len(output) <= limit:
            block = stream.read1(min(64 * 1024, limit + 1 - len(output)))
            if not block:
                return
            output.extend(block)
            if len(output) > limit:
                exceeded.set()
                return
    except (OSError, ValueError):
        exceeded.set()
    finally:
        stream.close()
