"""Closed repository transaction journal values."""

from enum import Enum


class ForwardBoundary(str, Enum):
    SOURCE_FROZEN = "source_frozen"
    WORKTREES_PRESERVED = "worktrees_preserved"
    LEGACY_RENAMED = "legacy_renamed"
    CONTAINER_PUBLISHED = "container_published"
    NON_MAIN_ZONES_PUBLISHED = "non_main_zones_published"
    MAIN_PUBLISHED = "main_published"
    WORKTREES_RECREATED = "worktrees_recreated"
    REPOSITORY_FINAL_VERIFIED = "repository_final_verified"


class ReverseBoundary(str, Enum):
    NEW_STATE_PRESERVED = "new_state_preserved"
    MAIN_EXTRACTED = "main_extracted"
    ADMIN_RECORDS_RESTORED = "admin_records_restored"
    PHYSICAL_WORKTREES_RESTORED = "physical_worktrees_restored"
    ORIGINAL_REPOSITORY_VERIFIED = "original_repository_verified"


class RepositoryJournalDirection(str, Enum):
    FORWARD = "forward"
    REVERSE = "reverse"


class RepositoryJournalEvent(str, Enum):
    INTENT = "intent"
    OBSERVED = "observed"
    COMMITTED = "committed"
    ABORTED = "aborted"


class RepositoryJournalOutcome(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    NOT_APPLIED = "not_applied"


class RepositoryMutationKind(str, Enum):
    PHYSICAL_MOVE = "physical_move"
    ADMIN_MOVE = "admin_move"
    CREATE_DIRECTORY = "create_directory"
    RESERVE_WORKTREE = "reserve_worktree"
    GIT_WORKTREE_ADD = "git_worktree_add"
    VERIFY = "verify"
