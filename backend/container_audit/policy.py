"""Trusted content-free expectations and fixed audit limits."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


AUDIT_SCHEMA_VERSION = 1
OPAQUE_FINGERPRINT_LENGTH = 64
MAX_APPROVED_WORKTREES = 64
MAX_CONFIG_BYTES = 16 * 1024
MAX_LOG_METADATA_ENTRIES = 4
MAX_ARTIFACT_METADATA_ENTRIES = 256
MAX_SQLITE_SIZE_BYTES = (1 << 63) - 1
MAX_SQLITE_AGGREGATE_ROW_COUNT = (1 << 63) - 1
MAX_SQLITE_SIDECARS = 3
PINNED_PYTHON_VERSION = "3.12.13"
PINNED_SQLITE_VERSION = "3.50.4"
NORMAL_CONFIG_FILENAME = "settings.env"
NORMAL_SQLITE_FILENAME = "email_agent.sqlite3"
TOP_LEVEL_NAMES = frozenset(
    {
        "main",
        "Runtimes",
        "LocalData",
        "RuntimeTemp",
        "Logs",
        "Artifacts",
        "Worktrees",
        "Config",
        "OperatorPrivate",
    }
)
ALLOWED_CONFIG_KEYS = frozenset(
    {
        "EMAIL_AGENT_LOG_LEVEL",
        "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
    }
)
MAX_CONFIG_KEYS = len(ALLOWED_CONFIG_KEYS)
MAX_VOLUME_BOUND_IDENTITIES = (
    1  # Project Container
    + len(TOP_LEVEL_NAMES)
    + MAX_LOG_METADATA_ENTRIES
    + MAX_ARTIFACT_METADATA_ENTRIES
    + 1  # Git common directory
    + MAX_APPROVED_WORKTREES
    + 2  # pinned runtime root and executable
    + 1  # optional Config/settings.env
    + 1  # optional LocalData/email_agent.sqlite3
)
_LOWER_HEX = frozenset("0123456789abcdef")


class SqliteExpectation(str, Enum):
    """Reviewed preflight or stopped-database state."""

    ABSENT_EXPECTED = "absent_expected"
    STOPPED_PRESENT = "stopped_present"


@dataclass(frozen=True, slots=True, repr=False)
class TrustedAuditPolicy:
    """Independent expected metadata with no path or reader capability."""

    schema_version: int
    container_identity: str
    container_acl_fingerprint: str
    operator_private_acl_fingerprint: str
    volume_identity: str
    approved_worktrees: tuple[str, ...]
    require_clean_worktrees: bool
    sqlite_expectation: SqliteExpectation


def is_opaque_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == OPAQUE_FINGERPRINT_LENGTH
        and all(character in _LOWER_HEX for character in value)
    )


def is_valid_policy(value: object) -> bool:
    if type(value) is not TrustedAuditPolicy:
        return False
    if (
        type(value.schema_version) is not int
        or value.schema_version != AUDIT_SCHEMA_VERSION
        or type(value.require_clean_worktrees) is not bool
        or type(value.sqlite_expectation) is not SqliteExpectation
        or type(value.approved_worktrees) is not tuple
        or len(value.approved_worktrees) > MAX_APPROVED_WORKTREES
    ):
        return False
    fingerprints = (
        value.container_identity,
        value.container_acl_fingerprint,
        value.operator_private_acl_fingerprint,
        value.volume_identity,
        *value.approved_worktrees,
    )
    if not all(is_opaque_fingerprint(item) for item in fingerprints):
        return False
    return (
        tuple(sorted(set(value.approved_worktrees)))
        == value.approved_worktrees
    )
