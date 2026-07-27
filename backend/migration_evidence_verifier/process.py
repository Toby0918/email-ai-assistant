"""Bounded parent-side launcher for the fixed verifier worker."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from .canonical import (
    VerifierProcessError,
    canonical_json,
    canonical_sha256,
    decode_canonical_object,
    is_sha256,
)
from .contracts import (
    PackageVerificationObservationV1,
    PackageVerificationStatus,
)
from .process_tree import ProcessTree


_MAX_RESPONSE_BYTES = 4096
_TIMEOUT_SECONDS = 30
_ZERO_SHA256 = "0" * 64
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def verify_package_in_separate_process(
    *,
    package: Path,
) -> PackageVerificationObservationV1:
    """Verify a published package in one fixed read-only worker."""

    try:
        return _run_worker(package)
    except Exception:
        return _rejected_observation()


def _run_worker(package: Path) -> PackageVerificationObservationV1:
    if not isinstance(package, Path) or not package.is_absolute():
        raise VerifierProcessError
    request = canonical_json(
        {
            "schema_version": "PackageVerificationRequestV1",
            "package": str(package),
        }
    ) + b"\n"
    process = None
    timer = None
    timed_out = threading.Event()
    process_tree = ProcessTree.prepare()
    try:
        process = _launch_worker(process_tree)
        if process.pid == os.getpid():
            raise VerifierProcessError
        process_tree.attach(process)
        timer = threading.Timer(
            _TIMEOUT_SECONDS,
            _expire_process,
            args=(process_tree, process, timed_out),
        )
        timer.daemon = True
        timer.start()
        _send_request(process, request)
        payload = _read_response(process)
        returncode = process_tree.finish(process)
        if timed_out.is_set() or returncode != 0:
            raise VerifierProcessError
        return _parse_observation(
            payload,
            _process_fingerprint(os.getpid()),
        )
    finally:
        if timer is not None:
            timer.cancel()
        process_tree.terminate(process)
        _close_pipes(process)


def _launch_worker(process_tree: ProcessTree) -> subprocess.Popen:
    return subprocess.Popen(
        (
            sys.executable,
            "-B",
            "-m",
            "backend.migration_evidence_verifier.worker",
        ),
        cwd=_REPOSITORY_ROOT,
        env=_worker_environment(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        shell=False,
        **process_tree.popen_options(),
    )


def _send_request(
    process: subprocess.Popen,
    request: bytes,
) -> None:
    if process.stdin is None:
        raise VerifierProcessError
    process.stdin.write(request)
    process.stdin.flush()
    process.stdin.close()


def _read_response(process: subprocess.Popen) -> bytes:
    if process.stdout is None:
        raise VerifierProcessError
    payload = process.stdout.read(_MAX_RESPONSE_BYTES + 1)
    if (
        len(payload) > _MAX_RESPONSE_BYTES
        or not payload.endswith(b"\n")
        or b"\n" in payload[:-1]
    ):
        raise VerifierProcessError
    return payload[:-1]


def _parse_observation(
    payload: bytes,
    caller_process: str,
) -> PackageVerificationObservationV1:
    value = decode_canonical_object(payload)
    _require_observation_shape(value, caller_process)
    status = _parse_status(value["status"])
    hashes = _observation_hashes(value)
    counts = _observation_counts(value)
    if not all(is_sha256(item) for item in hashes):
        raise VerifierProcessError
    if not _valid_counts(counts):
        raise VerifierProcessError
    if status is PackageVerificationStatus.REJECTED:
        if hashes[:5] != (_ZERO_SHA256,) * 5 or counts != (0, 0, 0):
            raise VerifierProcessError
    elif _ZERO_SHA256 in hashes or 0 in counts:
        raise VerifierProcessError
    return _build_observation(value, status)


def _require_observation_shape(
    value: dict[str, object],
    caller_process: str,
) -> None:
    expected_keys = {
        "schema_version",
        "status",
        "review_fingerprint",
        "package_sha256",
        "manifest_sha256",
        "package_identity_fingerprint",
        "files",
        "refs",
        "worktrees",
        "counts_fingerprint",
        "process_fingerprint",
    }
    if (
        set(value) != expected_keys
        or value["schema_version"] != "PackageVerificationObservationV1"
        or value["process_fingerprint"] == caller_process
    ):
        raise VerifierProcessError


def _observation_hashes(
    value: dict[str, object],
) -> tuple[object, ...]:
    return (
        value["review_fingerprint"],
        value["package_sha256"],
        value["manifest_sha256"],
        value["package_identity_fingerprint"],
        value["counts_fingerprint"],
        value["process_fingerprint"],
    )


def _observation_counts(
    value: dict[str, object],
) -> tuple[object, ...]:
    return (
        value["files"],
        value["refs"],
        value["worktrees"],
    )


def _build_observation(
    value: dict[str, object],
    status: PackageVerificationStatus,
) -> PackageVerificationObservationV1:
    return PackageVerificationObservationV1(
        status=status,
        review_fingerprint=value["review_fingerprint"],
        package_sha256=value["package_sha256"],
        manifest_sha256=value["manifest_sha256"],
        package_identity_fingerprint=value["package_identity_fingerprint"],
        files=value["files"],
        refs=value["refs"],
        worktrees=value["worktrees"],
        counts_fingerprint=value["counts_fingerprint"],
        process_fingerprint=value["process_fingerprint"],
    )


def _parse_status(value: object) -> PackageVerificationStatus:
    try:
        return PackageVerificationStatus(value)
    except (TypeError, ValueError):
        raise VerifierProcessError from None


def _valid_counts(values: tuple[object, ...]) -> bool:
    return all(
        type(value) is int and 0 <= value <= maximum
        for value, maximum in zip(values, (599, 128, 64), strict=True)
    )


def _process_fingerprint(process_id: int) -> str:
    return canonical_sha256(
        {
            "schema": "MigrationEvidenceVerifierProcessV1",
            "process_id": process_id,
        }
    )


def _worker_environment() -> dict[str, str]:
    allowed = {
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SystemRoot",
        "TEMP",
        "TMP",
        "TMPDIR",
        "WINDIR",
    }
    environment = {
        name: value
        for name, value in os.environ.items()
        if name in allowed
    }
    environment.update(
        {
            "LANG": "C",
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    return environment


def _expire_process(
    process_tree: ProcessTree,
    process: subprocess.Popen,
    timed_out: threading.Event,
) -> None:
    timed_out.set()
    try:
        process_tree.terminate(process)
    except Exception:
        pass


def _close_pipes(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    for stream in (process.stdin, process.stdout):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass


def _rejected_observation() -> PackageVerificationObservationV1:
    return PackageVerificationObservationV1(
        status=PackageVerificationStatus.REJECTED,
        review_fingerprint=_ZERO_SHA256,
        package_sha256=_ZERO_SHA256,
        manifest_sha256=_ZERO_SHA256,
        package_identity_fingerprint=_ZERO_SHA256,
        files=0,
        refs=0,
        worktrees=0,
        counts_fingerprint=_ZERO_SHA256,
        process_fingerprint=_ZERO_SHA256,
    )
