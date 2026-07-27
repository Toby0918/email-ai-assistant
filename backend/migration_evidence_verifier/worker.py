"""Fixed stdin/stdout worker for read-only package verification."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .bridge import verify_existing_payload
from .canonical import (
    VerifierProcessError,
    canonical_json,
    canonical_sha256,
    decode_canonical_object,
)
from .package_read import (
    package_observation,
    read_package_once,
    require_same_package,
)


_MAX_REQUEST_BYTES = 64 * 1024
_ZERO_SHA256 = "0" * 64


def main() -> int:
    process_fingerprint = _process_fingerprint(os.getpid())
    try:
        request = _read_request()
        response = _verify(request, process_fingerprint)
    except BaseException:
        response = _rejected_response(process_fingerprint)
    sys.stdout.buffer.write(canonical_json(response) + b"\n")
    sys.stdout.buffer.flush()
    return 0


def _verify(
    request: dict[str, object],
    process_fingerprint: str,
) -> dict[str, object]:
    if set(request) != {"schema_version", "package"}:
        raise VerifierProcessError
    if request["schema_version"] != "PackageVerificationRequestV1":
        raise VerifierProcessError
    raw_package = request["package"]
    if type(raw_package) is not str or not 1 <= len(raw_package) <= 32768:
        raise VerifierProcessError
    package = Path(raw_package)
    before = read_package_once(package)
    result = verify_existing_payload(payload=before.payload)
    after = read_package_once(package)
    require_same_package(before, after)
    observation = package_observation(after)
    _require_verified_result(result, observation)
    return {
        "schema_version": "PackageVerificationObservationV1",
        "status": "migration_evidence_package_verified",
        **observation,
        "process_fingerprint": process_fingerprint,
    }


def _require_verified_result(
    result,
    observation: dict[str, object],
) -> None:
    status = getattr(getattr(result, "status", None), "value", None)
    counts = getattr(result, "counts", None)
    if (
        status != "migration_evidence_verified"
        or counts is None
        or counts.files != observation["files"]
        or counts.refs != observation["refs"]
        or counts.worktrees != observation["worktrees"]
        or counts.packages != 1
        or counts.verified != 1
        or counts.rejected != 0
    ):
        raise VerifierProcessError


def _read_request() -> dict[str, object]:
    payload = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
    if (
        len(payload) > _MAX_REQUEST_BYTES
        or not payload.endswith(b"\n")
        or b"\n" in payload[:-1]
    ):
        raise VerifierProcessError
    return decode_canonical_object(payload[:-1])


def _rejected_response(
    process_fingerprint: str,
) -> dict[str, object]:
    return {
        "schema_version": "PackageVerificationObservationV1",
        "status": "migration_evidence_package_rejected",
        "review_fingerprint": _ZERO_SHA256,
        "package_sha256": _ZERO_SHA256,
        "manifest_sha256": _ZERO_SHA256,
        "package_identity_fingerprint": _ZERO_SHA256,
        "files": 0,
        "refs": 0,
        "worktrees": 0,
        "counts_fingerprint": _ZERO_SHA256,
        "process_fingerprint": process_fingerprint,
    }


def _process_fingerprint(process_id: int) -> str:
    return canonical_sha256(
        {
            "schema": "MigrationEvidenceVerifierProcessV1",
            "process_id": process_id,
        }
    )


if __name__ == "__main__":
    raise SystemExit(main())
