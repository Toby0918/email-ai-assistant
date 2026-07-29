"""Held source and immutable wheel-byte capture for Runtime publication."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass, field
from io import BytesIO

from .canonical import fail
from .errors import ManagedActivationError
from .runtime_archive import (
    MAX_CAPTURED_WHEEL_BYTES,
    MAX_WHEEL_PAYLOAD_BYTES,
    preflight_wheel_payload,
    review_wheel_archive,
)
from .runtime_policy import LockedWheelV1
from .runtime_source_tree import (
    HeldPythonSourceTree,
    SourceTreeObservation,
)
from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)

_MAX_LOCK_BYTES = 256_000


@dataclass(frozen=True, slots=True, repr=False)
class CapturedWheel:
    review: LockedWheelV1 = field(repr=False)
    payload: bytes = field(repr=False)


def open_python_source(path, review) -> HeldPythonSourceTree:
    try:
        expected = SourceTreeObservation(
            fingerprint=review.source_tree_fingerprint,
            entry_count=review.source_entry_count,
            total_bytes=review.source_total_bytes,
            executable_sha256=review.source_executable_sha256,
        )
        return HeldPythonSourceTree.open(path, expected)
    except Exception:
        fail("runtime_python_source_invalid")


def capture_locked_wheels(scenario, review) -> tuple[CapturedWheel, ...]:
    api = WindowsReadHandleApi()
    result = []
    total = 0
    for wheel in review.wheels:
        path = scenario.wheelhouse / wheel.wheel
        remaining = MAX_CAPTURED_WHEEL_BYTES - total
        if remaining <= 0:
            fail("runtime_wheel_invalid")
        payload = _capture_file_bytes(
            api,
            path,
            wheel.wheel_sha256,
            min(MAX_WHEEL_PAYLOAD_BYTES, remaining),
        )
        _validate_captured_wheel(payload)
        total += len(payload)
        result.append(CapturedWheel(review=wheel, payload=payload))
    return tuple(result)


def capture_lock(scenario, review) -> bytes:
    return _capture_file_bytes(
        WindowsReadHandleApi(),
        scenario.dependency_lock,
        review.dependency_lock_fingerprint,
        _MAX_LOCK_BYTES,
    )


def _validate_captured_wheel(payload: bytes) -> None:
    try:
        preflight_wheel_payload(payload)
        with zipfile.ZipFile(BytesIO(payload), "r") as archive:
            review_wheel_archive(archive)
    except ManagedActivationError:
        fail("runtime_wheel_invalid")
    except (OSError, zipfile.BadZipFile, KeyError):
        fail("runtime_wheel_invalid")


def _capture_file_bytes(api, path, expected_hash, limit) -> bytes:
    handle = None
    try:
        handle = api.open_existing(path, deny_write=True)
        observed = api.observe(handle)
        _validate_captured_file(observed)
        payload = api.read_bounded(handle, limit=limit)
        if (
            len(payload) > limit
            or hashlib.sha256(payload).hexdigest() != expected_hash
        ):
            fail("runtime_source_changed")
        api.require_stable(handle, observed, path)
        return payload
    except ManagedActivationError:
        fail("runtime_source_changed")
    except Exception:
        fail("runtime_source_changed")
    finally:
        if handle is not None:
            api.close(handle)


def _validate_captured_file(observed) -> None:
    if (
        observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or not observed.fixed_drive
    ):
        fail("runtime_source_changed")
