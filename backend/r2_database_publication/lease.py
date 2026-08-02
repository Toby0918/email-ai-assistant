"""Single-use, handle-bound source database copy lease."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import fingerprint
from .service import require_issued_receipt
from .windows_handle import SourceHandle

_ISSUED_LEASES: list[LegacyDatabaseCopyLeaseV1] = []
_LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True, init=False, repr=False)
class LegacyDatabaseCopyLeaseV1:
    source_identity_fingerprint: str = field(repr=False)
    stopped_receipt_fingerprint: str = field(repr=False)
    lease_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("database lease requires validated construction")


@dataclass(slots=True, repr=False)
class _LeaseState:
    handle: SourceHandle
    source: Path
    source_hash: str
    size: int
    consumed: bool = False
    read_passes: int = 0


_STATES: dict[int, _LeaseState] = {}


def issue_lease(source: Path, stopped: object, expected_hash: str) -> LegacyDatabaseCopyLeaseV1:
    receipt = require_issued_receipt(stopped)
    handle = SourceHandle(source)
    try:
        observed = handle.observe()
        size, source_hash = handle.hash_all(limit=_LIMIT)
        if source_hash != expected_hash:
            raise ValueError("database_source_drift")
        body = {
            "source_identity_fingerprint": observed.identity_fingerprint,
            "stopped_receipt_fingerprint": receipt.receipt_fingerprint,
            "source_hash": source_hash,
            "size": size,
        }
        lease = object.__new__(LegacyDatabaseCopyLeaseV1)
        object.__setattr__(
            lease,
            "source_identity_fingerprint",
            body["source_identity_fingerprint"],
        )
        object.__setattr__(lease, "stopped_receipt_fingerprint", receipt.receipt_fingerprint)
        object.__setattr__(lease, "lease_fingerprint", fingerprint("legacy-database-copy-lease-v1", body))
        _ISSUED_LEASES.append(lease)
        _STATES[id(lease)] = _LeaseState(handle, source, source_hash, size)
        return lease
    except Exception:
        handle.close()
        raise


def copy_once(lease: object, staging: Path, *, partial: bool) -> tuple[int, str]:
    state = _state(lease)
    if state.consumed:
        raise ValueError("database_copy_lease_consumed")
    state.consumed = True
    payload = state.handle.read_all(limit=_LIMIT)
    state.read_passes += 1
    if partial:
        payload = payload[: max(1, len(payload) // 2)]
    _write_create_only(staging, payload)
    if partial:
        raise RuntimeError("database_partial_staging_injected")
    return len(payload), hashlib.sha256(payload).hexdigest()


def verify_again(lease: object) -> tuple[int, str]:
    state = _state(lease)
    if not state.consumed or state.read_passes != 1:
        raise ValueError("database_copy_lease_state_invalid")
    size, digest = state.handle.hash_all(limit=_LIMIT)
    state.read_passes += 1
    return size, digest


def lease_read_passes(lease: object) -> int:
    return _state(lease).read_passes


def close_lease(lease: object) -> None:
    if type(lease) is not LegacyDatabaseCopyLeaseV1:
        return
    state = _STATES.pop(id(lease), None)
    _ISSUED_LEASES[:] = [item for item in _ISSUED_LEASES if item is not lease]
    if state is not None:
        state.handle.close()


def _state(lease: object) -> _LeaseState:
    if (
        type(lease) is not LegacyDatabaseCopyLeaseV1
        or not any(item is lease for item in _ISSUED_LEASES)
    ):
        raise ValueError("database_copy_lease_invalid")
    return _STATES[id(lease)]


def _write_create_only(path: Path, payload: bytes) -> None:
    handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(handle, payload[offset : offset + 64 * 1024])
            if written <= 0:
                raise OSError("database_stage_write_failed")
            offset += written
        os.fsync(handle)
    finally:
        os.close(handle)
