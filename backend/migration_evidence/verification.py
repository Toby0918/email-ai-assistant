"""Independent verification of one migration evidence package."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .archive_validation import (
    MAX_PACKAGE_BYTES,
    validate_package_payload,
)
from .contract import MigrationEvidenceStatus
from .errors import MigrationEvidenceError
from .git_discovery import git_output
from .path_checks import require_existing_non_reparse_directory
from .results import failure_result, success_result
from .snapshot import read_checked_file


def verify_migration_evidence_package(*, package: Path):
    """Verify archive hashes and a self-contained Git bundle."""

    try:
        payload = _read_package(package)
    except Exception:
        return failure_result()
    return verify_migration_evidence_payload(payload=payload)


def verify_migration_evidence_payload(*, payload: bytes):
    """Verify the exact complete package bytes supplied by a reader."""

    try:
        files, refs, worktrees = validate_package_payload(payload)
        _verify_bundle(payload, refs)
        return success_result(
            MigrationEvidenceStatus.VERIFIED,
            len(files),
            len(refs),
            len(worktrees),
        )
    except Exception:
        return failure_result()


def _read_package(package: Path) -> bytes:
    if not isinstance(package, Path) or not package.is_absolute():
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    if package.name.endswith(".migration-evidence.zip") is False:
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    parent = require_existing_non_reparse_directory(package.parent)
    if parent / package.name != package.absolute():
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    return read_checked_file(
        parent,
        package.name,
        maximum=MAX_PACKAGE_BYTES,
    )


def _verify_bundle(
    package_payload: bytes,
    refs: tuple[tuple[str, str], ...],
) -> None:
    from .archive_validation import _verify_archive

    _manifest, _manifest_bytes, _files, contents = _verify_archive(
        package_payload
    )
    bundle = contents["git/repository.bundle"]
    with tempfile.TemporaryDirectory(
        prefix="migration-evidence-verify-"
    ) as temporary:
        root = Path(temporary).resolve()
        path = root / "repository.bundle"
        path.write_bytes(bundle)
        repository = root / "empty.git"
        git_output(root, ("init", "--bare", str(repository)))
        git_output(repository, ("bundle", "verify", str(path)))
        output = git_output(
            repository,
            ("bundle", "list-heads", str(path)),
        )
        assert output is not None
        if _bundle_heads(output) != refs:
            raise MigrationEvidenceError(
                "migration_evidence_verify_failed"
            )


def _bundle_heads(
    payload: bytes,
) -> tuple[tuple[str, str], ...]:
    try:
        values = []
        for line in payload.decode("utf-8").splitlines():
            oid, separator, name = line.partition(" ")
            if not separator:
                raise MigrationEvidenceError(
                    "migration_evidence_verify_failed"
                )
            values.append((oid, name))
        return tuple(values)
    except UnicodeDecodeError:
        raise MigrationEvidenceError(
            "migration_evidence_verify_failed"
        ) from None
