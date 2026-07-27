"""Neutral fixed results for migration evidence create and verify seams."""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass

from .contract import (
    MigrationEvidenceCounts,
    MigrationEvidenceResult,
    MigrationEvidenceStatus,
)


@dataclass(frozen=True, slots=True, repr=False)
class MigrationEvidenceCreationResult:
    result: MigrationEvidenceResult
    review_fingerprint: str
    source_snapshot_fingerprint: str
    package_sha256: str
    manifest_sha256: str
    package_identity_fingerprint: str


def success_result(
    status: MigrationEvidenceStatus,
    files: int,
    refs: int,
    worktrees: int,
) -> MigrationEvidenceResult:
    return MigrationEvidenceResult(
        status=status,
        counts=MigrationEvidenceCounts(
            packages=1,
            verified=(
                1 if status is MigrationEvidenceStatus.VERIFIED else 0
            ),
            rejected=0,
            files=files,
            refs=refs,
            worktrees=worktrees,
        ),
    )


def failure_result() -> MigrationEvidenceResult:
    return MigrationEvidenceResult(
        status=MigrationEvidenceStatus.FAILED,
        counts=MigrationEvidenceCounts(
            packages=0,
            verified=0,
            rejected=1,
            files=0,
            refs=0,
            worktrees=0,
        ),
    )


def success_creation_result(
    *,
    result: MigrationEvidenceResult,
    review_fingerprint: str,
    source_snapshot_fingerprint: str,
    package_sha256: str,
    manifest_sha256: str,
    identity: object,
) -> MigrationEvidenceCreationResult:
    identity_fingerprint = _fingerprint(
        {
            "schema": "MigrationEvidencePackageIdentityV1",
            "device": identity.device,
            "inode": identity.inode,
            "mode_type": stat.S_IFMT(identity.mode),
            "size": identity.size,
            "modified_ns": identity.modified_ns,
            "links": identity.links,
            "package_sha256": package_sha256,
            "manifest_sha256": manifest_sha256,
        }
    )
    return MigrationEvidenceCreationResult(
        result=result,
        review_fingerprint=review_fingerprint,
        source_snapshot_fingerprint=source_snapshot_fingerprint,
        package_sha256=package_sha256,
        manifest_sha256=manifest_sha256,
        package_identity_fingerprint=identity_fingerprint,
    )


def failure_creation_result() -> MigrationEvidenceCreationResult:
    zero = "0" * 64
    return MigrationEvidenceCreationResult(
        result=failure_result(),
        review_fingerprint=zero,
        source_snapshot_fingerprint=zero,
        package_sha256=zero,
        manifest_sha256=zero,
        package_identity_fingerprint=zero,
    )


def _fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()
