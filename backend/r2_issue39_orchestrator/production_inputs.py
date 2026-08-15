"""Fixed read-only production inputs for the Issue #39 cutover."""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .production_manifest import (
    MANIFEST_NAME,
    MAX_MANIFEST_BYTES,
    WheelhouseValidationError,
    strict_object,
    verify_wheelhouse_manifest,
)
from .input_identity import file_identity_fingerprint as _file_identity_fingerprint


_WHEELHOUSE = Path(
    r"D:\Projects\email_ai_assistant-runtime\issue39-wheelhouse"
)
_RUNTIME = Path(
    "D:\\Projects\\email_ai_assistant-runtime\\"
    "python-3.12.13-sqlite-3.50.4\\python.exe"
)
_HISTORICAL_DATABASE = Path(
    r"D:\Projects\email-ai-assistant\-local-data\email_agent.sqlite3"
)
_CRX_SOURCE = Path(r"D:\Projects\email_ai_assistant\frontend\browser_extension.crx")
_MANIFEST_SHA256 = (
    "5709429425f9eab1028157cd81df8638944d686c15b8db7db5bba6f0df9eddc2"
)
_DEPENDENCY_LOCK_SHA256 = (
    "531f8054b8d8d908fe73f6a74ba42bd9b5dfe931b002b81647572c06bf08f8c0"
)
_RUNTIME_SHA256 = "f598fb950a86a895d8f9b4755fc9b38c48adc7a15732a342e55c17a3c3499602"
_CRX_SHA256 = "c369425dfbc86bc5faa5d1b4719e77349f77f9ae3daec81a4d451b8565081dd6"
_CONFIG_FINGERPRINT = hashlib.sha256(
    b"r2-issue39-provider-disabled-config-v1\0"
    b"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=cndlf.com\n"
    b"EMAIL_AGENT_LOG_LEVEL=INFO\n"
).hexdigest()


class Issue39ProductionInputStatusV1(str, Enum):
    READY = "ISSUE39_PRODUCTION_INPUTS_READY"
    BLOCKED_WHEELHOUSE = "BLOCKED_WHEELHOUSE"
    BLOCKED_RUNTIME = "BLOCKED_RUNTIME"
    BLOCKED_HISTORICAL_DATABASE = "BLOCKED_HISTORICAL_DATABASE"
    BLOCKED_DEPENDENCY_LOCK = "BLOCKED_DEPENDENCY_LOCK"


@dataclass(frozen=True, slots=True, repr=False)
class Issue39ProductionInputsV1:
    status: Issue39ProductionInputStatusV1
    manifest_sha256: str = field(repr=False)
    wheel_count: int
    historical_database_count: int
    read_operations: int
    runtime_fingerprint: str = field(repr=False)
    runtime_tree_fingerprint: str = field(repr=False)
    runtime_entry_count: int
    runtime_total_bytes: int
    database_identity_fingerprint: str = field(repr=False)
    crx_fingerprint: str = field(repr=False)
    config_fingerprint: str = field(repr=False)

    def counts(self) -> tuple[int, int, int]:
        return (
            self.wheel_count,
            self.historical_database_count,
            self.read_operations,
        )


def verify_fixed_production_inputs_v1() -> Issue39ProductionInputsV1:
    """Verify the sole reviewed input locations without reading SQLite bytes."""

    repository = Path(__file__).resolve().parents[2]
    return _verify_production_inputs_at(
        wheelhouse=_WHEELHOUSE,
        runtime_executable=_RUNTIME,
        historical_database=_HISTORICAL_DATABASE,
        crx_source=_CRX_SOURCE,
        dependency_lock=repository / "requirements-ci-windows.lock",
        expected_manifest_sha256=_MANIFEST_SHA256,
        expected_wheel_count=31,
        expected_runtime_sha256=_RUNTIME_SHA256,
        expected_runtime_size=91_648,
        expected_runtime_tree_fingerprint=(
            "afe6f653ab7a1760357824f64845f28ac6dea81f107f6df220321a3b3d6d2d2f"
        ),
        expected_runtime_entry_count=3_684,
        expected_runtime_total_bytes=66_855_518,
        expected_database_size=12_288,
        expected_crx_sha256=_CRX_SHA256,
        expected_crx_size=54_864,
        expected_dependency_lock_sha256=_DEPENDENCY_LOCK_SHA256,
    )


def _verify_production_inputs_at(
    *,
    wheelhouse: Path,
    runtime_executable: Path,
    historical_database: Path,
    crx_source: Path,
    dependency_lock: Path,
    expected_manifest_sha256: str,
    expected_wheel_count: int,
    expected_runtime_sha256: str,
    expected_runtime_size: int,
    expected_database_size: int,
    expected_crx_sha256: str,
    expected_crx_size: int,
    expected_dependency_lock_sha256: str | None = None,
    expected_runtime_tree_fingerprint: str | None = None,
    expected_runtime_entry_count: int | None = None,
    expected_runtime_total_bytes: int | None = None,
) -> Issue39ProductionInputsV1:
    try:
        return _verify_values(locals())
    except WheelhouseValidationError as error:
        status = (
            Issue39ProductionInputStatusV1.BLOCKED_DEPENDENCY_LOCK
            if error.reason == "dependency_lock"
            else Issue39ProductionInputStatusV1.BLOCKED_WHEELHOUSE
        )
        return _blocked_inputs(status)
    except _Blocked as error:
        return _blocked_inputs(error.status)
    except Exception:
        return _blocked_inputs(Issue39ProductionInputStatusV1.BLOCKED_WHEELHOUSE)


