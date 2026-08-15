"""Strict fixed wheelhouse manifest verification for Issue #39."""

from __future__ import annotations

import json
from pathlib import Path


MANIFEST_NAME = "wheelhouse-manifest-v1.json"
MAX_MANIFEST_BYTES = 64 * 1024
MAX_WHEEL_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_MANIFEST_FIELDS = {
    "schema", "python_version", "sqlite_version", "platform",
    "implementation", "abi", "dependency_lock", "dependency_lock_sha256",
    "wheel_count", "total_bytes", "wheels",
}
_WHEEL_FIELDS = {"name", "size_bytes", "sha256"}


class WheelhouseValidationError(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def verify_wheelhouse_manifest(
    *, manifest, wheelhouse, dependency_lock,
    expected_count, hash_regular_file, expected_dependency_lock_sha256=None,
):
    if set(manifest) != _MANIFEST_FIELDS:
        raise WheelhouseValidationError("wheelhouse")
    expected = (
        "issue39-wheelhouse-manifest-v1", "3.12.13", "3.50.4",
        "win_amd64", "cp", "cp312", "requirements-ci-windows.lock",
    )
    observed = tuple(
        manifest[name] for name in (
            "schema", "python_version", "sqlite_version", "platform",
            "implementation", "abi", "dependency_lock",
        )
    )
    if observed != expected or manifest["wheel_count"] != expected_count:
        raise WheelhouseValidationError("wheelhouse")
    try:
        lock_hash = hash_regular_file(dependency_lock, 256 * 1024)
    except Exception:
        raise WheelhouseValidationError("dependency_lock") from None
    if (
        manifest["dependency_lock_sha256"] != lock_hash
        or (
            expected_dependency_lock_sha256 is not None
            and lock_hash != expected_dependency_lock_sha256
        )
    ):
        raise WheelhouseValidationError("dependency_lock")
    return _entries(
        manifest, wheelhouse, expected_count, hash_regular_file
    )


def strict_object(payload: bytes) -> dict[str, object]:
    def pairs(items):
        value = {}
        for key, item in items:
            if type(key) is not str or key in value:
                raise ValueError
            value[key] = item
        return value

    value = json.loads(payload, object_pairs_hook=pairs)
    if type(value) is not dict:
        raise ValueError
    return value


def _entries(manifest, wheelhouse, expected_count, hash_regular_file):
    entries = manifest["wheels"]
    if type(entries) is not list or len(entries) != expected_count:
        raise WheelhouseValidationError("wheelhouse")
    names = []
    total = 0
    for entry in entries:
        if type(entry) is not dict or set(entry) != _WHEEL_FIELDS:
            raise WheelhouseValidationError("wheelhouse")
        name, size, digest = (
            entry["name"], entry["size_bytes"], entry["sha256"],
        )
        if not _safe_wheel_name(name) or name in names:
            raise WheelhouseValidationError("wheelhouse")
        if type(size) is not int or not 1 <= size <= MAX_WHEEL_BYTES:
            raise WheelhouseValidationError("wheelhouse")
        path = wheelhouse / name
        if path.stat().st_size != size or hash_regular_file(path, size) != digest:
            raise WheelhouseValidationError("wheelhouse")
        names.append(name)
        total += size
    actual = sorted(item.name for item in wheelhouse.iterdir())
    expected = sorted([*names, MANIFEST_NAME])
    if actual != expected or total != manifest["total_bytes"] or total > MAX_TOTAL_BYTES:
        raise WheelhouseValidationError("wheelhouse")
    return tuple(names)


def _safe_wheel_name(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 240
        and value.endswith(".whl")
        and value == Path(value).name
        and all(character.isascii() and character.isprintable() for character in value)
    )
