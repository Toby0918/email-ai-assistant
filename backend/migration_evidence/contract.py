"""Immutable review values for a no-clobber migration evidence package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class DirtyDisposition(str, Enum):
    """The exact dirty-path review dispositions."""

    INCLUDED = "included"
    EXCLUDED = "excluded"


class DirtyReason(str, Enum):
    """Content-free reasons used by the inclusion/exclusion manifest."""

    APPROVED_SOURCE = "approved_source"
    NOT_APPROVED = "not_approved"
    IGNORED = "ignored"
    CREDENTIAL = "credential"
    SIGNING_MATERIAL = "signing_material"
    SQLITE = "sqlite"
    LOG = "log"
    PID_STATE = "pid_state"
    VIRTUAL_ENVIRONMENT = "virtual_environment"
    IDE_STATE = "ide_state"
    PRIVATE_DATA = "private_data"
    CACHE = "cache"
    OUTPUT = "output"


class MigrationEvidenceStatus(str, Enum):
    """The complete public create/verify status allowlist."""

    CREATED = "migration_evidence_created"
    VERIFIED = "migration_evidence_verified"
    FAILED = "migration_evidence_failed"


@dataclass(frozen=True, slots=True)
class MigrationEvidenceCounts:
    """Bounded aggregate counts with no path or identity values."""

    packages: int
    verified: int
    rejected: int
    files: int
    refs: int
    worktrees: int


@dataclass(frozen=True, slots=True)
class MigrationEvidenceResult:
    """A fixed public result with no diagnostic field."""

    status: MigrationEvidenceStatus
    counts: MigrationEvidenceCounts


@dataclass(frozen=True, slots=True, repr=False)
class HostBaseline:
    """Reviewed ACL and volume metadata with no account or path values."""

    schema_version: int
    acl_sha256: str
    acl_entry_count: int
    volume_sha256: str
    filesystem_name: str
    drive_type: str
    evidence_complete: bool
    content_observed: bool


@dataclass(frozen=True, slots=True, repr=False)
class DirtyEntryReview:
    """One exact status path and its reviewed disposition."""

    path: str
    status: str
    tracked: bool
    ignored: bool
    disposition: DirtyDisposition
    reason: DirtyReason


@dataclass(frozen=True, slots=True, repr=False)
class ReviewedRef:
    """One approved local branch ref at an exact object ID."""

    name: str
    oid: str


@dataclass(frozen=True, slots=True, repr=False)
class ReviewedWorktree:
    """One worktree discovered from Git and bound to branch plus HEAD."""

    path: Path
    path_sha256: str
    branch_ref: str
    head_oid: str
    status_sha256: str
    status_count: int
    is_main: bool


@dataclass(frozen=True, slots=True, repr=False)
class RemoteBaseline:
    """A remote name with hashed URL and fetch configuration."""

    name: str
    url_sha256: str
    fetch_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class GitBaseline:
    """Bounded content-free state for the reviewed repository root."""

    branch_ref: str
    head_oid: str
    upstream_ref: str
    ahead: int
    behind: int
    remotes: tuple[RemoteBaseline, ...]


@dataclass(frozen=True, slots=True, repr=False)
class MigrationEvidenceReview:
    """Exact operator-review value required before package creation."""

    schema_version: int
    repository_root: Path
    target: Path
    dirty_entries: tuple[DirtyEntryReview, ...]
    reviewed_refs: tuple[ReviewedRef, ...]
    worktrees: tuple[ReviewedWorktree, ...]
    git_baseline: GitBaseline
    host_baseline: HostBaseline
    review_fingerprint: str
