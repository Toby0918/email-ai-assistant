"""Fixed content-free Windows observations for Issue #39 preflight."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from backend.r2_production_binding import ProductionCommandV2

from .production_evidence import verify_fixed_issue39_evidence_v1


_PROJECTS = Path(r"D:\Projects")
_SOURCE = _PROJECTS / "email_ai_assistant"
_FINANCE = _PROJECTS / "financial_statement_analysis"
_LEGACY = _PROJECTS / "LegacySourceAnchorV1"
_FAILED = _PROJECTS / "FailedContainerV1"


def observe_fixed(command, prepared, catalog, package):
    if command is ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT:
        _require_directory(_SOURCE)
        _require_directory(_SOURCE / ".git")
        if os.path.lexists(_LEGACY) or os.path.lexists(_FAILED):
            raise ValueError
        return _hash(
            b"r2-issue39-current-topology-v1\0"
            + bytes.fromhex(prepared.prepare_fingerprint)
            + bytes.fromhex(prepared._roster.roster_fingerprint)
        )
    if command is ProductionCommandV2.HOST_BASELINE:
        if _SOURCE.stat().st_dev != _FINANCE.stat().st_dev:
            raise ValueError
        return _hash(
            b"r2-issue39-host-baseline-v1\0"
            + bytes.fromhex(_directory_identity(_PROJECTS))
            + bytes.fromhex(_directory_identity(_FINANCE))
        )
    if command is ProductionCommandV2.EVIDENCE_REVIEW:
        return _hash(
            b"r2-issue39-evidence-review-v1\0"
            + bytes.fromhex(prepared._inputs.manifest_sha256)
            + bytes.fromhex(prepared._roster.roster_fingerprint)
            + bytes.fromhex(catalog.catalog_fingerprint)
        )
    if command is ProductionCommandV2.EVIDENCE_VERIFICATION:
        if verify_fixed_issue39_evidence_v1(package) is not True:
            raise ValueError
        return _hash(
            b"r2-issue39-evidence-verification-v1\0"
            + bytes.fromhex(package.evidence_identity_fingerprint)
        )
    if command is ProductionCommandV2.FINAL_AUDIT_READINESS:
        if any(os.path.lexists(path) for path in (_LEGACY, _FAILED)):
            raise ValueError
        return _hash(
            b"r2-issue39-final-audit-readiness-v1\0"
            + bytes.fromhex(prepared.prepare_fingerprint)
            + bytes.fromhex(package.package_fingerprint)
        )
    if command is ProductionCommandV2.RECOVERY_INSPECTION:
        return _hash(
            b"r2-issue39-recovery-inspection-v1\0"
            + bytes.fromhex(prepared.prepare_fingerprint)
            + bytes.fromhex(catalog.catalog_fingerprint)
        )
    raise ValueError


def _require_directory(path):
    metadata = path.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & 0x400
        or path.is_symlink() or path.is_junction()
    ):
        raise ValueError


def _directory_identity(path):
    _require_directory(path)
    metadata = path.lstat()
    return _hash(
        b"r2-issue39-directory-identity-v1\0"
        + f"{metadata.st_dev}:{metadata.st_ino}".encode("ascii")
    )


def _hash(payload):
    return hashlib.sha256(payload).hexdigest()
