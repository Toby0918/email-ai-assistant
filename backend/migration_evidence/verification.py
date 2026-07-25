"""Independent verification of one migration evidence package."""

from __future__ import annotations

import hashlib
import io
import stat
import tempfile
import zipfile
from pathlib import Path

from .contract import MigrationEvidenceStatus
from .errors import MigrationEvidenceError
from .git_discovery import git_output
from .manifest import manifest_comment, strict_json
from .package import _failure_result, _success_result
from .path_checks import require_existing_non_reparse_directory
from .snapshot import read_checked_file
from .verification_schema import validate_package_semantics


_MAX_PACKAGE_BYTES = 256 * 1024 * 1024


def verify_migration_evidence_package(*, package: Path):
    """Verify archive hashes and a self-contained Git bundle."""

    try:
        payload = _read_package(package)
        manifest, manifest_bytes, files, archive_payloads = _verify_archive(
            payload
        )
        refs, worktrees = validate_package_semantics(
            manifest,
            manifest_bytes,
            archive_payloads,
        )
        _verify_bundle(archive_payloads["git/repository.bundle"], refs)
        return _success_result(
            MigrationEvidenceStatus.VERIFIED,
            len(files),
            len(refs),
            len(worktrees),
        )
    except BaseException:
        return _failure_result()


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
        maximum=_MAX_PACKAGE_BYTES,
    )


def _verify_archive(payload: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if not 1 <= len(names) <= 600 or "manifest.json" not in names:
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            if len(names) != len(set(names)) or len(names) != len(
                {name.casefold() for name in names}
            ):
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            if any(not _valid_zip_info(item) for item in infos):
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            if sum(item.file_size for item in infos) > _MAX_PACKAGE_BYTES:
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            manifest_info = archive.getinfo("manifest.json")
            if manifest_info.file_size > 2 * 1024 * 1024:
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            manifest_bytes = archive.read("manifest.json")
            if archive.comment != manifest_comment(manifest_bytes):
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            manifest = strict_json(manifest_bytes)
            files = _file_records(manifest)
            if set(names) != {"manifest.json", *(item["path"] for item in files)}:
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            contents = {item["path"]: archive.read(item["path"]) for item in files}
    except MigrationEvidenceError:
        raise
    except Exception:
        raise MigrationEvidenceError("migration_evidence_verify_failed") from None
    _verify_file_hashes(files, contents)
    return manifest, manifest_bytes, files, contents


def _file_records(manifest: dict[str, object]) -> tuple[dict[str, object], ...]:
    values = manifest.get("files")
    if type(values) is not list or not 1 <= len(values) <= 599:
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    records: list[dict[str, object]] = []
    for value in values:
        if type(value) is not dict or set(value) != {"path", "size", "sha256"}:
            raise MigrationEvidenceError("migration_evidence_verify_failed")
        if not _valid_archive_path(value["path"]):
            raise MigrationEvidenceError("migration_evidence_verify_failed")
        records.append(value)
    if records != sorted(records, key=lambda item: item["path"]):
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    paths = [item["path"] for item in records]
    if len(paths) != len(set(paths)) or len(paths) != len(
        {item.casefold() for item in paths if type(item) is str}
    ):
        raise MigrationEvidenceError("migration_evidence_verify_failed")
    return tuple(records)


def _verify_file_hashes(files, contents) -> None:
    for record in files:
        path = record["path"]
        size = record["size"]
        digest = record["sha256"]
        if type(path) is not str or path.startswith("/") or "\\" in path or ".." in path.split("/"):
            raise MigrationEvidenceError("migration_evidence_verify_failed")
        if (
            type(size) is not int
            or type(size) is bool
            or size < 0
            or type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise MigrationEvidenceError("migration_evidence_verify_failed")
        payload = contents[path]
        if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
            raise MigrationEvidenceError("migration_evidence_verify_failed")


def _verify_bundle(bundle: bytes, refs: tuple[tuple[str, str], ...]) -> None:
    with tempfile.TemporaryDirectory(prefix="migration-evidence-verify-") as temporary:
        root = Path(temporary).resolve()
        path = root / "repository.bundle"
        path.write_bytes(bundle)
        repository = root / "empty.git"
        git_output(root, ("init", "--bare", str(repository)))
        git_output(repository, ("bundle", "verify", str(path)))
        output = git_output(repository, ("bundle", "list-heads", str(path)))
        assert output is not None
        actual = []
        for line in output.decode("utf-8").splitlines():
            oid, separator, name = line.partition(" ")
            if not separator:
                raise MigrationEvidenceError("migration_evidence_verify_failed")
            actual.append((oid, name))
        if tuple(actual) != refs:
            raise MigrationEvidenceError("migration_evidence_verify_failed")


def _valid_zip_info(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return (
        not info.is_dir()
        and info.compress_type == zipfile.ZIP_STORED
        and info.file_size == info.compress_size
        and info.file_size <= 192 * 1024 * 1024
        and _valid_archive_path(info.filename, allow_manifest=True)
        and stat.S_IFMT(mode) in {0, stat.S_IFREG}
    )


def _valid_archive_path(
    value: object,
    *,
    allow_manifest: bool = False,
) -> bool:
    if type(value) is not str or not 1 <= len(value) <= 512:
        return False
    if value == "manifest.json":
        return allow_manifest
    parts = value.split("/")
    return (
        not value.startswith("/")
        and "\\" not in value
        and ":" not in value
        and all(
            part not in {"", ".", ".."}
            and len(part) <= 128
            and all(32 <= ord(character) != 127 for character in part)
            for part in parts
        )
    )