def _verify_values(values):
    entries = _verify_wheelhouse(values)
    runtime = _verify_runtime(values)
    database = values["historical_database"]
    if (
        not _regular_non_reparse(database)
        or database.stat().st_size != values["expected_database_size"]
    ):
        raise _Blocked(Issue39ProductionInputStatusV1.BLOCKED_HISTORICAL_DATABASE)
    database_identity = _file_identity_fingerprint(database)
    crx = values["crx_source"]
    if (
        crx.stat().st_size != values["expected_crx_size"]
        or _hash_regular_file(crx, values["expected_crx_size"])
        != values["expected_crx_sha256"]
    ):
        raise _Blocked(Issue39ProductionInputStatusV1.BLOCKED_WHEELHOUSE)
    return _ready_inputs(values, entries, runtime, database_identity)


def _verify_wheelhouse(values):
    payload = _bounded_regular_bytes(
        values["wheelhouse"] / MANIFEST_NAME, MAX_MANIFEST_BYTES
    )
    if _sha256(payload) != values["expected_manifest_sha256"]:
        raise _Blocked(Issue39ProductionInputStatusV1.BLOCKED_WHEELHOUSE)
    return verify_wheelhouse_manifest(
        manifest=strict_object(payload), wheelhouse=values["wheelhouse"],
        dependency_lock=values["dependency_lock"],
        expected_count=values["expected_wheel_count"],
        hash_regular_file=_hash_regular_file,
        expected_dependency_lock_sha256=values["expected_dependency_lock_sha256"],
    )


def _verify_runtime(values):
    executable = values["runtime_executable"]
    expected_hash = values["expected_runtime_sha256"]
    if (
        executable.stat().st_size != values["expected_runtime_size"]
        or _hash_regular_file(executable, values["expected_runtime_size"])
        != expected_hash
    ):
        raise _Blocked(Issue39ProductionInputStatusV1.BLOCKED_RUNTIME)
    if values["expected_runtime_tree_fingerprint"] is None:
        return None
    from backend.cutover_managed_activation.runtime_source_tree import observe_source_tree

    runtime = observe_source_tree(executable)
    expected = (
        values["expected_runtime_tree_fingerprint"],
        values["expected_runtime_entry_count"],
        values["expected_runtime_total_bytes"], expected_hash,
    )
    if (
        runtime.fingerprint, runtime.entry_count, runtime.total_bytes,
        runtime.executable_sha256,
    ) != expected:
        raise _Blocked(Issue39ProductionInputStatusV1.BLOCKED_RUNTIME)
    return runtime


def _ready_inputs(values, entries, runtime, database_identity):
    runtime_hash = values["expected_runtime_sha256"]
    runtime_size = values["expected_runtime_size"]
    return Issue39ProductionInputsV1(
        Issue39ProductionInputStatusV1.READY,
        values["expected_manifest_sha256"], len(entries), 1,
        len(entries) + 7, runtime_hash,
        runtime.fingerprint if runtime is not None else runtime_hash,
        runtime.entry_count if runtime is not None else 1,
        runtime.total_bytes if runtime is not None else runtime_size,
        database_identity, values["expected_crx_sha256"], _CONFIG_FINGERPRINT,
    )


def _blocked_inputs(status):
        return Issue39ProductionInputsV1(
            status,
            "0" * 64,
            0,
            0,
            0,
            "0" * 64,
            "0" * 64,
            0,
            0,
            "0" * 64,
            "0" * 64,
            "0" * 64,
        )


class _Blocked(Exception):
    def __init__(self, status: Issue39ProductionInputStatusV1) -> None:
        self.status = status
        super().__init__(status.value)


def _bounded_regular_bytes(path: Path, maximum: int) -> bytes:
    if not _regular_non_reparse(path):
        raise ValueError
    size = path.stat().st_size
    if not 1 <= size <= maximum:
        raise ValueError
    payload = path.read_bytes()
    if len(payload) != size:
        raise ValueError
    return payload


def _hash_regular_file(path: Path, maximum: int) -> str:
    if not _regular_non_reparse(path):
        raise ValueError
    size = path.stat().st_size
    if not 1 <= size <= maximum:
        raise ValueError
    digest = hashlib.sha256()
    read = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            read += len(chunk)
            if read > maximum:
                raise ValueError
            digest.update(chunk)
    if read != size:
        raise ValueError
    return digest.hexdigest()


def _regular_non_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return stat.S_ISREG(metadata.st_mode) and not (
        getattr(metadata, "st_file_attributes", 0) & 0x400
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
