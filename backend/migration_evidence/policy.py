"""Exact dirty-source inclusion and mechanical exclusion policy."""

from __future__ import annotations

from pathlib import PurePosixPath

from .contract import DirtyReason
from .errors import MigrationEvidenceError


_SOURCE_ROOTS = frozenset(
    {"backend", "docs", "frontend", "scripts", "tests", ".github"}
)
_ROOT_SOURCE = frozenset(
    {
        ".gitignore",
        "AGENTS.md",
        "CONTEXT.md",
        "README.md",
        "requirements.txt",
        "start_local_service.cmd",
        "stop_local_service.cmd",
        "restart_local_service.cmd",
        "status_local_service.cmd",
    }
)
_SOURCE_SUFFIXES = frozenset(
    {".cmd", ".css", ".html", ".js", ".json", ".md", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml"}
)


def validate_relative_path(value: str) -> str:
    """Return one safe Git-style relative path or fail closed."""

    if type(value) is not str or not value or len(value) > 512:
        raise MigrationEvidenceError()
    if "\\" in value or ":" in value or any(ord(character) < 32 for character in value):
        raise MigrationEvidenceError()
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise MigrationEvidenceError()
    if any(len(part) > 128 for part in path.parts):
        raise MigrationEvidenceError()
    return path.as_posix()


def inclusion_reason(path: str, *, ignored: bool) -> DirtyReason:
    """Classify one path without opening it."""

    normalized = validate_relative_path(path)
    parts = tuple(part.casefold() for part in PurePosixPath(normalized).parts)
    name = parts[-1]
    stem = PurePosixPath(name).stem.casefold()
    suffix = PurePosixPath(name).suffix.casefold()
    if _has_credential_marker(name, stem, suffix):
        return DirtyReason.CREDENTIAL
    if _has_signing_marker(name, stem, suffix):
        return DirtyReason.SIGNING_MATERIAL
    if _has_sqlite_marker(name, suffix):
        return DirtyReason.SQLITE
    if suffix == ".log" or ".log." in name or "logs" in parts:
        return DirtyReason.LOG
    if suffix == ".pid" or name.endswith(".pid.lock"):
        return DirtyReason.PID_STATE
    if _has_environment_marker(parts):
        return DirtyReason.VIRTUAL_ENVIRONMENT
    if any(part in {".fleet", ".idea", ".vs", ".vscode"} for part in parts):
        return DirtyReason.IDE_STATE
    if _has_private_marker(parts, suffix):
        return DirtyReason.PRIVATE_DATA
    if _has_cache_marker(parts, suffix):
        return DirtyReason.CACHE
    if _has_output_marker(parts, name):
        return DirtyReason.OUTPUT
    return DirtyReason.IGNORED if ignored else DirtyReason.NOT_APPROVED


def require_approved_source(path: str) -> str:
    """Reject every path outside the exact source/test/docs policy."""

    normalized = validate_relative_path(path)
    reason = inclusion_reason(normalized, ignored=False)
    if reason is not DirtyReason.NOT_APPROVED:
        raise MigrationEvidenceError()
    pure = PurePosixPath(normalized)
    if normalized in _ROOT_SOURCE:
        return normalized
    if pure.parts[0] not in _SOURCE_ROOTS or pure.suffix.casefold() not in _SOURCE_SUFFIXES:
        raise MigrationEvidenceError()
    return normalized


def _has_private_marker(parts: tuple[str, ...], suffix: str) -> bool:
    markers = {
        "operatorprivate",
        "private",
        "private-data",
        "private_data",
        "customer-data",
        "customer_data",
        "recovery",
        "vault",
    }
    return bool(markers.intersection(parts)) or suffix in {
        ".mailvault",
        ".pkeval",
        ".pkevalstage",
    }


def _has_cache_marker(parts: tuple[str, ...], suffix: str) -> bool:
    markers = {
        "__pycache__",
        ".cache",
        ".coverage",
        ".hypothesis",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
        "node_modules",
    }
    return bool(markers.intersection(parts)) or suffix in {".pyc", ".pyo"}


def _has_credential_marker(name: str, stem: str, suffix: str) -> bool:
    names = {
        ".env",
        ".netrc",
        ".npmrc",
        ".pypirc",
        "credentials",
        "secrets",
        "tokens",
        "access-token",
        "api-key",
        "client-secret",
        "refresh-token",
    }
    return name in names or stem in names or suffix in {".secret", ".token"}


def _has_signing_marker(name: str, stem: str, suffix: str) -> bool:
    markers = {
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "private_key",
        "private-key",
        "signing_key",
        "signing-key",
    }
    return name in markers or stem in markers or suffix in {
        ".cer",
        ".crt",
        ".key",
        ".p12",
        ".pem",
        ".pfx",
    }


def _has_sqlite_marker(name: str, suffix: str) -> bool:
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return True
    return name.endswith(
        (
            ".db-journal",
            ".db-shm",
            ".db-wal",
            ".sqlite-journal",
            ".sqlite-shm",
            ".sqlite-wal",
            ".sqlite3-journal",
            ".sqlite3-shm",
            ".sqlite3-wal",
        )
    )


def _has_environment_marker(parts: tuple[str, ...]) -> bool:
    markers = {
        ".nox",
        ".tox",
        ".venv",
        "env",
        "site-packages",
        "venv",
    }
    return bool(markers.intersection(parts))


def _has_output_marker(parts: tuple[str, ...], name: str) -> bool:
    markers = {
        "artifacts",
        "build",
        "dist",
        "outputs",
        "reports",
        "test-results",
    }
    return (
        bool(markers.intersection(parts))
        or name.endswith(".migration-evidence.zip")
    )
