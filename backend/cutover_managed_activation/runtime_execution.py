"""Network-disabled Runtime execution and captured-wheel extraction."""

from __future__ import annotations

import os
import subprocess
import threading
import time
import zipfile
from io import BytesIO
from pathlib import Path

from .canonical import fail
from .runtime_archive import preflight_wheel_payload, review_wheel_archive

_ERROR = "runtime_publication_failed"
_MAX_PROCESS_OUTPUT = 256_000


def install_locked_wheels(captured, tree) -> None:
    for item in captured:
        _install_one_wheel(item.payload, tree)


def _install_one_wheel(payload: bytes, tree) -> None:
    try:
        preflight_wheel_payload(payload)
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            for info in review_wheel_archive(archive):
                _extract_create_only(archive, info, tree)
    except (OSError, zipfile.BadZipFile, KeyError):
        fail("runtime_wheel_invalid")


def _extract_create_only(archive, info, tree) -> None:
    parts = ("Lib", "site-packages", *Path(info.filename).parts)
    if info.is_dir():
        tree.ensure_directory(parts)
        return
    try:
        with archive.open(info, "r") as source:
            tree.create_streamed_file(parts, source, info.file_size)
    except (OSError, RuntimeError, zipfile.BadZipFile):
        fail("runtime_wheel_invalid")


def publish_lock(payload: bytes, tree) -> None:
    tree.create_file(("dependency-lock.json",), payload)


def run_offline(
    command: list[str],
    *,
    root: Path,
    timeout: int,
    output_limit: int = _MAX_PROCESS_OUTPUT,
):
    if (
        type(output_limit) is not int
        or not 0 <= output_limit <= _MAX_PROCESS_OUTPUT
    ):
        fail(_ERROR)
    environment = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "COMSPEC")
        if key in os.environ
    }
    environment.update(
        {
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_CONFIG_FILE": os.devnull,
            "PYTHONNOUSERSITE": "1",
        }
    )
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    except OSError:
        fail(_ERROR)
    return _collect_bounded(process, command, timeout, output_limit)


def _collect_bounded(process, command, timeout, output_limit):
    output = bytearray()
    exceeded = threading.Event()
    reader = threading.Thread(
        target=_read_bounded_output,
        args=(process.stdout, output, output_limit, exceeded),
        daemon=True,
    )
    reader.start()
    deadline = time.monotonic() + timeout
    forced_failure = False
    while process.poll() is None:
        if exceeded.is_set() or time.monotonic() >= deadline:
            forced_failure = True
            process.kill()
            break
        time.sleep(0.01)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        forced_failure = True
    reader.join(timeout=2)
    if reader.is_alive():
        forced_failure = True
    return subprocess.CompletedProcess(
        command,
        -1 if forced_failure or exceeded.is_set() else process.returncode,
        bytes(output),
    )


def _read_bounded_output(stream, output, limit, exceeded) -> None:
    try:
        while len(output) <= limit:
            remaining = limit + 1 - len(output)
            block = stream.read1(min(64 * 1024, remaining))
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
