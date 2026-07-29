"""Closed Python, dependency-lock, and wheelhouse policy."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .canonical import canonical_json, fail, is_fingerprint
from .runtime_archive import review_wheel_archive, safe_wheel_members
from .runtime_source_tree import observe_source_tree

PYTHON_VERSION = "3.12.13"
SQLITE_VERSION = "3.50.4"
DEPENDENCIES = (
    ("beautifulsoup4", "4.15.0", "bs4"),
    ("cryptography", "49.0.0", "cryptography"),
    ("openpyxl", "3.1.5", "openpyxl"),
    ("openai", "2.45.0", "openai"),
    ("python-dotenv", "1.2.2", "dotenv"),
    ("pypdf", "6.14.2", "pypdf"),
    ("python-docx", "1.2.0", "docx"),
    ("Pillow", "12.3.0", "PIL"),
    ("pytesseract", "0.3.13", "pytesseract"),
)
_LOCK_ERROR = "runtime_dependency_lock_invalid"
_SOURCE_ERROR = "runtime_python_source_invalid"
_REPARSE_ATTRIBUTE = 0x400
_DISTRIBUTION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]{0,63}", re.ASCII)
_IMPORT_NAME = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
    re.ASCII,
)


@dataclass(frozen=True, slots=True, repr=False)
class LockedWheelV1:
    distribution: str
    version: str
    wheel: str
    wheel_sha256: str
    import_name: str
    import_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeInputReviewV1:
    python_runtime_fingerprint: str
    wheelhouse_fingerprint: str
    dependency_lock_fingerprint: str
    source_tree_fingerprint: str
    source_entry_count: int
    source_total_bytes: int
    source_executable_sha256: str
    wheels: tuple[LockedWheelV1, ...]


def review_runtime_inputs(
    *,
    source: Path,
    source_manifest: Path,
    wheelhouse: Path,
    dependency_lock: Path,
) -> RuntimeInputReviewV1:
    if source.name != "python.exe":
        fail(_SOURCE_ERROR)
    source_observation = observe_source_tree(source)
    manifest_bytes = _read_regular(source_manifest, 64_000, _SOURCE_ERROR)
    manifest = _strict_json(manifest_bytes, _SOURCE_ERROR)
    expected_manifest = {
        "source_type": "approved-cpython-source/v1",
        "python_version": PYTHON_VERSION,
        "sqlite_version": SQLITE_VERSION,
        "source_tree_fingerprint": source_observation.fingerprint,
        "source_entry_count": source_observation.entry_count,
        "source_total_bytes": source_observation.total_bytes,
        "executable_name": source.name,
        "executable_sha256": source_observation.executable_sha256,
    }
    if manifest != expected_manifest:
        fail(_SOURCE_ERROR)
    lock_bytes = _read_regular(dependency_lock, 256_000, _LOCK_ERROR)
    lock = _strict_json(lock_bytes, _LOCK_ERROR)
    wheels = _locked_wheels(lock)
    wheel_observation = _review_wheelhouse(wheelhouse, wheels)
    return RuntimeInputReviewV1(
        python_runtime_fingerprint=hashlib.sha256(manifest_bytes).hexdigest(),
        wheelhouse_fingerprint=hashlib.sha256(
            canonical_json(wheel_observation, code=_LOCK_ERROR)
        ).hexdigest(),
        dependency_lock_fingerprint=hashlib.sha256(lock_bytes).hexdigest(),
        source_tree_fingerprint=source_observation.fingerprint,
        source_entry_count=source_observation.entry_count,
        source_total_bytes=source_observation.total_bytes,
        source_executable_sha256=expected_manifest["executable_sha256"],
        wheels=wheels,
    )


def _review_wheelhouse(wheelhouse, wheels) -> list[dict[str, str]]:
    expected_names = {wheel.wheel for wheel in wheels}
    observed_names = set()
    observed_count = 0
    try:
        for child in wheelhouse.iterdir():
            observed_count += 1
            if observed_count > len(expected_names):
                fail(_LOCK_ERROR)
            if not _regular_no_reparse(child):
                fail(_LOCK_ERROR)
            observed_names.add(child.name)
    except OSError:
        fail(_LOCK_ERROR)
    if observed_names != expected_names:
        fail(_LOCK_ERROR)
    result = []
    for wheel in wheels:
        payload = _read_regular(
            wheelhouse / wheel.wheel, 100_000_000, _LOCK_ERROR
        )
        digest = hashlib.sha256(payload).hexdigest()
        if digest != wheel.wheel_sha256:
            fail(_LOCK_ERROR)
        result.append({"wheel": wheel.wheel, "wheel_sha256": digest})
    result.sort(key=lambda item: item["wheel"].casefold())
    return result


def _locked_wheels(value: object) -> tuple[LockedWheelV1, ...]:
    if (
        type(value) is not dict
        or set(value) != {"lock_type", "packages"}
        or value["lock_type"] != "managed-runtime-dependency-lock/v1"
        or type(value["packages"]) is not list
        or not len(DEPENDENCIES) <= len(value["packages"]) <= 128
    ):
        fail(_LOCK_ERROR)
    wheels = []
    for item in value["packages"]:
        keys = {
            "distribution",
            "version",
            "wheel",
            "wheel_sha256",
            "import_name",
            "import_sha256",
        }
        if type(item) is not dict or set(item) != keys:
            fail(_LOCK_ERROR)
        if (
            not _valid_distribution(item["distribution"])
            or not _valid_version(item["version"])
            or not _valid_import_name(item["import_name"])
            or not _valid_wheel_name(
                item["wheel"], item["distribution"], item["version"]
            )
            or not is_fingerprint(item["wheel_sha256"])
            or not is_fingerprint(item["import_sha256"])
        ):
            fail(_LOCK_ERROR)
        wheels.append(LockedWheelV1(**item))
    _require_complete_roots(wheels)
    if (
        len({item.distribution.casefold() for item in wheels}) != len(wheels)
        or len({item.wheel.casefold() for item in wheels}) != len(wheels)
        or len({item.import_name.casefold() for item in wheels}) != len(wheels)
    ):
        fail(_LOCK_ERROR)
    return tuple(wheels)


def _require_complete_roots(wheels: list[LockedWheelV1]) -> None:
    by_name = {item.distribution.casefold(): item for item in wheels}
    for distribution, version, import_name in DEPENDENCIES:
        item = by_name.get(distribution.casefold())
        if (
            item is None
            or item.distribution != distribution
            or item.version != version
            or item.import_name != import_name
        ):
            fail(_LOCK_ERROR)


def _valid_distribution(value: object) -> bool:
    return type(value) is str and _DISTRIBUTION.fullmatch(value) is not None


def _valid_version(value: object) -> bool:
    return type(value) is str and _VERSION.fullmatch(value) is not None


def _valid_import_name(value: object) -> bool:
    return type(value) is str and _IMPORT_NAME.fullmatch(value) is not None


def _valid_wheel_name(name: object, distribution: str, version: str) -> bool:
    if (
        type(name) is not str
        or not 1 <= len(name) <= 240
        or not name.isascii()
        or "/" in name
        or "\\" in name
        or not name.casefold().endswith(".whl")
    ):
        return False
    normalized = re.sub(r"[-_.]+", "_", distribution).casefold()
    return (
        name.casefold().startswith(normalized + "-")
        and f"-{version.casefold()}-" in name.casefold()
    )


def _strict_json(payload: bytes, code: str) -> object:
    try:
        value = json.loads(payload.decode("ascii"))
    except (UnicodeError, json.JSONDecodeError):
        fail(code)
    if canonical_json(value, code=code) != payload:
        fail(code)
    return value


def _read_regular(path: Path, limit: int, code: str) -> bytes:
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or path.is_symlink()
            or _is_reparse(metadata)
            or metadata.st_size > limit
        ):
            fail(code)
        payload = _read_bounded_path(path, limit, code)
        current = path.lstat()
    except OSError:
        fail(code)
    if (
        len(payload) != metadata.st_size
        or current.st_dev != metadata.st_dev
        or current.st_ino != metadata.st_ino
        or current.st_size != metadata.st_size
    ):
        fail(code)
    return payload


def _read_bounded_path(path: Path, limit: int, code: str) -> bytes:
    result = bytearray()
    with path.open("rb") as input_file:
        while len(result) <= limit:
            block = input_file.read(min(64 * 1024, limit + 1 - len(result)))
            if not block:
                break
            result.extend(block)
    if len(result) > limit:
        fail(code)
    return bytes(result)


def _regular_no_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and not path.is_symlink()
        and not _is_reparse(metadata)
    )


def _is_reparse(metadata: object) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE
    )
