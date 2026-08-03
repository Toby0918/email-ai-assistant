"""Closed contracts for the dormant R2 repository-manifest slice."""

from .contracts import (
    RepositoryContentManifestV1,
    RepositoryTopologyReceiptV1,
)
from ._git_byte_validation_v2 import GitByteStateError
from .git_byte_receipt_v2 import R2GitByteStateReceiptV1
from .git_byte_state_v2 import GitByteSnapshotV2
from .git_byte_types_v2 import (
    GitCommonStateRoleV2,
    GitCommonStateV2,
    GitWorktreeStateV2,
    SelectedGitByteV2,
)
from .types import (
    ManifestBoundary,
    ManifestCategory,
    ManifestCrashGap,
    ManifestSelectorV1,
)

__all__ = [
    "ManifestBoundary",
    "ManifestCategory",
    "ManifestCrashGap",
    "ManifestSelectorV1",
    "RepositoryContentManifestV1",
    "RepositoryTopologyReceiptV1",
    "GitByteSnapshotV2",
    "GitByteStateError",
    "GitCommonStateRoleV2",
    "GitCommonStateV2",
    "GitWorktreeStateV2",
    "R2GitByteStateReceiptV1",
    "SelectedGitByteV2",
]
